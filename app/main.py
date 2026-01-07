from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .db import get_db
from .ingest import fetch_and_ingest_game_logs
from .features import build_team_features_for_season, get_or_compute_team_features
from .defense_features import build_defense_features_for_season
from .gameplan import generate_gameplan
from .matchups import build_matchups_for_season
from .ml import predict_win_probability
from pydantic import BaseModel
from typing import Optional
from datetime import date

app = FastAPI(title="NBA Team Gameplan Simulator")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def read_root():
    return {"message": "Welcome to NBA Team Gameplan Simulator API"}

@app.post("/v1/admin/ingest/{season}")
def ingest_data(season: str, db: Session = Depends(get_db)):
    """
    Triggers data ingestion for the specified season.
    Returns stats: fetched, inserted, skipped.
    """
    try:
        stats = fetch_and_ingest_game_logs(db, season)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/admin/build-features/{season}")
def build_features(season: str, window: int = 10, min_games: int = 5, db: Session = Depends(get_db)):
    """
    Builds rolling team features for the entire season.
    """
    try:
        stats = build_team_features_for_season(db, season, window, min_games)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/admin/build-defense-features/{season}")
def build_defense_features(season: str, window: int = 10, min_games: int = 5, db: Session = Depends(get_db)):
    """
    Builds rolling defensive team features for the entire season.
    """
    try:
        stats = build_defense_features_for_season(db, season, window, min_games)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/admin/build-matchups/{season}")
def build_matchups(season: str, window: int = 10, db: Session = Depends(get_db)):
    """
    Builds the matchup dataset for the season.
    Joins features for Home/Away teams and creates labeled examples.
    """
    try:
        stats = build_matchups_for_season(db, season, window)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/features/team/{team_id}")
def get_team_features(
    team_id: int, 
    season: str,
    as_of_date: date,
    window: int = 10, 
    db: Session = Depends(get_db)
):
    """
    Retrieves rolling stats for a team as of a specific date.
    """
    features = get_or_compute_team_features(db, team_id, as_of_date, season, window)
    if not features:
        raise HTTPException(status_code=404, detail="Features not found or insufficient history.")
    return features

class PredictionRequest(BaseModel):
    home_team_id: int
    away_team_id: int
    game_date: date
    season: str
    window: int = 10

class GameplanRequest(BaseModel):
    team_a_id: int
    team_b_id: int
    season: str
    as_of_date: date
    window: int = 10

@app.post("/v1/gameplan")
def get_gameplan(req: GameplanRequest, db: Session = Depends(get_db)):
    """
    Generates matchup-based gameplan tips for both teams.
    """
    try:
        plan = generate_gameplan(db, req.team_a_id, req.team_b_id, req.season, req.as_of_date, req.window)
        if not plan:
            raise HTTPException(status_code=404, detail="Insufficient data to generate gameplan.")
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/predict/win-probability")
def predict(req: PredictionRequest, db: Session = Depends(get_db)):
    """
    Predicts the win probability for the Home Team.
    Fetches features for both teams as of the game_date and runs the ML model.
    """
    home_feat = get_or_compute_team_features(db, req.home_team_id, req.game_date, req.season, req.window)
    away_feat = get_or_compute_team_features(db, req.away_team_id, req.game_date, req.season, req.window)
    
    if not home_feat or not away_feat:
        raise HTTPException(status_code=404, detail="Insufficient data/history for one or both teams to make prediction.")
    
    try:
        prob = predict_win_probability(home_feat, away_feat)
        return {
            "home_team_id": req.home_team_id,
            "away_team_id": req.away_team_id,
            "game_date": req.game_date,
            "home_win_prob": prob,
            "implied_odds_home": 1/prob if prob > 0 else 999.0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

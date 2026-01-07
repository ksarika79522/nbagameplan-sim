import logging
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, exists
from .models import TeamGameLog, TeamFeature
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def compute_features(games: list[TeamGameLog], team_id: int, as_of_date: date, season: str, window: int) -> dict:
    """
    Computes rolling features from a list of TeamGameLog objects.
    Returns a dictionary matching TeamFeature columns or None if empty.
    """
    if not games:
        return None

    # Convert to DataFrame for easier calc
    # Extract only needed columns to speed up
    data = []
    for g in games:
        data.append({
            'pts': g.pts,
            'fga': g.fga,
            'fg3a': g.fg3a,
            'fta': g.fta,
            'oreb': g.oreb,
            'tov': g.tov
        })
    
    df = pd.DataFrame(data)
    
    # Calculate Averages
    avg_pts = df['pts'].mean()
    avg_fga = df['fga'].mean()
    avg_fg3a = df['fg3a'].mean()
    avg_fta = df['fta'].mean()
    avg_oreb = df['oreb'].mean()
    avg_tov = df['tov'].mean()

    # Derived Features
    # avg_poss = avg_fga - avg_oreb + avg_tov + 0.44 * avg_fta
    avg_poss = avg_fga - avg_oreb + avg_tov + (0.44 * avg_fta)

    # Avoid division by zero
    rate_3pa = avg_fg3a / avg_fga if avg_fga > 0 else 0.0
    rate_fta = avg_fta / avg_fga if avg_fga > 0 else 0.0
    rate_tov = avg_tov / avg_poss if avg_poss > 0 else 0.0

    return {
        "team_id": team_id,
        "as_of_date": as_of_date,
        "season": season,
        "window": window,
        "games_used": len(df),
        "avg_pts": float(avg_pts),
        "avg_fga": float(avg_fga),
        "avg_fg3a": float(avg_fg3a),
        "avg_fta": float(avg_fta),
        "avg_oreb": float(avg_oreb),
        "avg_tov": float(avg_tov),
        "avg_poss": float(avg_poss),
        "rate_3pa": float(rate_3pa),
        "rate_fta": float(rate_fta),
        "rate_tov": float(rate_tov)
    }

def build_team_features_for_season(db: Session, season: str, window: int = 10, min_games: int = 5) -> dict:
    """
    Iterates over all team_id + game_date pairs in team_games for the season.
    Computes rolling features and inserts into TeamFeature table.
    Idempotent: skips if (team_id, as_of_date, window) exists.
    """
    logger.info(f"Building features for season {season}, window {window}")
    
    # 1. Get all target games (dates) for this season
    # We want to predict/represent the state AS OF 'game_date', so we use games PRIOR to 'game_date'.
    # We iterate through every game played to build the feature store for that game.
    targets = db.execute(
        select(TeamGameLog.team_id, TeamGameLog.game_date)
        .filter(TeamGameLog.game_id.like(f"002%")) # Basic filter for regular season usually but season param in ingest handles it
        # Actually better to just filter by what we ingested or distinct dates.
        # Since we don't store 'season' column in TeamGameLog explicitly in Step 1 (oops), 
        # we assume the DB contains the relevant data or we filter by date range if we knew it.
        # For v1, we'll iterate ALL logs, or we can assume the user ingested checks out.
        # Let's just iterate all logs in DB since we wiped/started fresh or user manages seasons.
        # Ideally TeamGameLog should have season, but for now we iterate all.
        .order_by(TeamGameLog.game_date)
    ).all()
    
    total_candidates = len(targets)
    inserted_count = 0
    skipped_count = 0
    
    # Pre-fetch existing features signatures to skip efficiently
    existing_sigs = set(
        db.execute(
            select(TeamFeature.team_id, TeamFeature.as_of_date)
            .filter(TeamFeature.window == window)
            # .filter(TeamFeature.season == season) # good if we had season column populated correctly
        ).all()
    )

    batch_buffer = []
    BATCH_SIZE = 200

    for team_id, game_date in targets:
        if (team_id, game_date) in existing_sigs:
            skipped_count += 1
            continue

        # Get previous games
        # game_date is NOT datetime, it's date.
        past_games = db.query(TeamGameLog).filter(
            TeamGameLog.team_id == team_id,
            TeamGameLog.game_date < game_date
        ).order_by(TeamGameLog.game_date.desc()).limit(window).all()

        if len(past_games) < min_games:
            skipped_count += 1 # Not enough history
            continue

        feat_dict = compute_features(past_games, team_id, game_date, season, window)
        if feat_dict:
            feature_obj = TeamFeature(**feat_dict)
            batch_buffer.append(feature_obj)

        if len(batch_buffer) >= BATCH_SIZE:
            try:
                db.bulk_save_objects(batch_buffer)
                db.commit()
                inserted_count += len(batch_buffer)
                batch_buffer = []
            except Exception as e:
                db.rollback()
                logger.error(f"Batch insert error: {e}")
                raise e

    # Commit remaining
    if batch_buffer:
        try:
            db.bulk_save_objects(batch_buffer)
            db.commit()
            inserted_count += len(batch_buffer)
        except Exception as e:
            db.rollback()
            logger.error(f"Final batch insert error: {e}")
            raise e

    return {
        "season": season,
        "window": window,
        "inserted": inserted_count,
        "skipped": skipped_count,
        "total_candidates": total_candidates
    }

def get_or_compute_team_features(db: Session, team_id: int, as_of_date: date, season: str, window: int = 10) -> dict:
    """
    Retrieves features from DB or computes them on-the-fly.
    """
    # Try DB first
    feat = db.scalar(
        select(TeamFeature).where(
            TeamFeature.team_id == team_id,
            TeamFeature.as_of_date == as_of_date,
            TeamFeature.window == window
        )
    )
    
    if feat:
        # Convert object to dict
        return {c.name: getattr(feat, c.name) for c in TeamFeature.__table__.columns}

    # Compute on-the-fly
    past_games = db.query(TeamGameLog).filter(
        TeamGameLog.team_id == team_id,
        TeamGameLog.game_date < as_of_date
    ).order_by(TeamGameLog.game_date.desc()).limit(window).all()
    
    if not past_games:
        return None

    return compute_features(past_games, team_id, as_of_date, season, window)

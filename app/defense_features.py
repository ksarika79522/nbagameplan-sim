import logging
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, exists
from .models import TeamGameLog, TeamDefFeature
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def compute_defense_features(games: list[TeamGameLog], db: Session, team_id: int, as_of_date: date, season: str, window: int) -> dict:
    """
    Computes rolling defensive features from a list of TeamGameLog objects.
    For each game the team played, we find the opponent's stats to see what was "allowed".
    """
    if not games:
        return None

    opp_data = []
    for g in games:
        # Find the opponent's log for the same game
        opp_log = db.execute(
            select(TeamGameLog)
            .filter(TeamGameLog.game_id == g.game_id)
            .filter(TeamGameLog.team_id != team_id)
        ).scalar_one_or_none()

        if opp_log:
            opp_data.append({
                'pts': opp_log.pts,
                'fga': opp_log.fga,
                'fg3a': opp_log.fg3a,
                'fta': opp_log.fta,
                'oreb': opp_log.oreb,
                'tov': opp_log.tov
            })
    
    if not opp_data:
        return None

    df = pd.DataFrame(opp_data)
    
    # Calculate Opponent Averages (what this team allowed)
    avg_opp_pts = df['pts'].mean()
    avg_opp_fga = df['fga'].mean()
    avg_opp_fg3a = df['fg3a'].mean()
    avg_opp_fta = df['fta'].mean()
    avg_opp_oreb = df['oreb'].mean()
    avg_opp_tov = df['tov'].mean()

    # Opponent Possessions = opp_fga - opp_oreb + opp_tov + 0.44 * opp_fta
    # We compute it per game and then average, or average the components. 
    # The prompt says: where opp_poss = opp_fga - opp_oreb + opp_tov + 0.44 * opp_fta
    # We'll use the averages of components to get the rolling average possession.
    avg_opp_poss = avg_opp_fga - avg_opp_oreb + avg_opp_tov + (0.44 * avg_opp_fta)

    # Avoid division by zero
    def_rate_3pa_allowed = avg_opp_fg3a / avg_opp_fga if avg_opp_fga > 0 else 0.0
    def_rate_fta_allowed = avg_opp_fta / avg_opp_fga if avg_opp_fga > 0 else 0.0
    def_rate_tov_forced = avg_opp_tov / avg_opp_poss if avg_opp_poss > 0 else 0.0

    return {
        "team_id": team_id,
        "as_of_date": as_of_date,
        "season": season,
        "window": window,
        "games_used": len(df),
        "def_avg_pts_allowed": float(avg_opp_pts),
        "def_rate_3pa_allowed": float(def_rate_3pa_allowed),
        "def_rate_fta_allowed": float(def_rate_fta_allowed),
        "def_rate_tov_forced": float(def_rate_tov_forced)
    }

def build_defense_features_for_season(db: Session, season: str, window: int = 10, min_games: int = 5) -> dict:
    """
    Iterates over all team_id + game_date pairs in team_game_logs for the season.
    Computes rolling defensive features and inserts into TeamDefFeature table.
    """
    logger.info(f"Building defensive features for season {season}, window {window}")
    
    # Get all target games (dates)
    # Using the same logic as offensive features: iterate all games in DB.
    # We can filter by game_id prefix 002 for regular season if needed, 
    # but the prompt says just use team_games for the season.
    targets = db.execute(
        select(TeamGameLog.team_id, TeamGameLog.game_date)
        .order_by(TeamGameLog.game_date)
    ).all()
    
    total_candidates = len(targets)
    inserted_count = 0
    skipped_count = 0
    
    # Pre-fetch existing signatures
    existing_sigs = set(
        db.execute(
            select(TeamDefFeature.team_id, TeamDefFeature.as_of_date)
            .filter(TeamDefFeature.window == window)
        ).all()
    )

    batch_buffer = []
    BATCH_SIZE = 100 # Smaller batch because we do lookups per game

    for team_id, game_date in targets:
        if (team_id, game_date) in existing_sigs:
            skipped_count += 1
            continue

        # Get previous games for this team
        past_games = db.query(TeamGameLog).filter(
            TeamGameLog.team_id == team_id,
            TeamGameLog.game_date < game_date
        ).order_by(TeamGameLog.game_date.desc()).limit(window).all()

        if len(past_games) < min_games:
            skipped_count += 1
            continue

        feat_dict = compute_defense_features(past_games, db, team_id, game_date, season, window)
        if feat_dict:
            feature_obj = TeamDefFeature(**feat_dict)
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

def get_or_compute_def_features(db: Session, team_id: int, as_of_date: date, season: str, window: int = 10) -> dict:
    """
    Retrieves defensive features from DB or computes them on-the-fly.
    """
    feat = db.scalar(
        select(TeamDefFeature).where(
            TeamDefFeature.team_id == team_id,
            TeamDefFeature.as_of_date == as_of_date,
            TeamDefFeature.window == window
        )
    )
    
    if feat:
        return {c.name: getattr(feat, c.name) for c in TeamDefFeature.__table__.columns}

    past_games = db.query(TeamGameLog).filter(
        TeamGameLog.team_id == team_id,
        TeamGameLog.game_date < as_of_date
    ).order_by(TeamGameLog.game_date.desc()).limit(window).all()
    
    if not past_games:
        return None

    return compute_defense_features(past_games, db, team_id, as_of_date, season, window)


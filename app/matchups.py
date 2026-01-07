import logging
from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import TeamGameLog, TeamFeature, Matchup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def build_matchups_for_season(db: Session, season: str, window: int = 10) -> dict:
    """
    Builds the Matchup dataset for a given season.
    1. Identifies unique games from TeamGameLog.
    2. Determines Home/Away based on 'matchup' string ("vs." vs "@").
    3. Fetches TeamFeatures for both teams as of the game_date.
    4. Inserts into Matchup table.
    """
    logger.info(f"Building matchups for season {season}")

    # 1. Fetch all game logs for the season (iterating by game_id)
    # Since we want to process pairs, let's fetch all logs and group in memory 
    # (assuming filtering by season is done via an implicit check or just iterating all logs that match date range if we had it)
    # We will query ALL logs. If this is huge, we should paginate. 
    # For now (one season ~2460 rows), memory is fine.
    
    logs = db.execute(
        select(TeamGameLog).order_by(TeamGameLog.game_date)
    ).scalars().all()

    # Group by game_id
    games_map = {}
    for log in logs:
        # Filter by season hack (since we didn't store season in log, we rely on user context or check date)
        # Assuming the DB has the right data.
        if log.game_id not in games_map:
            games_map[log.game_id] = []
        games_map[log.game_id].append(log)

    inserted_count = 0
    skipped_count = 0
    batch_buffer = []
    BATCH_SIZE = 100

    # Pre-fetch existing matchups to skip
    existing_matchups = set(
        db.execute(select(Matchup.game_id)).scalars().all()
    )

    for game_id, team_logs in games_map.items():
        if game_id in existing_matchups:
            skipped_count += 1
            continue
        
        if len(team_logs) != 2:
            logger.warning(f"Game {game_id} has {len(team_logs)} logs (expected 2). Skipping.")
            continue

        # Identify Home vs Away
        # Convention: "TEAM vs TEAM" is Home. "TEAM @ TEAM" is Away.
        team_a = team_logs[0]
        team_b = team_logs[1]

        home_log = None
        away_log = None

        if "vs." in team_a.matchup:
            home_log = team_a
            away_log = team_b
        elif "@" in team_a.matchup:
            home_log = team_b
            away_log = team_a
        else:
            # Try the other one
            if "vs." in team_b.matchup:
                home_log = team_b
                away_log = team_a
            elif "@" in team_b.matchup:
                home_log = team_a
                away_log = team_b
        
        if not home_log or not away_log:
            logger.warning(f"Could not determine home/away for {game_id}: {team_a.matchup}, {team_b.matchup}")
            continue

        # Fetch Features
        # We need features AS OF game_date.
        # Note: TeamFeature.as_of_date is the date we 'stand at' to predict.
        # So we look for TeamFeature where as_of_date == game_date.
        
        home_feat = db.scalar(
            select(TeamFeature).where(
                TeamFeature.team_id == home_log.team_id,
                TeamFeature.as_of_date == home_log.game_date,
                TeamFeature.window == window
            )
        )

        away_feat = db.scalar(
            select(TeamFeature).where(
                TeamFeature.team_id == away_log.team_id,
                TeamFeature.as_of_date == away_log.game_date,
                TeamFeature.window == window
            )
        )

        if not home_feat or not away_feat:
            # We strictly require features. If missing (e.g. first games of season), skip.
            # This is correct behavior for ML dataset (no rows with null features).
            skipped_count += 1
            continue

        # Create Matchup Object
        matchup = Matchup(
            game_id=game_id,
            game_date=home_log.game_date,
            season=season,
            home_team_id=home_log.team_id,
            away_team_id=away_log.team_id,
            home_win=1 if home_log.wl == 'W' else 0,
            
            # Home Features
            home_avg_pts=home_feat.avg_pts,
            home_avg_fga=home_feat.avg_fga,
            home_avg_fg3a=home_feat.avg_fg3a,
            home_avg_fta=home_feat.avg_fta,
            home_avg_oreb=home_feat.avg_oreb,
            home_avg_tov=home_feat.avg_tov,
            home_avg_poss=home_feat.avg_poss,
            home_rate_3pa=home_feat.rate_3pa,
            home_rate_fta=home_feat.rate_fta,
            home_rate_tov=home_feat.rate_tov,

            # Away Features
            away_avg_pts=away_feat.avg_pts,
            away_avg_fga=away_feat.avg_fga,
            away_avg_fg3a=away_feat.avg_fg3a,
            away_avg_fta=away_feat.avg_fta,
            away_avg_oreb=away_feat.avg_oreb,
            away_avg_tov=away_feat.avg_tov,
            away_avg_poss=away_feat.avg_poss,
            away_rate_3pa=away_feat.rate_3pa,
            away_rate_fta=away_feat.rate_fta,
            away_rate_tov=away_feat.rate_tov
        )
        
        batch_buffer.append(matchup)

        if len(batch_buffer) >= BATCH_SIZE:
            db.bulk_save_objects(batch_buffer)
            db.commit()
            inserted_count += len(batch_buffer)
            batch_buffer = []

    if batch_buffer:
        db.bulk_save_objects(batch_buffer)
        db.commit()
        inserted_count += len(batch_buffer)

    return {
        "season": season,
        "window": window,
        "inserted": inserted_count,
        "skipped": skipped_count
    }

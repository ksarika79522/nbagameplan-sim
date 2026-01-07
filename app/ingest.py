import logging
import argparse
from sqlalchemy.orm import Session
from sqlalchemy import select
from nba_api.stats.endpoints import leaguegamelog
from datetime import datetime
from .models import TeamGameLog

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_and_ingest_game_logs(db: Session, season: str = '2023-24') -> dict:
    """
    Fetches game logs for a specific season and ingests them into the database.
    Skips duplicates based on (game_id, team_id).
    Returns a dictionary with execution stats.
    """
    logger.info(f"Starting ingestion for season: {season}")
    
    try:
        # Fetch data from NBA API
        logger.info("Fetching data from NBA API...")
        log = leaguegamelog.LeagueGameLog(season=season, player_or_team_abbreviation='T')
        df = log.get_data_frames()[0]
        rows_fetched = len(df)
        logger.info(f"Fetched {rows_fetched} rows from API.")
    except Exception as e:
        logger.error(f"Failed to fetch data from NBA API: {e}")
        raise e

    # Optimization: Pre-fetch existing IDs to avoid N+1 selects
    logger.info("Checking for existing records...")
    existing_keys = set(
        db.execute(
            select(TeamGameLog.game_id, TeamGameLog.team_id)
        ).all()
    )
    logger.info(f"Found {len(existing_keys)} existing records in DB.")

    new_objects = []
    skipped_count = 0

    for _, row in df.iterrows():
        try:
            game_id = str(row['GAME_ID'])
            team_id = int(row['TEAM_ID'])

            if (game_id, team_id) in existing_keys:
                skipped_count += 1
                continue

            # Parse date
            game_date_obj = datetime.strptime(row['GAME_DATE'], '%Y-%m-%d').date()
            
            game_log = TeamGameLog(
                game_id=game_id,
                team_id=team_id,
                game_date=game_date_obj,
                matchup=row['MATCHUP'],
                wl=row['WL'],
                pts=row['PTS'],
                fgm=row['FGM'],
                fga=row['FGA'],
                fg_pct=row['FG_PCT'],
                fg3m=row['FG3M'],
                fg3a=row['FG3A'],
                fg3_pct=row['FG3_PCT'],
                ftm=row['FTM'],
                fta=row['FTA'],
                ft_pct=row['FT_PCT'],
                oreb=row['OREB'],
                dreb=row['DREB'],
                reb=row['REB'],
                ast=row['AST'],
                stl=row['STL'],
                blk=row['BLK'],
                tov=row['TOV'],
                pf=row['PF'],
                plus_minus=row['PLUS_MINUS']
            )
            new_objects.append(game_log)
        except Exception as e:
            logger.error(f"Error preparing row {row.get('GAME_ID')}: {e}")
            continue

    if new_objects:
        try:
            logger.info(f"Inserting {len(new_objects)} new records...")
            db.bulk_save_objects(new_objects)
            db.commit()
            inserted_count = len(new_objects)
        except Exception as e:
            db.rollback()
            logger.error(f"Error committing batch: {e}")
            raise e
    else:
        inserted_count = 0

    logger.info(f"Ingestion complete. Fetched: {rows_fetched}, Inserted: {inserted_count}, Skipped: {skipped_count}")

    return {
        "season": season,
        "rows_fetched": rows_fetched,
        "inserted": inserted_count,
        "skipped": skipped_count
    }

    return {
        "season": season,
        "rows_fetched": rows_fetched,
        "inserted": inserted_count,
        "skipped": skipped_count
    }

if __name__ == "__main__":
    from .db import SessionLocal
    
    parser = argparse.ArgumentParser(description="Ingest NBA Game Logs")
    parser.add_argument("--season", type=str, default="2023-24", help="Season to ingest (e.g., 2023-24)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = fetch_and_ingest_game_logs(db, season=args.season)
        print(stats)
    finally:
        db.close()

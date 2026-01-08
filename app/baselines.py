import logging
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from .models import TeamFeature, TeamDefFeature, SeasonFeatureBaseline

logger = logging.getLogger(__name__)

def compute_and_store_baselines(db: Session, season: str, window: int = 10):
    """
    Computes mean, std, and percentiles for all offensive and defensive features.
    Stores them in SeasonFeatureBaseline table.
    """
    logger.info(f"Computing baselines for {season}, window {window}")
    
    # 1. Fetch Offensive Features
    off_query = select(TeamFeature).filter(TeamFeature.season == season, TeamFeature.window == window)
    off_data = db.execute(off_query).scalars().all()
    
    # 2. Fetch Defensive Features
    def_query = select(TeamDefFeature).filter(TeamDefFeature.season == season, TeamDefFeature.window == window)
    def_data = db.execute(def_query).scalars().all()
    
    if not off_data or not def_data:
        logger.warning("Insufficient data to compute baselines.")
        return {"error": "Insufficient data"}

    # Convert to DataFrames
    off_df = pd.DataFrame([{col.name: getattr(row, col.name) for col in TeamFeature.__table__.columns} for row in off_data])
    def_df = pd.DataFrame([{col.name: getattr(row, col.name) for col in TeamDefFeature.__table__.columns} for row in def_data])

    # Columns to ignore
    ignore = ['id', 'team_id', 'as_of_date', 'season', 'window', 'games_used']
    
    baseline_objects = []

    def process_df(df):
        for col in df.columns:
            if col in ignore:
                continue
            
            series = df[col].dropna()
            if series.empty:
                continue
            
            p = np.percentile(series, [10, 25, 50, 75, 90])
            
            baseline = SeasonFeatureBaseline(
                season=season,
                window=window,
                feature_name=col,
                mean=float(series.mean()),
                std=float(series.std()),
                p10=float(p[0]),
                p25=float(p[1]),
                p50=float(p[2]),
                p75=float(p[3]),
                p90=float(p[4])
            )
            baseline_objects.append(baseline)

    process_df(off_df)
    process_df(def_df)

    # Idempotency: Delete existing for this season/window
    db.execute(delete(SeasonFeatureBaseline).where(
        SeasonFeatureBaseline.season == season,
        SeasonFeatureBaseline.window == window
    ))
    
    db.bulk_save_objects(baseline_objects)
    db.commit()
    
    return {
        "season": season,
        "window": window,
        "features_computed": len(baseline_objects)
    }

def get_baselines_dict(db: Session, season: str, window: int):
    """
    Returns baselines as a nested dict: {feature_name: {mean, std, ...}}
    """
    baselines = db.execute(
        select(SeasonFeatureBaseline).where(
            SeasonFeatureBaseline.season == season,
            SeasonFeatureBaseline.window == window
        )
    ).scalars().all()
    
    return {b.feature_name: {
        "mean": b.mean,
        "std": b.std,
        "p10": b.p10,
        "p25": b.p25,
        "p50": b.p50,
        "p75": b.p75,
        "p90": b.p90
    } for b in baselines}


import logging
import pandas as pd
import numpy as np
import joblib
from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import Matchup
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss

logger = logging.getLogger(__name__)

def run_model_evaluation(db: Session, season: str, window: int = 10):
    """
    Runs walk-forward validation on matchups.
    4 folds: train on k%, test on next block.
    Includes probability calibration.
    """
    # 1. Load Data
    query = select(Matchup).filter(Matchup.season == season).order_by(Matchup.game_date)
    matchups = db.execute(query).scalars().all()
    
    if len(matchups) < 100:
        return {"error": "Not enough matchups for robust evaluation"}

    feature_cols = [
        col.name for col in Matchup.__table__.columns 
        if col.name not in ['id', 'game_id', 'game_date', 'season', 'home_team_id', 'away_team_id', 'home_win']
    ]
    
    data = []
    for m in matchups:
        row = {col: getattr(m, col) for col in feature_cols}
        row['home_win'] = m.home_win
        data.append(row)
        
    df = pd.DataFrame(data).dropna()
    X = df[feature_cols]
    y = df['home_win']

    # 2. Walk-forward Validation (4 folds)
    # We'll use expanding window: 
    # Fold 1: Train 40%, Test 15%
    # Fold 2: Train 55%, Test 15%
    # Fold 3: Train 70%, Test 15%
    # Fold 4: Train 85%, Test 15%
    
    n = len(df)
    fold_results = []
    
    for i in range(4):
        train_end = int(n * (0.4 + i * 0.15))
        test_end = int(n * (0.55 + i * 0.15))
        
        X_train, X_test = X.iloc[:train_end], X.iloc[train_end:test_end]
        y_train, y_test = y.iloc[:train_end], y.iloc[train_end:test_end]
        
        # Pipeline with Calibration
        # We use sigmoid calibration. CalibratedClassifierCV with cv='prefit' 
        # would require a separate val set, but here we can use it with a sub-split 
        # within the training block to be time-safe, or just use 3-fold CV inside 
        # which is usually fine for calibration if the window is large.
        
        # To be strictly time-safe within the fold:
        # We'll split X_train again: 80% fit, 20% calibrate
        cal_split = int(len(X_train) * 0.8)
        X_fit, X_cal = X_train.iloc[:cal_split], X_train.iloc[cal_split:]
        y_fit, y_cal = y_train.iloc[:cal_split], y_train.iloc[cal_split:]
        
        base_pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('model', LogisticRegression(random_state=42))
        ])
        
        base_pipeline.fit(X_fit, y_fit)
        
        calibrated = CalibratedClassifierCV(base_pipeline, cv='prefit', method='sigmoid')
        calibrated.fit(X_cal, y_cal)
        
        # Evaluate on Test
        y_proba = calibrated.predict_proba(X_test)[:, 1]
        y_pred = (y_proba > 0.5).astype(int)
        
        fold_metrics = {
            "fold": i + 1,
            "train_size": len(X_train),
            "test_size": len(X_test),
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "roc_auc": float(roc_auc_score(y_test, y_proba)),
            "brier_score": float(brier_score_loss(y_test, y_proba))
        }
        fold_results.append(fold_metrics)

    # Summary
    summary = {
        "avg_accuracy": float(np.mean([f['accuracy'] for f in fold_results])),
        "avg_auc": float(np.mean([f['roc_auc'] for f in fold_results])),
        "avg_brier": float(np.mean([f['brier_score'] for f in fold_results])),
        "folds": fold_results
    }
    
    return summary


import logging
import joblib
import pandas as pd
import os
from sqlalchemy.orm import Session
from sqlalchemy import select
from .models import Matchup
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, roc_auc_score

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MODEL_PATH = "model.pkl"

def train_model(db: Session):
    """
    Trains a Logistic Regression model to predict home_win.
    Uses time-based split (80/20).
    Saves model pipeline to MODEL_PATH.
    Returns metrics.
    """
    logger.info("Loading matchups from database...")
    
    # 1. Load Data
    # Fetch all matchups, sorted by date (CRITICAL for time-series split)
    query = select(Matchup).order_by(Matchup.game_date)
    matchups = db.execute(query).scalars().all()
    
    if not matchups:
        logger.error("No matchups found in DB. Cannot train.")
        return None

    # Convert to DataFrame
    data = []
    # Identify feature columns dynamically (excluding IDs/metadata)
    # Metadata: id, game_id, game_date, season, home_team_id, away_team_id, home_win
    # Features: everything else
    feature_cols = [
        col.name for col in Matchup.__table__.columns 
        if col.name not in ['id', 'game_id', 'game_date', 'season', 'home_team_id', 'away_team_id', 'home_win']
    ]
    
    for m in matchups:
        row = {col: getattr(m, col) for col in feature_cols}
        row['home_win'] = m.home_win
        row['game_date'] = m.game_date # Keep for debug if needed, but implicit order is key
        data.append(row)
        
    df = pd.DataFrame(data)
    
    # Drop rows with NaN if any (shouldn't be based on builder logic, but safe check)
    df = df.dropna()
    
    if df.empty:
        return {"error": "No valid data after dropping NaNs"}

    X = df[feature_cols]
    y = df['home_win']
    
    # 2. Time-Based Split
    # First 80% train, Last 20% test
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    logger.info(f"Training on {len(X_train)} games, Testing on {len(X_test)} games")
    
    # 3. Pipeline: Scaling -> Model
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('model', LogisticRegression(random_state=42))
    ])
    
    # 4. Train
    pipeline.fit(X_train, y_train)
    
    # 5. Evaluate
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1] # Probability of Class 1 (Home Win)
    
    acc = accuracy_score(y_test, y_pred)
    try:
        auc = roc_auc_score(y_test, y_proba)
    except ValueError:
        auc = 0.0 # Handle case with one class in test set
        
    baseline_win_rate = y.mean()
    
    logger.info(f"Model Trained. Accuracy: {acc:.4f}, AUC: {auc:.4f}, Baseline Home Win%: {baseline_win_rate:.4f}")
    
    # 6. Save
    joblib.dump(pipeline, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")
    
    return {
        "accuracy": acc,
        "auc": auc,
        "baseline_win_rate": baseline_win_rate,
        "train_size": len(X_train),
        "test_size": len(X_test)
    }

def predict_win_probability(home_features: dict, away_features: dict) -> float:
    """
    Predicts probability of Home Team winning.
    """
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found. Train model first.")
        
    pipeline = joblib.load(MODEL_PATH)
    
    # Construct input vector in same order as training
    # We essentially need to map the dict keys to the feature columns expected by the model
    # The model expects [home_avg_pts, ..., away_avg_pts, ...]
    
    # Helper to map standard feature names (from TeamFeature) to Matchup column names
    # Matchup cols: home_avg_pts, away_avg_pts
    # Input dict keys: avg_pts, ...
    
    input_data = {}
    
    # Map Home Features
    for k, v in home_features.items():
        if k in ['team_id', 'as_of_date', 'season', 'window', 'games_used', 'id']:
            continue
        col_name = f"home_{k}"
        input_data[col_name] = v
        
    # Map Away Features
    for k, v in away_features.items():
        if k in ['team_id', 'as_of_date', 'season', 'window', 'games_used', 'id']:
            continue
        col_name = f"away_{k}"
        input_data[col_name] = v

    # Ensure we use the exact same columns as training
    # In production, we'd store feature names in the pipeline metadata. 
    # For now, we reconstruct the list from the Matchup model (safe assumption as code & DB are synced)
    feature_cols = [
        col.name for col in Matchup.__table__.columns 
        if col.name not in ['id', 'game_id', 'game_date', 'season', 'home_team_id', 'away_team_id', 'home_win']
    ]
    
    # Create DataFrame for prediction (handles ordering)
    df = pd.DataFrame([input_data])
    
    # Add missing cols with 0 if any (robustness), though keys should match
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0
            
    # Order columns
    df = df[feature_cols]
    
    prob_home_win = pipeline.predict_proba(df)[0][1]
    return float(prob_home_win)

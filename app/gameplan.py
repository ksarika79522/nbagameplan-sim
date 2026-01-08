import logging
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .models import TeamFeature, TeamDefFeature, SeasonFeatureBaseline, Matchup
from .features import get_or_compute_team_features
from .defense_features import get_or_compute_def_features
from .ml import predict_win_probability, MODEL_PATH
from .baselines import get_baselines_dict
import pandas as pd
import numpy as np
import joblib
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_feature_contributions(home_features, away_features):
    """
    Computes top feature contributions for Team A (Home) win probability.
    Returns list of {feature, contribution}.
    """
    if not os.path.exists(MODEL_PATH):
        return []

    pipeline = joblib.load(MODEL_PATH)
    model = pipeline.named_steps['model']
    scaler = pipeline.named_steps['scaler']
    
    # Reconstruct input vector (Home then Away)
    feature_cols = [
        col.name for col in Matchup.__table__.columns 
        if col.name not in ['id', 'game_id', 'game_date', 'season', 'home_team_id', 'away_team_id', 'home_win']
    ]
    
    input_data = {}
    for k, v in home_features.items():
        if f"home_{k}" in feature_cols: input_data[f"home_{k}"] = v
    for k, v in away_features.items():
        if f"away_{k}" in feature_cols: input_data[f"away_{k}"] = v
        
    df = pd.DataFrame([input_data])
    for col in feature_cols:
        if col not in df.columns: df[col] = 0.0
    df = df[feature_cols]
    
    # Standardize
    X_scaled = scaler.transform(df)[0]
    
    # Contribution = scaled_value * coefficient
    # For LogReg, positive contribution means increases prob of Class 1 (Home Win)
    coeffs = model.coef_[0]
    contributions = []
    for i, col in enumerate(feature_cols):
        contributions.append({
            "feature": col,
            "contribution": float(X_scaled[i] * coeffs[i])
        })
        
    # Sort by absolute contribution
    contributions = sorted(contributions, key=lambda x: abs(x['contribution']), reverse=True)
    return contributions[:3]

def generate_team_tips(team_off, team_def, opp_off, opp_def, baselines):
    """
    Generates and ranks tips for a single team using z-scores and rarity.
    """
    candidate_tips = []
    
    def add_tip(condition_met, score, theme, text, evidence):
        if condition_met and score > 0.6:
            candidate_tips.append({
                "theme": theme,
                "text": text,
                "score": round(float(score), 2),
                "evidence": evidence
            })

    # Helper for z-score
    def get_z(val, feat):
        b = baselines.get(feat)
        if not b or b['std'] == 0: return 0
        return (val - b['mean']) / b['std']

    # 1. Opponent 3P Weakness vs Team 3P Tendency
    opp_3p_allowed_z = get_z(opp_def['def_rate_3pa_allowed'], 'def_rate_3pa_allowed')
    team_3p_z = get_z(team_off['rate_3pa'], 'rate_3pa')
    # Tip score is high if opponent allows more than average AND team shoots more than average
    score_3p = (opp_3p_allowed_z + team_3p_z) / 2
    add_tip(
        opp_3p_allowed_z > 0.5,
        score_3p,
        "OFFENSE",
        "Emphasize three-point volume and drive-and-kick actions.",
        f"Opponent allows 3PA at a {opp_3p_allowed_z:.1f} std dev rate."
    )

    # 2. Attack the Rim (FTA)
    opp_fta_allowed_z = get_z(opp_def['def_rate_fta_allowed'], 'def_rate_fta_allowed')
    team_fta_z = get_z(team_off['rate_fta'], 'rate_fta')
    score_fta = (opp_fta_allowed_z + team_fta_z) / 2
    add_tip(
        opp_fta_allowed_z > 0.5,
        score_fta,
        "OFFENSE",
        "Attack the paint and put pressure on the rim.",
        f"Opponent gives up free throws at a {opp_fta_allowed_z:.1f} std dev rate."
    )

    # 3. Overall Defensive Vulnerability
    opp_pts_allowed_z = get_z(opp_def['def_avg_pts_allowed'], 'def_avg_pts_allowed')
    add_tip(
        opp_pts_allowed_z > 1.0,
        opp_pts_allowed_z,
        "PACE",
        "Push tempo and look for early offense.",
        f"Opponent ranks in bottom tier for points allowed ({opp_def['def_avg_pts_allowed']:.1f} PPG)."
    )

    # 4. Ball Security
    team_tov_z = get_z(team_off['rate_tov'], 'rate_tov')
    opp_forced_tov_z = get_z(opp_def['def_rate_tov_forced'], 'def_rate_tov_forced')
    score_tov = (team_tov_z + opp_forced_tov_z) / 2
    add_tip(
        team_tov_z > 0.5 and opp_forced_tov_z > 0.5,
        score_tov,
        "BALL CONTROL",
        "Protect the ball and avoid risky passes.",
        f"High turnover risk: Opponent forces TOs at +{opp_forced_tov_z:.1f} std dev."
    )

    # 5. Pace Control
    team_poss_z = get_z(team_off['avg_poss'], 'avg_poss')
    opp_poss_z = get_z(opp_off['avg_poss'], 'avg_poss')
    pace_diff_z = team_poss_z - opp_poss_z
    if pace_diff_z > 1.0:
        add_tip(True, pace_diff_z, "TEMPO", "Push pace and play faster than the opponent prefers.", f"Team pace is +{pace_diff_z:.1f} std dev vs opponent.")
    elif pace_diff_z < -1.0:
        add_tip(True, abs(pace_diff_z), "TEMPO", "Control tempo and limit transition opportunities.", f"Team prefers slower pace (-{abs(pace_diff_z):.1f} std dev).")

    # 6. Defensive Priority (Shooters)
    opp_3pa_z = get_z(opp_off['rate_3pa'], 'rate_3pa')
    add_tip(
        opp_3pa_z > 1.0,
        opp_3pa_z,
        "DEFENSE",
        "Run shooters off the line and prioritize closeouts.",
        f"Opponent ranks high in 3P volume (+{opp_3pa_z:.1f} std dev)."
    )

    # 7. Defend without Fouling
    opp_fta_z = get_z(opp_off['rate_fta'], 'rate_fta')
    add_tip(
        opp_fta_z > 1.0,
        opp_fta_z,
        "DEFENSE",
        "Defend without fouling and stay vertical.",
        f"Opponent excels at drawing contact (+{opp_fta_z:.1f} std dev)."
    )

    # Sort and return
    return sorted(candidate_tips, key=lambda x: x['score'], reverse=True)[:5]

def generate_gameplan(db: Session, team_a_id: int, team_b_id: int, season: str, as_of_date: date, window: int):
    """
    Generates a full gameplan for both teams with explainability.
    """
    # 1. Load Features
    a_off = get_or_compute_team_features(db, team_a_id, as_of_date, season, window)
    a_def = get_or_compute_def_features(db, team_a_id, as_of_date, season, window)
    b_off = get_or_compute_team_features(db, team_b_id, as_of_date, season, window)
    b_def = get_or_compute_def_features(db, team_b_id, as_of_date, season, window)

    if not all([a_off, a_def, b_off, b_def]):
        return None

    # 2. Get Win Probability
    win_prob_a = predict_win_probability(a_off, b_off)
    win_prob_b = 1.0 - win_prob_a

    # 3. Get Explainability
    factors = get_feature_contributions(a_off, b_off)

    # 4. Get Baselines
    baselines = get_baselines_dict(db, season, window)
    if not baselines:
        logger.warning("No baselines found. Run compute-baselines first.")
        return None

    # 5. Generate Tips
    tips_a = generate_team_tips(a_off, a_def, b_off, b_def, baselines)
    tips_b = generate_team_tips(b_off, b_def, a_off, a_def, baselines)

    return {
        "team_a": {
            "win_prob": round(win_prob_a, 3),
            "tips": tips_a
        },
        "team_b": {
            "win_prob": round(win_prob_b, 3),
            "tips": tips_b
        },
        "top_factors": factors
    }


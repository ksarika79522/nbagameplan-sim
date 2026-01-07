import logging
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .models import TeamFeature, TeamDefFeature
from .features import get_or_compute_team_features
from .defense_features import get_or_compute_def_features
from .ml import predict_win_probability
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_league_averages(db: Session, season: str, window: int):
    """
    Computes league-wide averages and std devs for offensive and defensive features.
    """
    # Offensive Averages
    off_query = select(
        func.avg(TeamFeature.avg_pts).label('avg_pts'),
        func.avg(TeamFeature.avg_poss).label('avg_poss'),
        func.avg(TeamFeature.rate_3pa).label('rate_3pa'),
        func.avg(TeamFeature.rate_fta).label('rate_fta'),
        func.avg(TeamFeature.rate_tov).label('rate_tov'),
        func.stddev(TeamFeature.avg_pts).label('std_pts'),
        func.stddev(TeamFeature.rate_3pa).label('std_3pa'),
        func.stddev(TeamFeature.rate_fta).label('std_fta'),
        func.stddev(TeamFeature.rate_tov).label('std_tov')
    ).filter(TeamFeature.season == season, TeamFeature.window == window)
    
    off_res = db.execute(off_query).first()
    
    # Defensive Averages
    def_query = select(
        func.avg(TeamDefFeature.def_avg_pts_allowed).label('avg_pts_allowed'),
        func.avg(TeamDefFeature.def_rate_3pa_allowed).label('rate_3pa_allowed'),
        func.avg(TeamDefFeature.def_rate_fta_allowed).label('rate_fta_allowed'),
        func.avg(TeamDefFeature.def_rate_tov_forced).label('rate_tov_forced'),
        func.stddev(TeamDefFeature.def_avg_pts_allowed).label('std_pts_allowed'),
        func.stddev(TeamDefFeature.def_rate_3pa_allowed).label('std_3pa_allowed'),
        func.stddev(TeamDefFeature.def_rate_fta_allowed).label('std_fta_allowed'),
        func.stddev(TeamDefFeature.def_rate_tov_forced).label('std_tov_forced')
    ).filter(TeamDefFeature.season == season, TeamDefFeature.window == window)
    
    def_res = db.execute(def_query).first()
    
    return {
        'off': off_res,
        'def': def_res
    }

def generate_team_tips(team_off, team_def, opp_off, opp_def, league_avgs):
    """
    Generates and ranks tips for a single team.
    """
    tips = []
    l_off = league_avgs['off']
    l_def = league_avgs['def']

    # OFFENSE vs OPPONENT DEFENSE
    # 1. Opponent allows many 3s
    if opp_def['def_rate_3pa_allowed'] > (l_def.rate_3pa_allowed or 0):
        score = (opp_def['def_rate_3pa_allowed'] - (l_def.rate_3pa_allowed or 0)) / (l_def.std_3pa_allowed or 1)
        tips.append({
            "text": "Emphasize three-point volume and drive-and-kick actions.",
            "score": float(score)
        })

    # 2. Opponent allows many FTs
    if opp_def['def_rate_fta_allowed'] > (l_def.rate_fta_allowed or 0):
        score = (opp_def['def_rate_fta_allowed'] - (l_def.rate_fta_allowed or 0)) / (l_def.std_fta_allowed or 1)
        tips.append({
            "text": "Attack the paint and put pressure on the rim.",
            "score": float(score)
        })

    # 3. Opponent allows many points (Overall Weakness)
    if opp_def['def_avg_pts_allowed'] > (l_def.avg_pts_allowed or 0):
        score = (opp_def['def_avg_pts_allowed'] - (l_def.avg_pts_allowed or 0)) / (l_def.std_pts_allowed or 1)
        tips.append({
            "text": "Push tempo and look for early offense.",
            "score": float(score)
        })

    # 4. Team turns it over AND Opponent forces many turnovers
    if team_off['rate_tov'] > (l_off.rate_tov or 0) and opp_def['def_rate_tov_forced'] > (l_def.rate_tov_forced or 0):
        score = ((team_off['rate_tov'] - (l_off.rate_tov or 0)) / (l_off.std_tov or 1) + 
                 (opp_def['def_rate_tov_forced'] - (l_def.rate_tov_forced or 0)) / (l_def.std_tov_forced or 1))
        tips.append({
            "text": "Protect the ball and avoid risky passes.",
            "score": float(score)
        })

    # TEMPO / STYLE
    # 5. Pace mismatch
    pace_diff = team_off['avg_poss'] - opp_off['avg_poss']
    if pace_diff > 3: # 3 more possessions than opponent
        tips.append({
            "text": "Push pace and play faster than the opponent prefers.",
            "score": float(pace_diff / 5.0) # Normalized roughly
        })
    elif pace_diff < -3:
        tips.append({
            "text": "Control tempo and limit transition opportunities.",
            "score": float(abs(pace_diff) / 5.0)
        })

    # DEFENSIVE FOCUS
    # 6. Opponent shoots many 3s
    if opp_off['rate_3pa'] > (l_off.rate_3pa or 0):
        score = (opp_off['rate_3pa'] - (l_off.rate_3pa or 0)) / (l_off.std_3pa or 1)
        tips.append({
            "text": "Run shooters off the line and prioritize closeouts.",
            "score": float(score)
        })

    # 7. Opponent attacks rim (FTA)
    if opp_off['rate_fta'] > (l_off.rate_fta or 0):
        score = (opp_off['rate_fta'] - (l_off.rate_fta or 0)) / (l_off.std_fta or 1)
        tips.append({
            "text": "Defend without fouling and stay vertical.",
            "score": float(score)
        })

    # Sort and return top 3-5
    tips = sorted(tips, key=lambda x: x['score'], reverse=True)
    return [t['text'] for t in tips[:5]]

def generate_gameplan(db: Session, team_a_id: int, team_b_id: int, season: str, as_of_date: date, window: int):
    """
    Generates a full gameplan for both teams.
    """
    # 1. Load Features
    a_off = get_or_compute_team_features(db, team_a_id, as_of_date, season, window)
    a_def = get_or_compute_def_features(db, team_a_id, as_of_date, season, window)
    b_off = get_or_compute_team_features(db, team_b_id, as_of_date, season, window)
    b_def = get_or_compute_def_features(db, team_b_id, as_of_date, season, window)

    if not all([a_off, a_def, b_off, b_def]):
        return None

    # 2. Get Win Probability
    # Note: predict_win_probability expects (home_features, away_features)
    # Here we treat team_a as home and team_b as away for the sake of the model.
    win_prob_a = predict_win_probability(a_off, b_off)
    win_prob_b = 1.0 - win_prob_a

    # 3. Get League Averages
    league_avgs = get_league_averages(db, season, window)

    # 4. Generate Tips
    tips_a = generate_team_tips(a_off, a_def, b_off, b_def, league_avgs)
    tips_b = generate_team_tips(b_off, b_def, a_off, a_def, league_avgs)

    return {
        "team_a": {
            "win_prob": round(win_prob_a, 3),
            "tips": tips_a
        },
        "team_b": {
            "win_prob": round(win_prob_b, 3),
            "tips": tips_b
        }
    }


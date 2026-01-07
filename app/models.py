from sqlalchemy import Column, Integer, String, Date, Float, Numeric, PrimaryKeyConstraint
import sqlalchemy
from .db import Base

class TeamGameLog(Base):
    __tablename__ = "team_game_logs"

    # Composite Primary Key
    game_id = Column(String, primary_key=True, index=True)
    team_id = Column(Integer, primary_key=True, index=True)
    
    game_date = Column(Date, index=True)
    matchup = Column(String)
    wl = Column(String)  # W or L

    # Base Stats
    pts = Column(Integer)
    fgm = Column(Integer)
    fga = Column(Integer)
    fg_pct = Column(Float)
    fg3m = Column(Integer)
    fg3a = Column(Integer)
    fg3_pct = Column(Float)
    ftm = Column(Integer)
    fta = Column(Integer)
    ft_pct = Column(Float)
    oreb = Column(Integer)
    dreb = Column(Integer)
    reb = Column(Integer)
    ast = Column(Integer)
    stl = Column(Integer)
    blk = Column(Integer)
    tov = Column(Integer)
    pf = Column(Integer)
    plus_minus = Column(Float)

    # Ensure uniqueness on game_id and team_id at DB level
    __table_args__ = (
        PrimaryKeyConstraint('game_id', 'team_id'),
    )

class TeamFeature(Base):
    __tablename__ = "team_features"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, index=True, nullable=False)
    as_of_date = Column(Date, index=True, nullable=False)
    season = Column(String, nullable=False)
    window = Column(Integer, nullable=False, default=10)
    games_used = Column(Integer, nullable=False)

    # Rolling Averages
    avg_pts = Column(Float)
    avg_fga = Column(Float)
    avg_fg3a = Column(Float)
    avg_fta = Column(Float)
    avg_oreb = Column(Float)
    avg_tov = Column(Float)

    # Derived Features
    avg_poss = Column(Float)
    rate_3pa = Column(Float)
    rate_fta = Column(Float)
    rate_tov = Column(Float)

    # Unique constraint on (team_id, as_of_date, window)
    __table_args__ = (
        sqlalchemy.UniqueConstraint('team_id', 'as_of_date', 'window', name='uq_team_feature'),
    )

class Matchup(Base):
    __tablename__ = "matchups"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(String, unique=True, index=True, nullable=False)
    game_date = Column(Date, index=True, nullable=False)
    season = Column(String, nullable=False)
    
    home_team_id = Column(Integer, nullable=False)
    away_team_id = Column(Integer, nullable=False)
    
    # Label: 1 if home team won, 0 otherwise
    home_win = Column(Integer, nullable=False)

    # Home Team Features
    home_avg_pts = Column(Float)
    home_avg_fga = Column(Float)
    home_avg_fg3a = Column(Float)
    home_avg_fta = Column(Float)
    home_avg_oreb = Column(Float)
    home_avg_tov = Column(Float)
    home_avg_poss = Column(Float)
    home_rate_3pa = Column(Float)
    home_rate_fta = Column(Float)
    home_rate_tov = Column(Float)

    # Away Team Features
    away_avg_pts = Column(Float)
    away_avg_fga = Column(Float)
    away_avg_fg3a = Column(Float)
    away_avg_fta = Column(Float)
    away_avg_oreb = Column(Float)
    away_avg_tov = Column(Float)
    away_avg_poss = Column(Float)
    away_rate_3pa = Column(Float)
    away_rate_fta = Column(Float)
    away_rate_tov = Column(Float)

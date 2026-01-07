from .db import engine, Base
from .db import engine, Base
from .db import engine, Base
from .models import TeamGameLog, TeamFeature, Matchup

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()

from .db import SessionLocal
from .ml import train_model

if __name__ == "__main__":
    db = SessionLocal()
    try:
        print("Starting training...")
        metrics = train_model(db)
        print("Training complete.")
        print(f"Metrics: {metrics}")
    finally:
        db.close()

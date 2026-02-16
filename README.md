# 🏀 NBA Team Gameplan Simulator

NBA Team Gameplan Simulator is a full-stack analytics application that estimates win probabilities for NBA matchups and generates strategic gameplans. It uses historical game data, rolling performance features, and a Machine Learning model to provide actionable insights.

## 🚀 Features
- **Win Probability Prediction**: ML-driven estimation of game outcomes.
- **Dynamic Gameplans**: Generates at least 3 strategic tips per team based on statistical mismatches.
- **Automated Data Ingestion**: Fetches and processes official NBA stats via `nba_api`.
- **Explainable AI**: Shows the top factors contributing to a prediction.

---

## 🛠️ Tech Stack
- **Backend**: FastAPI (Python 3.12+)
- **Frontend**: Next.js 14 (React, TypeScript, Tailwind CSS)
- **Database**: PostgreSQL (Supabase)
- **ORM**: SQLAlchemy
- **Machine Learning**: Scikit-Learn (Logistic Regression)

---

## 📋 Prerequisites
- Python 3.12 or higher
- Node.js 18 or higher
- A Supabase (or PostgreSQL) instance

---

## ⚙️ Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd nbagameplan-sim
```

### 2. Backend Setup
Create a virtual environment and install dependencies:
```bash
# Create venv
python3 -m venv venv
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://postgres.[PROJECT-ID]:[PASSWORD]@aws-0-us-west-2.pooler.supabase.com:6543/postgres
```
> **Note**: Ensure your password is URL-encoded if it contains special characters.

### 4. Frontend Setup
```bash
cd frontend
npm install
```

---

## 🏃 Running the Application

### Start the Backend
From the root directory:
```bash
python3 -m uvicorn app.main:app --reload --port 8000
```

### Start the Frontend
From the `frontend` directory:
```bash
npm run dev
```
The app will be available at [http://localhost:3000](http://localhost:3000).

---

## 📊 Data Pipeline (Admin)
To populate the app with data, use the following API endpoints (accessible via Swagger UI at `http://localhost:8000/docs`):

1.  **Ingest Data**: `POST /v1/admin/ingest/{season}` (e.g., `2023-24`)
2.  **Build Features**: `POST /v1/admin/build-features/{season}`
3.  **Build Defensive Features**: `POST /v1/admin/build-defense-features/{season}`
4.  **Compute Baselines**: `POST /v1/admin/compute-baselines/{season}`
5.  **Train Model**: Run `python app/train.py` locally to generate `model.pkl`.

---

## 📁 Project Structure
- `app/`: FastAPI backend logic, models, and data processing.
- `frontend/`: Next.js application and UI components.
- `requirements.txt`: Python dependencies.
- `model.pkl`: The trained ML pipeline.

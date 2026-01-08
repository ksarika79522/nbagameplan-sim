# NBA Team Gameplan Frontend

A Next.js MVP for the NBA Team Gameplan Simulator.

## Prerequisites

- Node.js (v18+)
- Backend running at `http://localhost:8000`

## Installation

```bash
cd frontend
npm install
```

## Running the App

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Features

- **Matchup Selection**: Pick two NBA teams.
- **Data Filtering**: Choose season, date, and rolling window size.
- **Win Probability**: Real-time prediction from the Day 4 Logistic Regression model.
- **Coaching Tips**: Top scouting notes ranked by statistical significance.
- **Proxy Support**: Uses `/api/gameplan` to avoid CORS issues.


# Command Card (MVP)

Private, local-first personal development planner + source-backed daily quiz app.

Frontend is mobile-friendly for iPhone/Android browsers with a responsive single-column layout on small screens.

## Security + Source Of Truth
- LLM output is never the source of truth. Only **user-approved facts** are allowed to generate questions.
- API now requires an `x-app-password` header for all `/api/*` routes.

## Production Target
- Frontend: Vercel free project name `arjunsheep`
- Backend: Fly.io app `arjunsheep-api`
- DB: Managed Postgres via `DATABASE_URL`

## Important Key Hygiene
You shared an OpenAI key in chat. Rotate/revoke it immediately in the OpenAI dashboard and create a new one before deploy.

## Architecture
- **Backend**: FastAPI + SQLModel + configurable DB URL (`backend/app`)
- **Frontend**: React + Vite + TypeScript (`frontend`)
- **Planner**: deterministic scoring for day type, deficits, staleness, weakness, missed recency
- **Quiz**: due + weakness + importance + focus + randomness
- **LLM adapter**: mock by default, OpenAI adapter when `OPENAI_API_KEY` is set
- **Calendar**: manual events + google placeholder via `source=google`

## Local Setup
### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
# set APP_PASSWORD and optionally OPENAI_API_KEY
python seed.py
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
cp .env.example .env
# set VITE_API_URL and VITE_APP_PASSWORD
npm install
npm run dev
```

## Test
```bash
cd backend
pytest
```

## Required Env Vars
Backend (`backend/.env`):
- `APP_PASSWORD`
- `DATABASE_URL` (Postgres for prod, SQLite is fine locally)
- `OPENAI_API_KEY` (optional)
- `CORS_ORIGINS` (comma-separated)

Frontend (`frontend/.env`):
- `VITE_API_URL`
- `VITE_APP_PASSWORD`

## Core Endpoints
Health, Topics, Weekly Targets, Tasks, Sources/Facts/Questions, Quiz, Planner, Calendar manual events.

## Deploy
### 1. Fly Backend
```bash
cd backend
fly launch --name arjunsheep-api --copy-config --no-deploy
fly postgres create --name arjunsheep-db
fly postgres attach --app arjunsheep-api arjunsheep-db
fly secrets set APP_PASSWORD='YOUR_STRONG_PASSWORD'
fly secrets set OPENAI_API_KEY='YOUR_NEW_ROTATED_KEY'
fly secrets set CORS_ORIGINS='https://arjunsheep.vercel.app'
fly deploy
```

### 2. Vercel Frontend
- Import `frontend/` as a new Vercel project named `arjunsheep`.
- Set env:
  - `VITE_API_URL=https://arjunsheep-api.fly.dev`
  - `VITE_APP_PASSWORD=<same APP_PASSWORD as backend>`
- Deploy.

## Future Work
- Google Calendar OAuth credentials flow
- PWA install polish
- FSRS scheduling
- iPhone widget
- Better analytics

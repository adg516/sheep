# Command Card (MVP)

Private, local-first personal development planner + source-backed daily quiz app.

Frontend is now mobile-friendly for iPhone/Android browsers (responsive single-column layout on small screens).

## Warning on truth source
LLM output is never the source of truth. Only **user-approved facts** are allowed to generate questions.

## Architecture
- **Backend**: FastAPI + SQLModel + SQLite (`backend/app`)
- **Frontend**: React + Vite + TypeScript (`frontend`)
- **Planner**: deterministic scoring for day type, deficits, staleness, weakness, missed recency
- **Quiz**: due + weakness + importance + focus + randomness
- **LLM adapter**: mock by default, OpenAI adapter when `OPENAI_API_KEY` is set
- **Calendar**: manual events + google placeholder via `source=google`

## Setup
### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
python seed.py
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Test
```bash
cd backend
pytest
```

## Env vars
- `OPENAI_API_KEY` (optional)

## Core endpoints implemented
Health, Topics, Weekly Targets, Tasks, Sources/Facts/Questions, Quiz, Planner, Calendar manual events.

## Future work
- Google Calendar OAuth credentials flow
- PWA install polish
- FSRS scheduling
- iPhone widget
- Better analytics

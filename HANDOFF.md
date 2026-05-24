# Command Card UI Handoff

Last updated: 2026-05-24

## What changed

This pass redesigned Command Card from a rough debug dashboard into a tabbed daily operating dashboard.

The work is intentionally frontend-heavy. Backend planning and quiz selection behavior were preserved except for small UI support around daily check-ins.

## Files changed

- `frontend/src/main.tsx`
  - Replaced the single debug-style view with a tabbed React app shell.
  - Added tabs: Today, Quiz, Tasks, Targets, Notes, Settings.
  - Added reusable local components in the same file: `Button`, `Card`, `Badge`, `ProgressBar`, `SegmentedControl`, `EmptyState`, `SectionHeader`.
  - Added Today command card, daily setup, work task input, training selection, quiz mini-card, and admin quick-add.
  - Added focused quiz flow with answer reveal, grading, progress, and simple keyboard grading.
  - Reworked tasks into Work, Admin, Training, and Missed/Recent sections.
  - Reworked Goals concept into Targets grouped as Active Core, Maintenance, and Exploration / Optional.
  - Reworked Notes into a 3-step source note -> fact review -> question generation flow.
  - Moved API URL/app password controls into Settings.

- `frontend/src/styles.css`
  - Replaced the minimal CSS with the app shell, responsive card layout, mobile tab wrapping, buttons, badges, progress bars, compact task rows, target cards, fact cards, and quiz styling.
  - Kept design simple: max-width app shell, soft borders, subtle shadows, 8px cards/buttons, mobile stacking, no decorative complexity.

- `backend/app/main.py`
  - Added `GET /api/checkin?date=YYYY-MM-DD` so the frontend can reload and display the latest saved check-in for a date.
  - Existing endpoints and behavior were otherwise preserved.

- `backend/app/services/planner.py`
  - Planner now reads the latest check-in row for the date instead of the first row, so repeated daily setup saves use the most recent state.

## Verification run

Commands run successfully:

```bash
cd frontend
npm install
npm run build
```

```bash
cd backend
python3 -m pip install --user --break-system-packages -e '.[dev]'
python3 -m pytest
```

Result: backend tests passed, `8 passed`.

`git diff --check` also passed.

Note: this environment did not have `python3-venv` or `pip` initially. `python3 -m venv` failed because `ensurepip` was missing, and sudo required a password. I installed pip user-local with `get-pip.py --user --break-system-packages` to run tests.

## Local preview used

I tested with a throwaway SQLite DB:

```bash
rm -f /tmp/command_card_dev.db
APP_PASSWORD=change-me DATABASE_URL=sqlite:////tmp/command_card_dev.db python3 seed.py
APP_PASSWORD=change-me DATABASE_URL=sqlite:////tmp/command_card_dev.db python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
VITE_API_URL=http://localhost:8000 VITE_APP_PASSWORD=change-me npm run dev -- --host 0.0.0.0 --port 5173
```

## Vercel deploy status

I attempted:

```bash
npx vercel --prod --yes
```

Deploy did not complete because the local Vercel CLI has no valid usable credentials:

```text
Error: The specified token is not valid. Use `vercel login` to generate a new token.
```

`npx vercel whoami` started an OAuth device login flow, which I stopped. Next session needs a valid Vercel login/token before deploying.

## Known limitations

- The current backend does not expose DDIA chapter filters, so Settings shows this as unavailable.
- Daily quiz size defaults are planner-controlled only; no frontend override exists yet.
- Target progress is computed client-side from done tasks because there is no target progress summary endpoint.
- Quiz "why this appeared" is inferred from available data. The backend does not return exact selection reasons.
- Question/topic/source metadata is assembled client-side from existing endpoints where possible.
- The frontend is still a single `main.tsx` file. It has reusable component functions, but it has not been split into multiple modules yet.

## Good next steps

- Split `frontend/src/main.tsx` into small page/component files if the app keeps growing.
- Add a backend target progress endpoint if target accuracy matters.
- Add a richer quiz selection response with topic/source/reason metadata.
- Add first-class training logs if training should be more than manual calendar events/tasks.
- Add Vercel credentials and deploy once auth is fixed.

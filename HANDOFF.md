# Command Card Handoff

Last updated: 2026-05-26

## Production

- Frontend: https://arjunsheep.vercel.app
- Backend: https://arjunsheep-api.fly.dev
- Current app password: `Galloran@1234`
- Production branch: `main`
- Latest deployed change: `Keep command card date manual and carry missed tasks`

Security note: the app password is intentionally static because the user requested it for now. Treat it as a convenience password, not real security. Rotate later if this app becomes less private.

## Repo / Branch State

Local working branch used by Codex:

```bash
codex/build-mvp-for-personal-development-webapp-0t7xfa
```

It is ahead/behind its old feature-branch upstream, but deployments have been pushed with:

```bash
git push origin HEAD:main
```

Recent commits:

```text
Keep command card date manual and carry missed tasks
Add API coverage and harden task writes
Add admin priority points and task deletion
af426d0 Show all work tasks on command card
c081714 Make daily quiz fixed and simplify command card
fdf9afd Show daily commitments and prioritize work tasks
2783184 Coerce check-in dates before Postgres queries
```

## Current Product Shape

Visible tabs:

- Today
- Quiz
- Tasks
- Targets
- Settings

Notes tab was removed from the frontend. Backend note/fact/source endpoints still exist because quiz source backing and future imports still depend on those concepts.

## Today Tab Rules

The main Daily Command Card is now an ordered checklist, not a wordy focus card.

Order is:

1. All planned work tasks, in user-defined priority order.
2. Standalone planner focus, such as DDIA, if it is not already represented by a task.
3. Daily quiz.
4. Chinese class event, if marked in setup.
5. Planned admin tasks.
6. Training events.
7. Social commitment event, if marked in setup.

Important behavior:

- Every planned work task appears on the card. The old work-task target no longer limits card display.
- Task rows on the card have `Done`, `Missed`, and `Skip`.
- The command card date is manually controlled and stored in local storage. It does not roll over at midnight; use the date control / "Use today" button to start a new card.
- Marking a task `Done` completes it. Marking it `Missed` leaves it incomplete; missed tasks from earlier card dates carry onto later cards.
- The standalone focus row also has `Done`, `Missed`, and `Skip`; it records a one-off focus task.
- Work tasks are still reordered with up/down arrows in the Work task panel and Tasks tab.
- Task rows can be deleted from the Tasks tab via the trash icon. This calls `DELETE /api/tasks/{id}`.
- Admin tasks use 1-5 priority points instead of arrows and are sorted highest priority first.
- The backend also clamps task `priority_points` to 1-5 and coerces task dates / calendar datetimes before writing, so direct API calls behave like the frontend.

## Daily Setup

Daily setup now saves:

- Sleep: bad / meh / good
- Soreness: low / medium / high
- Work pressure: low / medium / high
- Training today: none / BJJ / lifting / both / other
- Chinese class today: no / yes
- Social commitment today: no / yes

Implementation detail:

- Training, Chinese class, and social commitment are represented as manual calendar events so planner day classification can use existing calendar logic.
- Backend now has `DELETE /api/calendar/events/{id}` so toggling Chinese/social back to `No` can remove those auto-created manual events.

## Quiz Rules

Daily quiz is fixed:

- 10 DDIA questions
- 10 Chinese questions

Backend selector:

- `backend/app/services/quiz.py`
- Excludes BJJ questions.
- Respects the DDIA chapter filter.
- Ranks within each topic using due date, weakness, topic priority, current focus bonus, and small randomness.
- Falls back to generic ranking only if there are no DDIA/Chinese target-topic questions available.

Planner now records:

```json
{"count": 20, "topics": {"DDIA": 10, "Chinese": 10}}
```

DDIA chapter selection moved to the Quiz tab. Settings only summarizes the current chapter filter.

Live verification after deploy showed:

```text
DDIA    10
Chinese 10
```

## Targets Tab

Targets tab now supports:

- Add topic
- Pick category for any topic
- Pick priority 1-5
- Add or update weekly target for any existing topic
- Target types: blocks, minutes, questions, sessions, binary

Topics are bucketed by category:

- Professional
- Study
- Training
- Admin
- Creative
- Social
- Health
- Other

Current category display changes already in place:

- `language` displays as `Study`.
- Meditation is under Study in production seed/data from prior work.
- Meal prep is under Admin.
- Bidet reviews is under Creative.

## Deploy Commands

Backend:

```powershell
cd C:\Users\megab\Documents\Codex\2026-05-17\prior-conversation-with-codex-conversation-role\sheep\backend
C:\Users\megab\.fly\bin\flyctl.exe deploy
```

Frontend:

```powershell
cd C:\Users\megab\Documents\Codex\2026-05-17\prior-conversation-with-codex-conversation-role\sheep
C:\Users\megab\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe C:\Users\megab\Documents\Codex\2026-05-18\files-mentioned-by-the-user-ddia2\.tooling\vercel-cli\node_modules\vercel\dist\vc.js --prod --yes
```

The regular `vercel.cmd` path produced `Access is denied`; running Vercel through the bundled Node executable works.

## Verification Commands

Backend tests:

```powershell
cd C:\Users\megab\Documents\Codex\2026-05-17\prior-conversation-with-codex-conversation-role\sheep\backend
.\.venv\Scripts\python.exe -m pytest
```

Last result:

```text
33 passed
```

The suite now includes route-level FastAPI tests in `backend/tests/test_api.py` for password protection, task priority persistence/clamping, task deletion, task date filtering, missed-task incompleteness, daily settings, check-in upsert behavior, DDIA chapter settings, calendar event deletion, MCQ import, and generated plan persistence.

Frontend build:

```powershell
cd C:\Users\megab\Documents\Codex\2026-05-17\prior-conversation-with-codex-conversation-role\sheep\frontend
C:\Users\megab\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe node_modules\vite\bin\vite.js build
```

Last result: Vite production build succeeded.

Live backend health:

```powershell
Invoke-RestMethod -Uri https://arjunsheep-api.fly.dev/healthz
```

Live quiz mix:

```powershell
$headers=@{'x-app-password'='Galloran@1234'}
$topics=Invoke-RestMethod -Headers $headers -Uri 'https://arjunsheep-api.fly.dev/api/topics'
$topicById=@{}
foreach ($t in $topics) { $topicById[[int]$t.id]=$t.name }
$quiz=Invoke-RestMethod -Headers $headers -Uri 'https://arjunsheep-api.fly.dev/api/quiz/today?date=2026-05-24'
$quiz | Group-Object { $topicById[[int]$_.topic_id] } | Select-Object Name,Count
```

## Useful User Context

User prefers calm, patient iteration. They explicitly said they were high during the latest UI review, so avoid terse or brittle explanations.

Recent requested product direction:

- The app should reduce decisions.
- The main card should be the actual ordered list of things to do today.
- Mentally strenuous tasks first.
- Admin/lifting/social later.
- Daily quiz commitment is fine: always DDIA 10 + Chinese 10.
- BJJ quizzing is out.
- Work tasks should be reorderable and all planned work tasks should appear on the card.
- Card task rows should be actionable with Done/Missed/Skip.

## Known Follow-Ups

- The old daily `work_task_target` setting still exists in backend daily settings, but it no longer limits the Today card. It is mostly legacy UI state now.
- Training/social/Chinese event times are defaults. If the user wants exact times, add editable event times later.
- The frontend is still a large single `frontend/src/main.tsx`; splitting it up would help if the app grows.
- The Chinese imported text appears mojibake in some PowerShell JSON output, but the app/browser may still render from stored DB values. Check actual UI before assuming data corruption.

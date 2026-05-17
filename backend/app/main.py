from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Header
from sqlmodel import Session, select
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db, get_session
from app.models import *
from app.services.planner import generate_plan
from app.services.quiz import select_today_questions, apply_review
from app.adapters.llm import get_llm
from app.core.config import settings

app = FastAPI(title="Command Card")
origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins if origins else ["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    init_db()


@app.get('/healthz')
def healthz():
    return {"ok": True}


def require_password(x_app_password: str = Header(default="")):
    if x_app_password != settings.app_password:
        raise HTTPException(status_code=401, detail="Unauthorized")


for name, model in [("topics", Topic), ("weekly-targets", WeeklyTarget), ("sources", Source), ("questions", Question)]:
    @app.get(f"/api/{name}", dependencies=[Depends(require_password)])
    def list_items(session: Session = Depends(get_session), _m=model): return session.exec(select(_m)).all()


@app.post('/api/topics', dependencies=[Depends(require_password)])
def create_topic(t: Topic, session: Session = Depends(get_session)): session.add(t); session.commit(); session.refresh(t); return t


@app.patch('/api/topics/{item_id}', dependencies=[Depends(require_password)])
def patch_topic(item_id: int, patch: dict, session: Session = Depends(get_session)):
    t = session.get(Topic, item_id); [setattr(t, k, v) for k, v in patch.items()]; session.add(t); session.commit(); return t


@app.post('/api/weekly-targets', dependencies=[Depends(require_password)])
def create_wt(x: WeeklyTarget, session: Session = Depends(get_session)): session.add(x); session.commit(); session.refresh(x); return x


@app.patch('/api/weekly-targets/{item_id}', dependencies=[Depends(require_password)])
def patch_wt(item_id: int, patch: dict, session: Session = Depends(get_session)):
    x = session.get(WeeklyTarget, item_id); [setattr(x, k, v) for k, v in patch.items()]; session.add(x); session.commit(); return x


@app.get('/api/tasks', dependencies=[Depends(require_password)])
def list_tasks(date: str | None = None, session: Session = Depends(get_session)):
    q = select(Task)
    if date: q = q.where(Task.scheduled_date == datetime.strptime(date, '%Y-%m-%d').date())
    return session.exec(q).all()


@app.post('/api/tasks', dependencies=[Depends(require_password)])
def create_task(t: Task, session: Session = Depends(get_session)): session.add(t); session.commit(); session.refresh(t); return t


@app.patch('/api/tasks/{item_id}', dependencies=[Depends(require_password)])
def patch_task(item_id: int, patch: dict, session: Session = Depends(get_session)):
    t = session.get(Task, item_id); [setattr(t, k, v) for k, v in patch.items()]; session.add(t); session.commit(); return t


@app.post('/api/tasks/{item_id}/complete', dependencies=[Depends(require_password)])
def complete_task(item_id: int, session: Session = Depends(get_session)):
    t = session.get(Task, item_id); t.status = TaskStatus.done; t.completed_at = datetime.utcnow(); session.add(t); session.commit(); return t


@app.post('/api/tasks/{item_id}/miss', dependencies=[Depends(require_password)])
def miss_task(item_id: int, session: Session = Depends(get_session)):
    t = session.get(Task, item_id); t.status = TaskStatus.missed; session.add(t); session.commit(); return t


@app.post('/api/sources', dependencies=[Depends(require_password)])
def create_source(s: Source, session: Session = Depends(get_session)): session.add(s); session.commit(); session.refresh(s); return s


@app.post('/api/sources/{item_id}/extract-facts', dependencies=[Depends(require_password)])
def extract_facts(item_id: int, session: Session = Depends(get_session)):
    src = session.get(Source, item_id); llm = get_llm(); facts = llm.extract_facts(src.raw_text)
    rows = []
    for f in facts:
        af = AtomicFact(source_id=src.id, topic_id=src.topic_id, fact_text=f.fact_text, explanation=f.explanation, tags=f.tags)
        session.add(af); rows.append(af)
    session.commit(); return rows


@app.get('/api/facts', dependencies=[Depends(require_password)])
def list_facts(status: FactStatus | None = None, session: Session = Depends(get_session)):
    q = select(AtomicFact)
    if status: q = q.where(AtomicFact.status == status)
    return session.exec(q).all()


@app.patch('/api/facts/{item_id}', dependencies=[Depends(require_password)])
def patch_fact(item_id: int, patch: dict, session: Session = Depends(get_session)):
    f = session.get(AtomicFact, item_id); [setattr(f, k, v) for k, v in patch.items()]; session.add(f); session.commit(); return f


@app.post('/api/facts/{item_id}/approve', dependencies=[Depends(require_password)])
def approve_fact(item_id: int, session: Session = Depends(get_session)): f = session.get(AtomicFact, item_id); f.status = FactStatus.approved; session.add(f); session.commit(); return f


@app.post('/api/facts/{item_id}/reject', dependencies=[Depends(require_password)])
def reject_fact(item_id: int, session: Session = Depends(get_session)): f = session.get(AtomicFact, item_id); f.status = FactStatus.rejected; session.add(f); session.commit(); return f


@app.post('/api/facts/{item_id}/generate-questions', dependencies=[Depends(require_password)])
def gen_q(item_id: int, session: Session = Depends(get_session)):
    f = session.get(AtomicFact, item_id)
    if f.status != FactStatus.approved: raise HTTPException(400, "Fact must be approved")
    llm = get_llm(); qs = llm.generate_questions(f.fact_text, f.explanation); out = []
    for q in qs:
        row = Question(fact_id=f.id, topic_id=f.topic_id, prompt=q.prompt, correct_answer=q.correct_answer, acceptable_answers=q.acceptable_answers, explanation=q.explanation)
        session.add(row); out.append(row)
    session.commit(); return out


@app.get('/api/quiz/today', dependencies=[Depends(require_password)])
def quiz_today(date: str, session: Session = Depends(get_session)): return select_today_questions(session, datetime.strptime(date, '%Y-%m-%d').date())


@app.post('/api/quiz/review', dependencies=[Depends(require_password)])
def quiz_review(payload: dict, session: Session = Depends(get_session)):
    q = session.get(Question, payload['question_id']); llm = get_llm(); grading = llm.grade(payload.get('user_answer', ''), q.correct_answer)
    r, cs = apply_review(session, payload['question_id'], payload.get('user_answer', ''), Grade(payload['grade']), payload.get('is_correct', grading['is_correct']), grading['feedback'])
    return {"review": r, "card_state": cs, "llm_feedback": grading}


@app.post('/api/checkin', dependencies=[Depends(require_password)])
def checkin(c: DailyCheckIn, session: Session = Depends(get_session)): session.add(c); session.commit(); session.refresh(c); return c


@app.get('/api/plan/today', dependencies=[Depends(require_password)])
def today_plan(date: str, session: Session = Depends(get_session)):
    d = datetime.strptime(date, '%Y-%m-%d').date(); p = session.exec(select(DailyPlan).where(DailyPlan.date == d).order_by(DailyPlan.generated_at.desc())).first(); return p


@app.post('/api/plan/generate', dependencies=[Depends(require_password)])
def gen_plan(date: str, session: Session = Depends(get_session)): return generate_plan(session, datetime.strptime(date, '%Y-%m-%d').date())


@app.post('/api/calendar/events/manual', dependencies=[Depends(require_password)])
def add_event(e: CalendarEvent, session: Session = Depends(get_session)): session.add(e); session.commit(); session.refresh(e); return e


@app.get('/api/calendar/events', dependencies=[Depends(require_password)])
def events(date: str, session: Session = Depends(get_session)):
    d = datetime.strptime(date, '%Y-%m-%d'); return session.exec(select(CalendarEvent).where(CalendarEvent.start_at >= d, CalendarEvent.start_at < d.replace(hour=0) + __import__('datetime').timedelta(days=1))).all()

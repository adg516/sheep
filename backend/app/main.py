from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.adapters.llm import get_llm
from app.core.config import settings
from app.db import get_session, init_db
from app.models import *
from app.services.planner import generate_plan
from app.services.quiz import apply_review, select_today_questions


app = FastAPI(title="Command Card")

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/healthz")
def healthz():
    return {"ok": True}


def require_password(x_app_password: str = Header(default="")):
    if x_app_password != settings.app_password:
        raise HTTPException(status_code=401, detail="Unauthorized")


api_auth = [Depends(require_password)]


for name, model in [
    ("topics", Topic),
    ("weekly-targets", WeeklyTarget),
    ("sources", Source),
    ("questions", Question),
]:

    @app.get(f"/api/{name}", dependencies=api_auth)
    def list_items(session: Session = Depends(get_session), _m=model):
        return session.exec(select(_m)).all()


@app.post("/api/topics", dependencies=api_auth)
def create_topic(topic: Topic, session: Session = Depends(get_session)):
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


@app.patch("/api/topics/{item_id}", dependencies=api_auth)
def patch_topic(item_id: int, patch: dict, session: Session = Depends(get_session)):
    topic = session.get(Topic, item_id)
    for key, value in patch.items():
        setattr(topic, key, value)
    session.add(topic)
    session.commit()
    return topic


@app.post("/api/weekly-targets", dependencies=api_auth)
def create_weekly_target(target: WeeklyTarget, session: Session = Depends(get_session)):
    session.add(target)
    session.commit()
    session.refresh(target)
    return target


@app.patch("/api/weekly-targets/{item_id}", dependencies=api_auth)
def patch_weekly_target(item_id: int, patch: dict, session: Session = Depends(get_session)):
    target = session.get(WeeklyTarget, item_id)
    for key, value in patch.items():
        setattr(target, key, value)
    session.add(target)
    session.commit()
    return target


@app.get("/api/tasks", dependencies=api_auth)
def list_tasks(date: str | None = None, session: Session = Depends(get_session)):
    query = select(Task)
    if date:
        query = query.where(Task.scheduled_date == datetime.strptime(date, "%Y-%m-%d").date())
    return session.exec(query).all()


@app.post("/api/tasks", dependencies=api_auth)
def create_task(task: Task, session: Session = Depends(get_session)):
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/api/tasks/{item_id}", dependencies=api_auth)
def patch_task(item_id: int, patch: dict, session: Session = Depends(get_session)):
    task = session.get(Task, item_id)
    for key, value in patch.items():
        setattr(task, key, value)
    session.add(task)
    session.commit()
    return task


@app.post("/api/tasks/{item_id}/complete", dependencies=api_auth)
def complete_task(item_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, item_id)
    task.status = TaskStatus.done
    task.completed_at = datetime.utcnow()
    session.add(task)
    session.commit()
    return task


@app.post("/api/tasks/{item_id}/miss", dependencies=api_auth)
def miss_task(item_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, item_id)
    task.status = TaskStatus.missed
    session.add(task)
    session.commit()
    return task


@app.post("/api/sources", dependencies=api_auth)
def create_source(source: Source, session: Session = Depends(get_session)):
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


@app.post("/api/sources/{item_id}/extract-facts", dependencies=api_auth)
def extract_facts(item_id: int, session: Session = Depends(get_session)):
    source = session.get(Source, item_id)
    facts = get_llm().extract_facts(source.raw_text)
    rows = []
    for fact in facts:
        row = AtomicFact(
            source_id=source.id,
            topic_id=source.topic_id,
            fact_text=fact.fact_text,
            explanation=fact.explanation,
            tags=fact.tags,
        )
        session.add(row)
        rows.append(row)
    session.commit()
    return rows


@app.get("/api/facts", dependencies=api_auth)
def list_facts(status: FactStatus | None = None, session: Session = Depends(get_session)):
    query = select(AtomicFact)
    if status:
        query = query.where(AtomicFact.status == status)
    return session.exec(query).all()


@app.patch("/api/facts/{item_id}", dependencies=api_auth)
def patch_fact(item_id: int, patch: dict, session: Session = Depends(get_session)):
    fact = session.get(AtomicFact, item_id)
    for key, value in patch.items():
        setattr(fact, key, value)
    session.add(fact)
    session.commit()
    return fact


@app.post("/api/facts/{item_id}/approve", dependencies=api_auth)
def approve_fact(item_id: int, session: Session = Depends(get_session)):
    fact = session.get(AtomicFact, item_id)
    fact.status = FactStatus.approved
    session.add(fact)
    session.commit()
    return fact


@app.post("/api/facts/{item_id}/reject", dependencies=api_auth)
def reject_fact(item_id: int, session: Session = Depends(get_session)):
    fact = session.get(AtomicFact, item_id)
    fact.status = FactStatus.rejected
    session.add(fact)
    session.commit()
    return fact


@app.post("/api/facts/{item_id}/generate-questions", dependencies=api_auth)
def generate_questions(item_id: int, session: Session = Depends(get_session)):
    fact = session.get(AtomicFact, item_id)
    if fact.status != FactStatus.approved:
        raise HTTPException(status_code=400, detail="Fact must be approved")

    questions = get_llm().generate_questions(fact.fact_text, fact.explanation)
    rows = []
    for question in questions:
        row = Question(
            fact_id=fact.id,
            topic_id=fact.topic_id,
            prompt=question.prompt,
            correct_answer=question.correct_answer,
            acceptable_answers=question.acceptable_answers,
            explanation=question.explanation,
        )
        session.add(row)
        rows.append(row)
    session.commit()
    return rows


@app.get("/api/quiz/today", dependencies=api_auth)
def quiz_today(date: str, session: Session = Depends(get_session)):
    return select_today_questions(session, datetime.strptime(date, "%Y-%m-%d").date())


@app.post("/api/quiz/review", dependencies=api_auth)
def quiz_review(payload: dict, session: Session = Depends(get_session)):
    question = session.get(Question, payload["question_id"])
    grading = get_llm().grade(payload.get("user_answer", ""), question.correct_answer)
    review, card_state = apply_review(
        session,
        payload["question_id"],
        payload.get("user_answer", ""),
        Grade(payload["grade"]),
        payload.get("is_correct", grading["is_correct"]),
        grading["feedback"],
    )
    return {"review": review, "card_state": card_state, "llm_feedback": grading}


@app.post("/api/checkin", dependencies=api_auth)
def checkin(checkin: DailyCheckIn, session: Session = Depends(get_session)):
    session.add(checkin)
    session.commit()
    session.refresh(checkin)
    return checkin


@app.get("/api/checkin", dependencies=api_auth)
def get_checkin(date: str, session: Session = Depends(get_session)):
    checkin_date = datetime.strptime(date, "%Y-%m-%d").date()
    return session.exec(
        select(DailyCheckIn)
        .where(DailyCheckIn.date == checkin_date)
        .order_by(DailyCheckIn.id.desc())
    ).first()


@app.get("/api/plan/today", dependencies=api_auth)
def today_plan(date: str, session: Session = Depends(get_session)):
    plan_date = datetime.strptime(date, "%Y-%m-%d").date()
    return session.exec(
        select(DailyPlan)
        .where(DailyPlan.date == plan_date)
        .order_by(DailyPlan.generated_at.desc())
    ).first()


@app.post("/api/plan/generate", dependencies=api_auth)
def generate_today_plan(date: str, session: Session = Depends(get_session)):
    return generate_plan(session, datetime.strptime(date, "%Y-%m-%d").date())


@app.post("/api/calendar/events/manual", dependencies=api_auth)
def add_event(event: CalendarEvent, session: Session = Depends(get_session)):
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@app.get("/api/calendar/events", dependencies=api_auth)
def events(date: str, session: Session = Depends(get_session)):
    start = datetime.strptime(date, "%Y-%m-%d")
    end = start.replace(hour=0) + timedelta(days=1)
    return session.exec(
        select(CalendarEvent).where(CalendarEvent.start_at >= start, CalendarEvent.start_at < end)
    ).all()

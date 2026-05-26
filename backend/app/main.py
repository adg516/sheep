from datetime import date as date_type, datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from app.adapters.llm import get_llm
from app.core.config import settings
from app.db import get_session, init_db
from app.models import *
from app.services.import_mcq import import_mcq_jsonl_text
from app.services.planner import generate_plan
from app.services.quiz import DDIA_CHAPTER_SETTING_KEY, apply_review, select_today_questions


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


class ImportJsonlPayload(BaseModel):
    text: str
    topic_name: str = "Chinese"
    source_title: str = "Imported MCQ JSONL"
    source_ref: str = "api-import"
    update_existing: bool = True


class DdiaChaptersPayload(BaseModel):
    chapters: list[int] = []


class DailySettingsPayload(BaseModel):
    date: str
    work_task_target: int = 1


def available_ddia_chapters(session: Session) -> list[int]:
    topic = session.exec(select(Topic).where(Topic.name == "DDIA")).first()
    if not topic:
        return []
    questions = session.exec(
        select(Question).where(Question.topic_id == topic.id, Question.active == True)
    ).all()
    chapters = set()
    for question in questions:
        raw_chapter = (question.metadata_json or {}).get("chapter")
        try:
            chapters.add(int(raw_chapter))
        except (TypeError, ValueError):
            continue
    return sorted(chapters)


def get_ddia_chapter_setting(session: Session) -> dict:
    setting = session.get(AppSetting, DDIA_CHAPTER_SETTING_KEY)
    selected = (setting.value or {}).get("chapters", []) if setting else []
    return {
        "chapters": sorted({int(chapter) for chapter in selected if str(chapter).isdigit()}),
        "available_chapters": available_ddia_chapters(session),
    }


def coerce_ymd_date(value) -> date_type:
    if isinstance(value, date_type):
        return value
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    raise ValueError("Expected date in YYYY-MM-DD format")


def coerce_optional_ymd_date(value):
    if value is None:
        return None
    return coerce_ymd_date(value)


def coerce_iso_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError("Expected datetime in ISO format")


def daily_settings_key(on_date: date_type) -> str:
    return f"daily_settings:{on_date.isoformat()}"


def daily_settings_payload(session: Session, on_date: date_type) -> dict:
    setting = session.get(AppSetting, daily_settings_key(on_date))
    value = setting.value if setting else {}
    return {
        "date": on_date.isoformat(),
        "work_task_target": max(0, min(6, int(value.get("work_task_target", 1)))),
    }


def clamp_priority_points(value) -> int:
    return max(1, min(5, int(3 if value is None else value)))


for name, model in [
    ("topics", Topic),
    ("weekly-targets", WeeklyTarget),
    ("sources", Source),
    ("questions", Question),
    ("admin-items", AdminItem),
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


@app.post("/api/admin-items", dependencies=api_auth)
def create_admin_item(item: AdminItem, session: Session = Depends(get_session)):
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.patch("/api/admin-items/{item_id}", dependencies=api_auth)
def patch_admin_item(item_id: int, patch: dict, session: Session = Depends(get_session)):
    item = session.get(AdminItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Admin item not found")
    for key, value in patch.items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    return item


@app.get("/api/tasks", dependencies=api_auth)
def list_tasks(date: str | None = None, session: Session = Depends(get_session)):
    query = select(Task)
    if date:
        query = query.where(Task.scheduled_date == datetime.strptime(date, "%Y-%m-%d").date())
    return session.exec(query).all()


@app.post("/api/tasks", dependencies=api_auth)
def create_task(task: Task, session: Session = Depends(get_session)):
    try:
        task.scheduled_date = coerce_optional_ymd_date(task.scheduled_date)
        task.priority_points = clamp_priority_points(task.priority_points)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.patch("/api/tasks/{item_id}", dependencies=api_auth)
def patch_task(item_id: int, patch: dict, session: Session = Depends(get_session)):
    task = session.get(Task, item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        for key, value in patch.items():
            if key == "priority_points":
                value = clamp_priority_points(value)
            if key == "scheduled_date":
                value = coerce_optional_ymd_date(value)
            setattr(task, key, value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@app.delete("/api/tasks/{item_id}", dependencies=api_auth)
def delete_task(item_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, item_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()
    return {"ok": True}


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


@app.get("/api/settings/ddia-chapters", dependencies=api_auth)
def ddia_chapter_settings(session: Session = Depends(get_session)):
    return get_ddia_chapter_setting(session)


@app.patch("/api/settings/ddia-chapters", dependencies=api_auth)
def update_ddia_chapter_settings(payload: DdiaChaptersPayload, session: Session = Depends(get_session)):
    available = set(available_ddia_chapters(session))
    chapters = sorted({
        int(chapter)
        for chapter in payload.chapters
        if int(chapter) > 0 and (not available or int(chapter) in available)
    })
    setting = session.get(AppSetting, DDIA_CHAPTER_SETTING_KEY) or AppSetting(key=DDIA_CHAPTER_SETTING_KEY)
    setting.value = {"chapters": chapters}
    setting.updated_at = datetime.utcnow()
    session.add(setting)
    session.commit()
    return get_ddia_chapter_setting(session)


@app.get("/api/settings/daily", dependencies=api_auth)
def daily_settings(date: str, session: Session = Depends(get_session)):
    try:
        settings_date = coerce_ymd_date(date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return daily_settings_payload(session, settings_date)


@app.patch("/api/settings/daily", dependencies=api_auth)
def update_daily_settings(payload: DailySettingsPayload, session: Session = Depends(get_session)):
    try:
        settings_date = coerce_ymd_date(payload.date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    target = max(0, min(6, int(payload.work_task_target)))
    setting = session.get(AppSetting, daily_settings_key(settings_date)) or AppSetting(
        key=daily_settings_key(settings_date)
    )
    setting.value = {"work_task_target": target}
    setting.updated_at = datetime.utcnow()
    session.add(setting)
    session.commit()
    return daily_settings_payload(session, settings_date)


@app.post("/api/import/mcq-jsonl", dependencies=api_auth)
def import_mcq_jsonl(payload: ImportJsonlPayload, session: Session = Depends(get_session)):
    try:
        summary = import_mcq_jsonl_text(
            session,
            payload.text,
            topic_name=payload.topic_name,
            source_title=payload.source_title,
            source_ref=payload.source_ref,
            update_existing=payload.update_existing,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return summary


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
    try:
        checkin_date = coerce_ymd_date(checkin.date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    checkin.date = checkin_date
    existing = session.exec(select(DailyCheckIn).where(DailyCheckIn.date == checkin_date)).first()
    if existing:
        existing.sleep_quality = checkin.sleep_quality
        existing.soreness = checkin.soreness
        existing.work_pressure = checkin.work_pressure
        existing.notes = checkin.notes
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
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
    try:
        event.start_at = coerce_iso_datetime(event.start_at)
        event.end_at = coerce_iso_datetime(event.end_at)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@app.delete("/api/calendar/events/{item_id}", dependencies=api_auth)
def delete_event(item_id: int, session: Session = Depends(get_session)):
    event = session.get(CalendarEvent, item_id)
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    session.delete(event)
    session.commit()
    return {"ok": True}


@app.get("/api/calendar/events", dependencies=api_auth)
def events(date: str, session: Session = Depends(get_session)):
    start = datetime.strptime(date, "%Y-%m-%d")
    end = start.replace(hour=0) + timedelta(days=1)
    return session.exec(
        select(CalendarEvent).where(CalendarEvent.start_at >= start, CalendarEvent.start_at < end)
    ).all()

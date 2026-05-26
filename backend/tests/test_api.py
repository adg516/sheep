from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app.core.config import settings
from app.main import app, get_session
from app.models import (
    AppSetting,
    AtomicFact,
    DailyCheckIn,
    FactStatus,
    Question,
    QuestionType,
    Source,
    SourceType,
    Topic,
    TopicCategory,
)
from app.services.quiz import DDIA_CHAPTER_SETTING_KEY


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def client(session):
    def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers():
    return {"x-app-password": settings.app_password}


def test_health_does_not_require_password(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_api_routes_require_password(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers={"x-app-password": "wrong"}).status_code == 401


def test_create_task_persists_admin_priority_points(client, auth_headers):
    response = client.post(
        "/api/tasks",
        headers=auth_headers,
        json={
            "title": "Pay dentist bill",
            "description": "admin_task",
            "scheduled_date": "2026-05-25",
            "priority_points": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Pay dentist bill"
    assert body["priority_points"] == 5

    listed = client.get("/api/tasks?date=2026-05-25", headers=auth_headers).json()
    assert [task["priority_points"] for task in listed] == [5]


def test_task_priority_points_are_clamped_on_create_and_patch(client, auth_headers):
    low = client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"title": "Low clamp", "description": "admin_task", "priority_points": 0},
    ).json()
    high = client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"title": "High clamp", "description": "admin_task", "priority_points": 99},
    ).json()

    assert low["priority_points"] == 1
    assert high["priority_points"] == 5

    patched = client.patch(
        f"/api/tasks/{low['id']}",
        headers=auth_headers,
        json={"priority_points": 12},
    ).json()
    assert patched["priority_points"] == 5


def test_delete_task_removes_it_from_task_list(client, auth_headers):
    created = client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"title": "Duplicate cleanup", "scheduled_date": "2026-05-25"},
    ).json()

    response = client.delete(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert client.delete(f"/api/tasks/{created['id']}", headers=auth_headers).status_code == 404
    assert client.get("/api/tasks?date=2026-05-25", headers=auth_headers).json() == []


def test_task_date_filter_keeps_sessions_separate(client, auth_headers):
    client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"title": "Today", "scheduled_date": "2026-05-25"},
    )
    client.post(
        "/api/tasks",
        headers=auth_headers,
        json={"title": "Tomorrow", "scheduled_date": "2026-05-26"},
    )

    listed = client.get("/api/tasks?date=2026-05-25", headers=auth_headers).json()
    assert [task["title"] for task in listed] == ["Today"]


def test_daily_settings_clamps_work_task_target(client, auth_headers):
    too_high = client.patch(
        "/api/settings/daily",
        headers=auth_headers,
        json={"date": "2026-05-25", "work_task_target": 100},
    ).json()
    too_low = client.patch(
        "/api/settings/daily",
        headers=auth_headers,
        json={"date": "2026-05-26", "work_task_target": -4},
    ).json()

    assert too_high["work_task_target"] == 6
    assert too_low["work_task_target"] == 0


def test_checkin_upserts_same_day_instead_of_duplicating(client, auth_headers, session):
    payload = {
        "date": "2026-05-25",
        "sleep_quality": "bad",
        "soreness": "high",
        "work_pressure": "high",
        "notes": "rough",
    }
    first = client.post("/api/checkin", headers=auth_headers, json=payload).json()
    second = client.post(
        "/api/checkin",
        headers=auth_headers,
        json={**payload, "sleep_quality": "good", "notes": "better"},
    ).json()

    assert first["id"] == second["id"]
    assert second["sleep_quality"] == "good"
    assert session.exec(select(DailyCheckIn)).all()[0].notes == "better"
    assert len(session.exec(select(DailyCheckIn)).all()) == 1


def test_ddia_chapter_settings_only_keep_available_chapters(client, auth_headers, session):
    ddia = Topic(name="DDIA", category=TopicCategory.professional, priority_weight=5)
    session.add(ddia)
    session.commit()
    session.refresh(ddia)
    source = Source(topic_id=ddia.id, title="DDIA", source_type=SourceType.book_notes, raw_text="raw")
    session.add(source)
    session.commit()
    session.refresh(source)
    fact = AtomicFact(
        source_id=source.id,
        topic_id=ddia.id,
        fact_text="chapter fact",
        explanation="source backed",
        status=FactStatus.approved,
    )
    session.add(fact)
    session.commit()
    session.refresh(fact)
    session.add(
        Question(
            fact_id=fact.id,
            topic_id=ddia.id,
            question_type=QuestionType.multiple_choice,
            prompt="Ch 2 question",
            correct_answer="answer",
            acceptable_answers=["answer"],
            metadata_json={"chapter": 2},
            explanation="source backed",
        )
    )
    session.commit()

    response = client.patch(
        "/api/settings/ddia-chapters",
        headers=auth_headers,
        json={"chapters": [2, 99, -1]},
    )

    assert response.status_code == 200
    assert response.json()["chapters"] == [2]
    saved = session.get(AppSetting, DDIA_CHAPTER_SETTING_KEY)
    assert saved.value == {"chapters": [2]}


def test_manual_calendar_event_can_be_deleted(client, auth_headers):
    start = datetime(2026, 5, 25, 19, 0)
    created = client.post(
        "/api/calendar/events/manual",
        headers=auth_headers,
        json={
            "title": "Chinese class",
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
            "source": "manual",
            "tags": ["study"],
        },
    ).json()

    assert client.delete(f"/api/calendar/events/{created['id']}", headers=auth_headers).status_code == 200
    assert client.get("/api/calendar/events?date=2026-05-25", headers=auth_headers).json() == []


def test_import_mcq_jsonl_api_creates_source_backed_question(client, auth_headers, session):
    text = "\n".join(
        [
            '{"id":"api-ddia-1","source":"DDIA","chapter":3,"question":"What is a log?","choices":["History","Cache"],"answer":"History","answer_index":0,"explanation":"A log is append-only."}'
        ]
    )
    response = client.post(
        "/api/import/mcq-jsonl",
        headers=auth_headers,
        json={"text": text, "topic_name": "DDIA", "source_title": "DDIA import"},
    )

    assert response.status_code == 200
    assert response.json()["created_questions"] == 1
    question = session.exec(select(Question)).one()
    fact = session.exec(select(AtomicFact)).one()
    assert question.external_id == "api-ddia-1"
    assert question.metadata_json["chapter"] == 3
    assert question.correct_choice == "A"
    assert fact.status == FactStatus.approved


def test_generate_plan_persists_retrievable_daily_plan(client, auth_headers, session):
    session.add(Topic(name="DDIA", category=TopicCategory.professional, priority_weight=5))
    session.commit()

    generated = client.post("/api/plan/generate?date=2026-05-25", headers=auth_headers).json()
    fetched = client.get("/api/plan/today?date=2026-05-25", headers=auth_headers).json()

    assert generated["id"] == fetched["id"]
    assert fetched["date"] == "2026-05-25"
    assert fetched["main_focus"]["topic"] == "DDIA"

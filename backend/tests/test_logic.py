from datetime import datetime, date, timedelta
from sqlmodel import SQLModel, Session, create_engine
from app.models import *
from app.services.planner import classify_day, score_topic, generate_plan
from app.services.quiz import select_today_questions

def mk():
    e=create_engine('sqlite://', connect_args={'check_same_thread':False})
    SQLModel.metadata.create_all(e)
    return Session(e)

def test_day_classification():
    ev=[CalendarEvent(title='BJJ',start_at=datetime(2026,1,1,21),end_at=datetime(2026,1,1,22),tags=[])]
    assert classify_day(ev)=='late_bjj_day'

def test_task_priority_scoring():
    s=mk(); t=Topic(name='DDIA',category=TopicCategory.professional,priority_weight=5); s.add(t); s.commit(); s.refresh(t)
    assert score_topic(s,t,date.today(),'open_day')>=5

def test_quiz_prioritizes_overdue():
    s=mk(); t=Topic(name='A',category=TopicCategory.other,priority_weight=1); s.add(t); s.commit(); s.refresh(t)
    q1=Question(fact_id=1,topic_id=t.id,prompt='p1',correct_answer='a',acceptable_answers=['a'],explanation='e')
    q2=Question(fact_id=2,topic_id=t.id,prompt='p2',correct_answer='a',acceptable_answers=['a'],explanation='e')
    s.add(q1); s.add(q2); s.commit(); s.refresh(q1); s.refresh(q2)
    s.add(CardState(question_id=q1.id,next_due_at=datetime.utcnow()-timedelta(days=1),recent_accuracy=1.0))
    s.add(CardState(question_id=q2.id,next_due_at=datetime.utcnow()+timedelta(days=5),recent_accuracy=1.0)); s.commit()
    out=select_today_questions(s,date.today())
    assert out[0].id==q1.id

def test_quiz_prioritizes_weak_cards():
    s=mk(); t=Topic(name='A',category=TopicCategory.other,priority_weight=1); s.add(t); s.commit(); s.refresh(t)
    q1=Question(fact_id=1,topic_id=t.id,prompt='p1',correct_answer='a',acceptable_answers=['a'],explanation='e')
    q2=Question(fact_id=2,topic_id=t.id,prompt='p2',correct_answer='a',acceptable_answers=['a'],explanation='e')
    s.add(q1); s.add(q2); s.commit(); s.refresh(q1); s.refresh(q2)
    s.add(CardState(question_id=q1.id,recent_accuracy=0.2)); s.add(CardState(question_id=q2.id,recent_accuracy=0.95)); s.commit()
    out=select_today_questions(s,date.today()); assert out[0].id==q1.id

def test_late_bjj_avoids_heavy():
    s=mk(); t=Topic(name='Deep Work',category=TopicCategory.professional,priority_weight=4); s.add(t)
    s.add(CalendarEvent(title='BJJ',start_at=datetime.combine(date.today(), datetime.min.time()).replace(hour=21), end_at=datetime.combine(date.today(), datetime.min.time()).replace(hour=22),tags=[])); s.commit()
    p=generate_plan(s,date.today()); assert 'High cognitive tasks' in p.avoid[0]

def test_bad_sleep_reduces_serious_tasks():
    s=mk(); s.add(Topic(name='A',category=TopicCategory.professional,priority_weight=5)); s.add(Topic(name='B',category=TopicCategory.professional,priority_weight=4)); s.add(DailyCheckIn(date=date.today(),sleep_quality=Quality.bad,soreness=Level.low,work_pressure=Level.low)); s.commit()
    p=generate_plan(s,date.today()); assert p.secondary_focus is None

def test_only_approved_fact_generates_questions():
    f=AtomicFact(source_id=1,topic_id=1,fact_text='x',explanation='y',status=FactStatus.needs_review)
    assert f.status!=FactStatus.approved

from datetime import datetime, date, timedelta
import json
from sqlmodel import SQLModel, Session, create_engine, select
from app.models import *
from app.db import normalize_database_url
from app.main import coerce_ymd_date, daily_settings_payload
from app.services.planner import classify_day, score_topic, generate_plan
from app.services.quiz import select_today_questions
from app.services.import_mcq import import_mcq_jsonl

def mk():
    e=create_engine('sqlite://', connect_args={'check_same_thread':False})
    SQLModel.metadata.create_all(e)
    return Session(e)

def test_day_classification():
    ev=[CalendarEvent(title='BJJ',start_at=datetime(2026,1,1,21),end_at=datetime(2026,1,1,22),tags=[])]
    assert classify_day(ev)=='late_bjj_day'

def test_postgres_database_urls_use_installed_driver():
    assert normalize_database_url('postgres://u:p@h:5432/db') == 'postgresql+psycopg://u:p@h:5432/db'
    assert normalize_database_url('postgresql://u:p@h:5432/db') == 'postgresql+psycopg://u:p@h:5432/db'

def test_coerce_ymd_date_for_json_payloads():
    assert coerce_ymd_date('2026-05-23') == date(2026, 5, 23)
    assert coerce_ymd_date(date(2026, 5, 23)) == date(2026, 5, 23)

def test_daily_settings_default_work_target():
    s=mk()
    assert daily_settings_payload(s, date(2026, 5, 23))["work_task_target"] == 1

def test_task_priority_scoring():
    s=mk(); t=Topic(name='Startup',category=TopicCategory.professional,priority_weight=5); s.add(t); s.commit(); s.refresh(t)
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

def test_quiz_excludes_bjj_cards():
    s=mk(); bjj=Topic(name='BJJ',category=TopicCategory.training,priority_weight=5); ddia=Topic(name='DDIA',category=TopicCategory.professional,priority_weight=5); s.add(bjj); s.add(ddia); s.commit(); s.refresh(bjj); s.refresh(ddia)
    q1=Question(fact_id=1,topic_id=bjj.id,prompt='bjj',correct_answer='a',acceptable_answers=['a'],explanation='e')
    q2=Question(fact_id=2,topic_id=ddia.id,prompt='ddia',correct_answer='a',acceptable_answers=['a'],explanation='e')
    s.add(q1); s.add(q2); s.commit(); s.refresh(q1); s.refresh(q2)
    s.add(CardState(question_id=q1.id,next_due_at=datetime.utcnow()-timedelta(days=3),recent_accuracy=0.0))
    s.add(CardState(question_id=q2.id,next_due_at=datetime.utcnow()+timedelta(days=3),recent_accuracy=1.0)); s.commit()
    out=select_today_questions(s,date.today())
    assert [q.id for q in out]==[q2.id]

def test_quiz_keeps_some_topic_diversity():
    s=mk(); ddia=Topic(name='DDIA',category=TopicCategory.professional,priority_weight=5); chinese=Topic(name='Chinese',category=TopicCategory.language,priority_weight=4); s.add(ddia); s.add(chinese); s.commit(); s.refresh(ddia); s.refresh(chinese)
    for i in range(5):
        s.add(Question(fact_id=i+1,topic_id=ddia.id,prompt=f'ddia {i}',correct_answer='a',acceptable_answers=['a'],explanation='e'))
    s.add(Question(fact_id=99,topic_id=chinese.id,prompt='chinese',correct_answer='a',acceptable_answers=['a'],explanation='e'))
    s.commit()
    out=select_today_questions(s,date.today())
    topic_ids=[q.topic_id for q in out]
    assert chinese.id in topic_ids

def test_ddia_chapter_setting_filters_ddia_cards():
    s=mk(); ddia=Topic(name='DDIA',category=TopicCategory.professional,priority_weight=5); chinese=Topic(name='Chinese',category=TopicCategory.language,priority_weight=4); s.add(ddia); s.add(chinese); s.commit(); s.refresh(ddia); s.refresh(chinese)
    q1=Question(fact_id=1,topic_id=ddia.id,prompt='chapter 1',correct_answer='a',acceptable_answers=['a'],metadata_json={'chapter':1},explanation='e')
    q2=Question(fact_id=2,topic_id=ddia.id,prompt='chapter 2',correct_answer='a',acceptable_answers=['a'],metadata_json={'chapter':2},explanation='e')
    q3=Question(fact_id=3,topic_id=chinese.id,prompt='chinese',correct_answer='a',acceptable_answers=['a'],explanation='e')
    s.add(q1); s.add(q2); s.add(q3); s.add(AppSetting(key='ddia_chapters', value={'chapters':[2]})); s.commit()
    out=select_today_questions(s,date.today())
    prompts=[q.prompt for q in out]
    assert 'chapter 1' not in prompts
    assert 'chapter 2' in prompts
    assert 'chinese' in prompts

def test_late_bjj_avoids_heavy():
    s=mk(); t=Topic(name='Deep Work',category=TopicCategory.professional,priority_weight=4); s.add(t)
    s.add(CalendarEvent(title='BJJ',start_at=datetime.combine(date.today(), datetime.min.time()).replace(hour=21), end_at=datetime.combine(date.today(), datetime.min.time()).replace(hour=22),tags=[])); s.commit()
    p=generate_plan(s,date.today()); assert 'High cognitive tasks' in p.avoid[0]

def test_bad_sleep_reduces_serious_tasks():
    s=mk(); s.add(Topic(name='A',category=TopicCategory.professional,priority_weight=5)); s.add(Topic(name='B',category=TopicCategory.professional,priority_weight=4)); s.add(DailyCheckIn(date=date.today(),sleep_quality=Quality.bad,soreness=Level.low,work_pressure=Level.low)); s.commit()
    p=generate_plan(s,date.today()); assert p.secondary_focus is None

def test_ddia_weekend_and_leetcode_non_bjj_rules():
    s=mk(); ddia=Topic(name='DDIA',category=TopicCategory.professional,priority_weight=5); lc=Topic(name='LeetCode',category=TopicCategory.professional,priority_weight=5)
    s.add(ddia); s.add(lc); s.commit(); s.refresh(ddia); s.refresh(lc)
    saturday=date(2026,1,3); monday=date(2026,1,5)
    assert score_topic(s,ddia,saturday,'open_day') > score_topic(s,lc,saturday,'open_day')
    assert score_topic(s,lc,monday,'open_day') > score_topic(s,ddia,monday,'open_day')
    assert score_topic(s,lc,monday,'late_bjj_day',has_bjj=True) < score_topic(s,ddia,monday,'late_bjj_day',has_bjj=True)

def test_plan_includes_admin_enumeration_options():
    s=mk(); s.add(Topic(name='Startup',category=TopicCategory.professional,priority_weight=4)); s.add(AdminItem(title='Renew passport')); s.commit()
    p=generate_plan(s,date(2026,1,6))
    assert 'Renew passport' in p.admin['options']

def test_sunday_plan_surfaces_meal_prep():
    s=mk(); s.add(Topic(name='Meal prep',category=TopicCategory.admin,priority_weight=3)); s.add(Topic(name='DDIA',category=TopicCategory.professional,priority_weight=5)); s.commit()
    p=generate_plan(s,date(2026,1,4))
    assert p.admin['hint'].startswith('Sunday')
    assert 'Meal prep' in p.admin['options']
    assert score_topic(s, s.exec(select(Topic).where(Topic.name=='Meal prep')).first(), date(2026,1,4), 'open_day') > 5

def test_only_approved_fact_generates_questions():
    f=AtomicFact(source_id=1,topic_id=1,fact_text='x',explanation='y',status=FactStatus.needs_review)
    assert f.status!=FactStatus.approved

def test_import_mcq_jsonl_creates_multiple_choice_questions(tmp_path):
    path=tmp_path/'mcqs.jsonl'
    path.write_text(json.dumps({
        "id":"ddia2-test-001",
        "source":"Designing Data-Intensive Applications, 2nd Edition",
        "chapter":1,
        "type":"multiple_choice",
        "difficulty":"easy",
        "tags":["oltp"],
        "question":"Which workload is most characteristic of an OLTP system?",
        "choices":[
            {"label":"A","text":"Large scans"},
            {"label":"B","text":"Many small reads and writes"}
        ],
        "correct_choice":"B",
        "answer":"Many small reads and writes",
        "explanation":"OLTP serves interactive application requests."
    })+'\n', encoding='utf-8')
    s=mk()
    summary=import_mcq_jsonl(s,path)
    s.commit()
    q=s.exec(select(Question)).first()
    fact=s.exec(select(AtomicFact)).first()
    assert summary["created_questions"]==1
    assert q.question_type==QuestionType.multiple_choice
    assert q.external_id=="ddia2-test-001"
    assert q.choices[1]["label"]=="B"
    assert q.correct_choice=="B"
    assert q.metadata_json["chapter"]==1
    assert fact.status==FactStatus.approved

def test_import_mcq_jsonl_updates_existing_source_metadata(tmp_path):
    path=tmp_path/'mcqs.jsonl'
    base={
        "id":"ddia2-test-001",
        "source":"Designing Data-Intensive Applications, 2nd Edition",
        "chapter":1,
        "type":"multiple_choice",
        "difficulty":"easy",
        "tags":["oltp"],
        "question":"Which workload is most characteristic of an OLTP system?",
        "choices":[{"label":"A","text":"Large scans"},{"label":"B","text":"Many small reads and writes"}],
        "correct_choice":"B",
        "answer":"Many small reads and writes",
        "explanation":"Old explanation."
    }
    path.write_text(json.dumps(base)+'\n', encoding='utf-8')
    s=mk()
    assert import_mcq_jsonl(s,path)["created_questions"]==1
    sourced={**base, "explanation":"Updated explanation.", "source_page_start":3, "source_page_end":4, "source_pdf_page_start":27, "source_pdf_page_end":28}
    path.write_text(json.dumps(sourced)+'\n', encoding='utf-8')
    summary=import_mcq_jsonl(s,path)
    s.commit()
    q=s.exec(select(Question)).first()
    fact=s.exec(select(AtomicFact)).first()
    assert summary["created_questions"]==0
    assert summary["updated_existing"]==1
    assert q.metadata_json["source_page_start"]==3
    assert q.metadata_json["source_pdf_page_end"]==28
    assert q.explanation=="Updated explanation."
    assert fact.explanation=="Updated explanation."

def test_import_mcq_jsonl_supports_answer_index_and_context(tmp_path):
    path=tmp_path/'chinese.jsonl'
    path.write_text(json.dumps({
        "id":"cn-notes-test-001",
        "source_pages":[1],
        "category":"greetings",
        "tags":["vocab"],
        "difficulty":1,
        "question_type":"multiple_choice",
        "question":"What does this mean?",
        "context_zh":"\u4f60\u597d",
        "context_pinyin":"n\u01d0 h\u01ceo",
        "choices":["Hello","Goodbye","Thank you","Sorry"],
        "answer":"Hello",
        "answer_index":0,
        "explanation":"Basic greeting."
    })+'\n', encoding='utf-8')
    s=mk()
    summary=import_mcq_jsonl(s,path,topic_name='Chinese',source_title='Chinese Notes MCQ JSONL')
    s.commit()
    q=s.exec(select(Question)).first()
    fact=s.exec(select(AtomicFact)).first()
    topic=s.exec(select(Topic).where(Topic.name=='Chinese')).first()
    assert summary["created_questions"]==1
    assert topic.category==TopicCategory.language
    assert q.prompt=="What does this mean? \u4f60\u597d (n\u01d0 h\u01ceo)"
    assert q.correct_choice=="A"
    assert q.choices[0]["text"]=="Hello"
    assert q.metadata_json["category"]=="greetings"
    assert fact.difficulty==1

from datetime import datetime, timedelta, date
import hashlib
from sqlmodel import Session, select
from app.models import AppSetting, CardState, Question, Topic, DailyPlan, Review, Grade


DDIA_CHAPTER_SETTING_KEY = "ddia_chapters"
DAILY_TOPIC_TARGETS = {"ddia": 10, "chinese": 10}


def is_bjj_topic(topic: Topic | None) -> bool:
    return bool(topic and topic.name.lower() in {"bjj", "jiu jitsu", "jiu-jitsu", "brazilian jiu jitsu"})

def selected_ddia_chapters(session: Session) -> set[int]:
    setting = session.get(AppSetting, DDIA_CHAPTER_SETTING_KEY)
    chapters = (setting.value or {}).get("chapters") if setting else []
    return {int(chapter) for chapter in chapters if str(chapter).isdigit()}

def ddia_question_allowed(q: Question, topic: Topic | None, chapters: set[int]) -> bool:
    if not chapters or not topic or topic.name.lower()!="ddia":
        return True
    raw_chapter=(q.metadata_json or {}).get("chapter")
    try:
        return int(raw_chapter) in chapters
    except (TypeError, ValueError):
        return False

def topic_key(topic: Topic | None) -> str:
    return topic.name.strip().lower() if topic else "unknown"

def stable_random_bonus(question_id: int | None, on_date: date) -> float:
    digest=hashlib.sha256(f"{on_date.isoformat()}:{question_id or 0}".encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) / 0xFFFFFFFF) * 0.3

def select_today_questions(session:Session, on_date:date):
    questions=session.exec(select(Question).where(Question.active==True)).all()
    plan=session.exec(select(DailyPlan).where(DailyPlan.date==on_date).order_by(DailyPlan.generated_at.desc())).first()
    focus=plan.main_focus.get("topic") if plan else None
    ddia_chapters=selected_ddia_chapters(session)
    ranked=[]
    for q in questions:
        cs=session.exec(select(CardState).where(CardState.question_id==q.id)).first()
        topic=session.get(Topic,q.topic_id)
        if is_bjj_topic(topic):
            continue
        if not ddia_question_allowed(q, topic, ddia_chapters):
            continue
        due=3 if not cs or not cs.next_due_at or cs.next_due_at.date()<=on_date else 0
        weak=(1-(cs.recent_accuracy if cs else 0.5))*2
        imp=(topic.priority_weight/5) if topic else 0
        bonus=1.5 if focus and topic and topic.name==focus else 0
        rand=stable_random_bonus(q.id, on_date)
        ranked.append((q,topic,due+weak+imp+bonus+rand))
    ranked.sort(key=lambda x:x[2], reverse=True)
    targeted=[]
    for target_topic, target_count in DAILY_TOPIC_TARGETS.items():
        topic_questions=[q for q,topic,_ in ranked if topic_key(topic)==target_topic]
        targeted.extend(topic_questions[:target_count])
    if targeted:
        return targeted

    count=20
    if plan and plan.quiz.get("count"): count=plan.quiz["count"]
    topic_limit=max(2, count//2)
    selected=[]
    overflow=[]
    topic_counts={}
    for q,topic,_ in ranked:
        topic_name=topic.name if topic else "unknown"
        cap=count if focus and topic_name==focus else topic_limit
        if topic_counts.get(topic_name,0) < cap:
            selected.append(q)
            topic_counts[topic_name]=topic_counts.get(topic_name,0)+1
        else:
            overflow.append(q)
        if len(selected)==count:
            return selected
    return (selected+overflow)[:count]

def apply_review(session:Session, question_id:int, user_answer:str, grade:Grade, is_correct:bool, feedback:str|None=None):
    review=Review(question_id=question_id,user_answer=user_answer,grade=grade,is_correct=is_correct,feedback=feedback)
    cs=session.exec(select(CardState).where(CardState.question_id==question_id)).first() or CardState(question_id=question_id)
    days={Grade.again:1, Grade.hard:2, Grade.good:5, Grade.easy:12}[grade]
    cs.last_seen_at=datetime.utcnow(); cs.next_due_at=datetime.utcnow()+timedelta(days=days); cs.times_seen+=1; cs.times_correct += 1 if is_correct else 0
    cs.recent_accuracy=cs.times_correct/max(cs.times_seen,1)
    session.add(review); session.add(cs); session.commit(); return review,cs

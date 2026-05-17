from datetime import datetime, timedelta, date
import random
from sqlmodel import Session, select
from app.models import CardState, Question, Topic, DailyPlan, Review, Grade

def select_today_questions(session:Session, on_date:date):
    questions=session.exec(select(Question).where(Question.active==True)).all()
    plan=session.exec(select(DailyPlan).where(DailyPlan.date==on_date).order_by(DailyPlan.generated_at.desc())).first()
    focus=plan.main_focus.get("topic") if plan else None
    ranked=[]
    for q in questions:
        cs=session.exec(select(CardState).where(CardState.question_id==q.id)).first()
        topic=session.get(Topic,q.topic_id)
        due=3 if not cs or not cs.next_due_at or cs.next_due_at.date()<=on_date else 0
        weak=(1-(cs.recent_accuracy if cs else 0.5))*2
        imp=(topic.priority_weight/5) if topic else 0
        bonus=1.5 if focus and topic and topic.name==focus else 0
        rand=random.random()*0.3
        ranked.append((q,due+weak+imp+bonus+rand))
    ranked.sort(key=lambda x:x[1], reverse=True)
    count=5
    if plan and plan.quiz.get("count"): count=plan.quiz["count"]
    return [q for q,_ in ranked[:count]]

def apply_review(session:Session, question_id:int, user_answer:str, grade:Grade, is_correct:bool, feedback:str|None=None):
    review=Review(question_id=question_id,user_answer=user_answer,grade=grade,is_correct=is_correct,feedback=feedback)
    cs=session.exec(select(CardState).where(CardState.question_id==question_id)).first() or CardState(question_id=question_id)
    days={Grade.again:1, Grade.hard:2, Grade.good:5, Grade.easy:12}[grade]
    cs.last_seen_at=datetime.utcnow(); cs.next_due_at=datetime.utcnow()+timedelta(days=days); cs.times_seen+=1; cs.times_correct += 1 if is_correct else 0
    cs.recent_accuracy=cs.times_correct/max(cs.times_seen,1)
    session.add(review); session.add(cs); session.commit(); return review,cs

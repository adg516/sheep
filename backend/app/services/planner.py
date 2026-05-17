from datetime import date, datetime, timedelta
from sqlmodel import Session, select
from app.models import CalendarEvent, DailyCheckIn, DailyPlan, Task, TaskStatus, Topic, Review, Question, CardState, EnergyCost

def classify_day(events:list[CalendarEvent])->str:
    titles=" ".join(e.title.lower() for e in events)
    if "bjj" in titles and any(e.start_at.hour>=20 for e in events if "bjj" in e.title.lower()): return "late_bjj_day"
    if "social" in titles or "friends" in titles: return "social_day"
    if "office" in titles or "work" in titles: return "office_day"
    if "bjj" in titles or "lifting" in titles or "train" in titles: return "training_day"
    return "open_day"

def score_topic(session:Session, topic:Topic, on_date:date, day_type:str)->float:
    week_start=on_date-timedelta(days=on_date.weekday())
    done=session.exec(select(Task).where(Task.topic_id==topic.id, Task.status==TaskStatus.done, Task.scheduled_date>=week_start)).all()
    deficits=1 if len(done)==0 else 0
    last_done=session.exec(select(Task).where(Task.topic_id==topic.id, Task.status==TaskStatus.done).order_by(Task.completed_at.desc())).first()
    stale=2 if (not last_done or (datetime.utcnow()- (last_done.completed_at or datetime.utcnow())).days>5) else 0
    questions=session.exec(select(Question.id).where(Question.topic_id==topic.id)).all()
    weakness=0
    if questions:
        cards=session.exec(select(CardState).where(CardState.question_id.in_(questions))).all()
        if cards:
            avg=sum(c.recent_accuracy for c in cards)/len(cards)
            weakness=2 if avg<0.6 else 0
    missed=session.exec(select(Task).where(Task.topic_id==topic.id, Task.status==TaskStatus.missed, Task.created_at>=datetime.utcnow()-timedelta(days=7))).all()
    missed_s=1 if missed else 0
    energy_penalty=1 if day_type=="late_bjj_day" and topic.category=="professional" else 0
    return topic.priority_weight+deficits+stale+weakness+missed_s-energy_penalty

def generate_plan(session:Session, on_date:date):
    events=session.exec(select(CalendarEvent).where(CalendarEvent.start_at>=datetime.combine(on_date, datetime.min.time()), CalendarEvent.start_at<datetime.combine(on_date+timedelta(days=1), datetime.min.time()))).all()
    day_type=classify_day(events)
    checkin=session.exec(select(DailyCheckIn).where(DailyCheckIn.date==on_date)).first()
    topics=session.exec(select(Topic).where(Topic.active==True)).all()
    ranked=sorted([(t,score_topic(session,t,on_date,day_type)) for t in topics], key=lambda x:x[1], reverse=True)
    main={"topic": ranked[0][0].name, "score": ranked[0][1]} if ranked else {}
    secondary={"topic": ranked[1][0].name, "score": ranked[1][1]} if len(ranked)>1 else None
    if checkin and checkin.sleep_quality.value=="bad": secondary=None
    avoid=["High cognitive tasks after BJJ"] if day_type=="late_bjj_day" else []
    quiz_count=10 if day_type=="open_day" else 5
    if day_type=="late_bjj_day" or (checkin and checkin.sleep_quality.value=="bad"): quiz_count=4
    plan=DailyPlan(date=on_date, day_type=day_type, main_focus=main, secondary_focus=secondary, training={"hint":"Keep training light if sore"}, admin={"hint":"Minimum viable day: 1 essential admin task"}, quiz={"count":quiz_count}, avoid=avoid)
    session.add(plan); session.commit(); session.refresh(plan)
    return plan

from datetime import date, datetime, timedelta
from sqlmodel import Session, select
from app.models import AdminItem, CalendarEvent, DailyCheckIn, DailyPlan, Task, TaskStatus, Topic, Review, Question, CardState, EnergyCost

def classify_day(events:list[CalendarEvent])->str:
    titles=" ".join(e.title.lower() for e in events)
    if "bjj" in titles and any(e.start_at.hour>=20 for e in events if "bjj" in e.title.lower()): return "late_bjj_day"
    if "social" in titles or "friends" in titles: return "social_day"
    if "office" in titles or "work" in titles: return "office_day"
    if "bjj" in titles or "lifting" in titles or "train" in titles: return "training_day"
    return "open_day"

def score_topic(session:Session, topic:Topic, on_date:date, day_type:str, has_bjj:bool=False)->float:
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
    category = topic.category.value if hasattr(topic.category, "value") else topic.category
    energy_penalty=1 if day_type=="late_bjj_day" and category=="professional" else 0
    score=topic.priority_weight+deficits+stale+weakness+missed_s-energy_penalty
    name=topic.name.lower()
    is_weekend=on_date.weekday()>=5
    if name=="ddia":
        score += 3 if is_weekend else -5
    if name=="leetcode":
        score += -8 if has_bjj else 2
    if name=="meal prep" and on_date.weekday()==6:
        score += 4
    if name in {"reading", "fun reading"} and is_weekend:
        score += 1
    return score

def focus_payload(topic:Topic, score:float, on_date:date, has_bjj:bool)->dict:
    name=topic.name
    suggestion=None
    minutes=45
    category = topic.category.value if hasattr(topic.category, "value") else topic.category
    if name.lower()=="ddia":
        minutes=30
        suggestion="30 min DDIA reading block; weekends only unless you choose otherwise"
    elif name.lower()=="leetcode":
        suggestion="1 LeetCode problem; scheduled for non-BJJ days"
    elif name.lower() in {"reading", "fun reading"}:
        minutes=30
        suggestion="Light reading bucket"
    elif name.lower()=="meal prep":
        minutes=60
        suggestion="Sunday meal prep block"
    elif category=="professional":
        suggestion="Pick one concrete work task and finish the smallest useful slice"
    return {"topic": name, "score": score, "minutes": minutes, "suggestion": suggestion}

def generate_plan(session:Session, on_date:date):
    events=session.exec(select(CalendarEvent).where(CalendarEvent.start_at>=datetime.combine(on_date, datetime.min.time()), CalendarEvent.start_at<datetime.combine(on_date+timedelta(days=1), datetime.min.time()))).all()
    day_type=classify_day(events)
    has_bjj=any("bjj" in e.title.lower() for e in events)
    checkin=session.exec(select(DailyCheckIn).where(DailyCheckIn.date==on_date).order_by(DailyCheckIn.id.desc())).first()
    topics=session.exec(select(Topic).where(Topic.active==True)).all()
    ranked=sorted([(t,score_topic(session,t,on_date,day_type,has_bjj)) for t in topics], key=lambda x:x[1], reverse=True)
    main=focus_payload(ranked[0][0], ranked[0][1], on_date, has_bjj) if ranked else {}
    secondary=focus_payload(ranked[1][0], ranked[1][1], on_date, has_bjj) if len(ranked)>1 else None
    if checkin and checkin.sleep_quality.value=="bad": secondary=None
    avoid=["High cognitive tasks after BJJ"] if day_type=="late_bjj_day" else []
    if has_bjj: avoid.append("LeetCode unless it is a tiny warm-up")
    if on_date.weekday()<5: avoid.append("DDIA reading block; keep it for Saturday/Sunday")
    quiz_count=20
    admin_items=session.exec(select(AdminItem).where(AdminItem.active==True).order_by(AdminItem.created_at.desc())).all()
    admin_options=[item.title for item in admin_items[:5]]
    sunday_meal_prep=on_date.weekday()==6 and any(t.name.lower()=="meal prep" for t in topics)
    if sunday_meal_prep and "Meal prep" not in admin_options:
        admin_options=["Meal prep", *admin_options]
    training_hint="Training marked today; keep the post-training plan light" if day_type in {"late_bjj_day","training_day"} else "No training logged yet; add BJJ/lifting if it is happening"
    admin_hint="Sunday: meal prep is the default admin task" if sunday_meal_prep else "Minimum viable day: 1 essential admin task"
    if admin_options:
        admin_hint=f"{admin_hint} from your list"
    plan=DailyPlan(date=on_date, day_type=day_type, main_focus=main, secondary_focus=secondary, training={"hint":training_hint}, admin={"hint":admin_hint, "options":admin_options}, quiz={"count":quiz_count, "topics":{"DDIA":10, "Chinese":10}}, avoid=avoid)
    session.add(plan); session.commit(); session.refresh(plan)
    return plan

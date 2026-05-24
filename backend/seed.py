from datetime import date
from sqlmodel import Session
from app.db import init_db, engine
from app.models import *

init_db()
with Session(engine) as s:
    topics=[("DDIA",TopicCategory.professional,5),("LeetCode",TopicCategory.professional,5),("BJJ",TopicCategory.training,5),("Chinese",TopicCategory.language,4),("Startup",TopicCategory.professional,4),("Lifting",TopicCategory.training,4),("Meditation",TopicCategory.language,3),("Meal prep",TopicCategory.admin,3),("Admin",TopicCategory.admin,3),("Friends/social",TopicCategory.social,2),("Fun reading",TopicCategory.creative,2),("Bidet reviews",TopicCategory.creative,1)]
    tmap={}
    for n,c,p in topics:
        t=Topic(name=n,category=c,priority_weight=p); s.add(t); s.flush(); tmap[n]=t
    w=[("DDIA",2,TargetType.blocks),("LeetCode",4,TargetType.questions),("BJJ",3,TargetType.sessions),("Lifting",3,TargetType.sessions),("Chinese",2,TargetType.sessions),("Meditation",4,TargetType.sessions),("Startup",1,TargetType.blocks),("Meal prep",1,TargetType.blocks),("Admin",2,TargetType.blocks)]
    for n,v,tp in w: s.add(WeeklyTarget(topic_id=tmap[n].id,target_type=tp,target_value=v,current_period_start=date.today()))
    src=Source(topic_id=tmap['DDIA'].id,title='DDIA notes',source_type=SourceType.book_notes,raw_text='Stale reads can happen with replication lag.')
    s.add(src); s.flush()
    facts=[AtomicFact(source_id=src.id,topic_id=tmap['DDIA'].id,fact_text='Replication lag can cause stale reads.',explanation='Replica is behind leader.',status=FactStatus.approved),AtomicFact(source_id=src.id,topic_id=tmap['Chinese'].id,fact_text='我今天学习中文 means I study Chinese today.',explanation='Simple present sentence.',status=FactStatus.approved),AtomicFact(source_id=src.id,topic_id=tmap['LeetCode'].id,fact_text='Sliding window keeps O(n) for contiguous constraints.',explanation='Move two pointers once.',status=FactStatus.approved)]
    for f in facts:
        s.add(f); s.flush(); s.add(Question(fact_id=f.id,topic_id=f.topic_id,prompt=f'Explain: {f.fact_text}',correct_answer=f.fact_text,acceptable_answers=[f.fact_text],explanation=f.explanation))
    s.commit()
print('seeded')

from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

class TopicCategory(str, Enum): professional="professional"; language="language"; training="training"; health="health"; admin="admin"; creative="creative"; social="social"; other="other"
class TargetType(str, Enum): blocks="blocks"; minutes="minutes"; questions="questions"; sessions="sessions"; binary="binary"
class EnergyCost(str, Enum): low="low"; medium="medium"; high="high"
class TaskStatus(str, Enum): planned="planned"; done="done"; missed="missed"; skipped="skipped"
class SourceType(str, Enum): note="note"; book_notes="book_notes"; bjj_log="bjj_log"; language_lesson="language_lesson"; leetcode_note="leetcode_note"; meditation_note="meditation_note"; other="other"
class FactStatus(str, Enum): needs_review="needs_review"; approved="approved"; rejected="rejected"
class QuestionType(str, Enum): short_answer="short_answer"; multiple_choice="multiple_choice"; cloze="cloze"; translation="translation"; self_grade="self_grade"
class Grade(str, Enum): again="again"; hard="hard"; good="good"; easy="easy"
class Quality(str, Enum): bad="bad"; meh="meh"; good="good"
class Level(str, Enum): low="low"; medium="medium"; high="high"
class CalendarSource(str, Enum): manual="manual"; google="google"

class Topic(SQLModel, table=True):
    id: Optional[int]=Field(default=None, primary_key=True); name:str; category:TopicCategory; priority_weight:int=3; active:bool=True; created_at:datetime=Field(default_factory=datetime.utcnow)
class WeeklyTarget(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); topic_id:int=Field(foreign_key="topic.id"); target_type:TargetType; target_value:int; current_period_start:date; active:bool=True
class Task(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); topic_id:Optional[int]=Field(default=None, foreign_key="topic.id"); title:str; description:Optional[str]=None; energy_cost:EnergyCost=EnergyCost.medium; duration_minutes:int=45; status:TaskStatus=TaskStatus.planned; scheduled_date:Optional[date]=None; completed_at:Optional[datetime]=None; created_at:datetime=Field(default_factory=datetime.utcnow)
class Source(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); topic_id:int=Field(foreign_key="topic.id"); title:str; source_type:SourceType; raw_text:str; source_ref:Optional[str]=None; created_at:datetime=Field(default_factory=datetime.utcnow)
class AtomicFact(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); source_id:int=Field(foreign_key="source.id"); topic_id:int=Field(foreign_key="topic.id"); fact_text:str; explanation:str; tags:list[str]=Field(default_factory=list, sa_column=Column(JSON)); status:FactStatus=FactStatus.needs_review; difficulty:int=2; created_at:datetime=Field(default_factory=datetime.utcnow)
class Question(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); fact_id:int=Field(foreign_key="atomicfact.id"); topic_id:int=Field(foreign_key="topic.id"); question_type:QuestionType=QuestionType.short_answer; prompt:str; correct_answer:str; acceptable_answers:list[str]=Field(default_factory=list, sa_column=Column(JSON)); distractors:Optional[list[str]]=Field(default=None, sa_column=Column(JSON)); explanation:str; active:bool=True; created_at:datetime=Field(default_factory=datetime.utcnow)
class Review(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); question_id:int=Field(foreign_key="question.id"); reviewed_at:datetime=Field(default_factory=datetime.utcnow); user_answer:str; grade:Grade; is_correct:bool; feedback:Optional[str]=None
class CardState(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); question_id:int=Field(foreign_key="question.id", unique=True); last_seen_at:Optional[datetime]=None; next_due_at:Optional[datetime]=None; times_seen:int=0; times_correct:int=0; recent_accuracy:float=0.0; stability:Optional[float]=None; difficulty:Optional[float]=None
class DailyCheckIn(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); date:date; sleep_quality:Quality=Quality.meh; soreness:Level=Level.medium; work_pressure:Level=Level.medium; notes:Optional[str]=None
class DailyPlan(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); date:date; day_type:str; main_focus:dict=Field(default_factory=dict, sa_column=Column(JSON)); secondary_focus:Optional[dict]=Field(default=None, sa_column=Column(JSON)); training:Optional[dict]=Field(default=None, sa_column=Column(JSON)); admin:Optional[dict]=Field(default=None, sa_column=Column(JSON)); quiz:dict=Field(default_factory=dict, sa_column=Column(JSON)); avoid:list[str]=Field(default_factory=list, sa_column=Column(JSON)); generated_at:datetime=Field(default_factory=datetime.utcnow)
class CalendarEvent(SQLModel, table=True):
    id:Optional[int]=Field(default=None, primary_key=True); external_id:Optional[str]=None; title:str; start_at:datetime; end_at:datetime; location:Optional[str]=None; source:CalendarSource=CalendarSource.manual; tags:list[str]=Field(default_factory=list, sa_column=Column(JSON))

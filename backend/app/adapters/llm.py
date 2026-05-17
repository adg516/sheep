from typing import List

from openai import OpenAI
from pydantic import BaseModel

from app.core.config import settings


class FactOut(BaseModel):
    fact_text: str
    explanation: str
    tags: List[str]


class QuestionOut(BaseModel):
    prompt: str
    correct_answer: str
    acceptable_answers: List[str]
    explanation: str


class MockLLM:
    def extract_facts(self, raw_text: str):
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return [
            FactOut(fact_text=line, explanation="From user source", tags=["user_note"])
            for line in lines[:5]
        ]

    def generate_questions(self, fact_text: str, explanation: str):
        return [
            QuestionOut(
                prompt=f"What is true about: {fact_text}?",
                correct_answer=fact_text,
                acceptable_answers=[fact_text],
                explanation=explanation,
            )
        ]

    def grade(self, answer: str, correct: str):
        ok = correct.lower() in answer.lower() or answer.lower() in correct.lower()
        return {"is_correct": ok, "feedback": "Close enough" if ok else "Review the approved fact."}


class OpenAILLM(MockLLM):
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)


def get_llm():
    return OpenAILLM() if settings.openai_api_key else MockLLM()

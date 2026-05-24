from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models import (
    AtomicFact,
    FactStatus,
    Question,
    QuestionType,
    Source,
    SourceType,
    Topic,
    TopicCategory,
)


CORE_KEYS = {"question", "choices", "correct_choice", "answer_index", "answer", "explanation"}
DIFFICULTY = {"easy": 1, "medium": 2, "hard": 3}


def _require_text(record: dict[str, Any], key: str, line_no: int) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Line {line_no}: `{key}` must be a non-empty string")
    return value.strip()


def _normalize_choices(raw_choices: Any, line_no: int) -> list[dict[str, str]]:
    if not isinstance(raw_choices, list) or not raw_choices:
        raise ValueError(f"Line {line_no}: `choices` must be a non-empty list")

    choices = []
    for index, choice in enumerate(raw_choices):
        fallback_label = chr(ord("A") + index)
        if isinstance(choice, dict):
            label = str(choice.get("label") or fallback_label).strip()
            text = str(choice.get("text") or "").strip()
        else:
            label = fallback_label
            text = str(choice).strip()

        if not label or not text:
            raise ValueError(f"Line {line_no}: every choice needs a label and text")
        choices.append({"label": label, "text": text})

    return choices


def _resolve_correct_choice(record: dict[str, Any], choices: list[dict[str, str]], line_no: int) -> str:
    if record.get("correct_choice") is not None:
        correct_choice = _require_text(record, "correct_choice", line_no)
    elif isinstance(record.get("answer_index"), int):
        answer_index = record["answer_index"]
        if answer_index < 0 or answer_index >= len(choices):
            raise ValueError(f"Line {line_no}: `answer_index` is outside the choices list")
        correct_choice = choices[answer_index]["label"]
    else:
        answer = _require_text(record, "answer", line_no)
        matching = [choice["label"] for choice in choices if choice["text"] == answer]
        if not matching:
            raise ValueError(f"Line {line_no}: needs `correct_choice`, `answer_index`, or an answer matching a choice")
        correct_choice = matching[0]

    if correct_choice not in {choice["label"] for choice in choices}:
        raise ValueError(f"Line {line_no}: `correct_choice` does not match a choice label")
    return correct_choice


def _context_text(record: dict[str, Any]) -> str:
    zh = str(record.get("context_zh") or "").strip()
    pinyin = str(record.get("context_pinyin") or "").strip()
    if zh and pinyin:
        return f"{zh} ({pinyin})"
    return zh or pinyin


def _should_add_context(question: str) -> bool:
    normalized = question.strip().lower()
    return (
        "this" in normalized
        or normalized.startswith("in ")
        or normalized.startswith("where does ")
        or normalized.startswith("when reading ")
        or "difference between" in normalized
    )


def _prompt(record: dict[str, Any], line_no: int) -> str:
    question = _require_text(record, "question", line_no)
    context = _context_text(record)
    if context and _should_add_context(question):
        return f"{question} {context}"
    return question


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in CORE_KEYS}


def _tags(metadata: dict[str, Any], topic_name: str) -> list[str]:
    tags = [str(tag) for tag in metadata.get("tags", []) if str(tag).strip()]
    topic_tag = topic_name.lower().replace(" ", "_")
    for tag in [
        topic_tag,
        metadata.get("category"),
        metadata.get("difficulty"),
        metadata.get("type"),
        metadata.get("question_type"),
    ]:
        if tag:
            tags.append(str(tag))
    if metadata.get("chapter") is not None:
        tags.append(f"chapter-{metadata['chapter']}")
    for page in metadata.get("source_pages", []) or []:
        tags.append(f"page-{page}")
    return sorted(set(tags))


def _difficulty(metadata: dict[str, Any]) -> int:
    raw = metadata.get("difficulty")
    if isinstance(raw, int):
        return max(1, min(raw, 5))
    return DIFFICULTY.get(str(metadata.get("difficulty", "")).lower(), 2)


def _get_or_create_topic(session: Session, topic_name: str) -> Topic:
    topic = session.exec(select(Topic).where(Topic.name == topic_name)).first()
    if topic:
        return topic

    category = TopicCategory.language if topic_name.lower() in {"chinese", "spanish", "hindi"} else TopicCategory.professional
    priority = 4 if category == TopicCategory.language else 5
    topic = Topic(name=topic_name, category=category, priority_weight=priority)
    session.add(topic)
    session.flush()
    return topic


def _get_or_create_source(session: Session, topic_id: int, title: str, source_ref: str) -> Source:
    source = session.exec(
        select(Source).where(Source.title == title, Source.source_ref == source_ref)
    ).first()
    if source:
        return source

    source = Source(
        topic_id=topic_id,
        title=title,
        source_type=SourceType.book_notes,
        raw_text=f"Imported multiple-choice questions from {source_ref}",
        source_ref=source_ref,
    )
    session.add(source)
    session.flush()
    return source


def _iter_records(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {line_no}: invalid JSON ({exc.msg})") from exc
            if not isinstance(record, dict):
                raise ValueError(f"Line {line_no}: expected a JSON object")
            yield line_no, record


def _iter_text_records(text: str):
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Line {line_no}: invalid JSON ({exc.msg})") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Line {line_no}: expected a JSON object")
        yield line_no, record


def import_mcq_records(
    session: Session,
    records,
    *,
    topic_name: str,
    source_title: str,
    source_ref: str,
    update_existing: bool = True,
) -> dict[str, int]:
    topic = _get_or_create_topic(session, topic_name)
    source = _get_or_create_source(session, topic.id, source_title, source_ref)
    created = 0
    skipped = 0
    updated = 0

    for line_no, record in records:
        prompt = _prompt(record, line_no)
        answer = _require_text(record, "answer", line_no)
        choices = _normalize_choices(record.get("choices"), line_no)
        correct_choice = _resolve_correct_choice(record, choices, line_no)
        metadata = _metadata(record)
        external_id = str(record.get("id") or metadata.get("id") or f"{source_title}:{line_no}")

        existing = session.exec(select(Question).where(Question.external_id == external_id)).first()
        if existing:
            if update_existing:
                explanation = str(record.get("explanation") or record.get("review_hint") or answer)
                distractors = [choice["text"] for choice in choices if choice["label"] != correct_choice]
                existing.topic_id = topic.id
                existing.prompt = prompt
                existing.correct_answer = answer
                existing.acceptable_answers = [answer, correct_choice]
                existing.distractors = distractors
                existing.choices = choices
                existing.correct_choice = correct_choice
                existing.metadata_json = metadata
                existing.explanation = explanation
                existing.question_type = QuestionType.multiple_choice

                fact = session.get(AtomicFact, existing.fact_id)
                if fact:
                    fact.source_id = source.id
                    fact.topic_id = topic.id
                    fact.fact_text = f"{prompt} Answer: {answer}"
                    fact.explanation = explanation
                    fact.tags = _tags(metadata, topic_name)
                    fact.status = FactStatus.approved
                    fact.difficulty = _difficulty(metadata)
                    session.add(fact)
                session.add(existing)
                updated += 1
            else:
                skipped += 1
            continue

        explanation = str(record.get("explanation") or record.get("review_hint") or answer)
        fact = AtomicFact(
            source_id=source.id,
            topic_id=topic.id,
            fact_text=f"{prompt} Answer: {answer}",
            explanation=explanation,
            tags=_tags(metadata, topic_name),
            status=FactStatus.approved,
            difficulty=_difficulty(metadata),
        )
        session.add(fact)
        session.flush()

        distractors = [choice["text"] for choice in choices if choice["label"] != correct_choice]
        question = Question(
            external_id=external_id,
            fact_id=fact.id,
            topic_id=topic.id,
            question_type=QuestionType.multiple_choice,
            prompt=prompt,
            correct_answer=answer,
            acceptable_answers=[answer, correct_choice],
            distractors=distractors,
            choices=choices,
            correct_choice=correct_choice,
            metadata_json=metadata,
            explanation=explanation,
        )
        session.add(question)
        created += 1

    return {"created_questions": created, "updated_existing": updated, "skipped_existing": skipped}


def import_mcq_jsonl_text(
    session: Session,
    text: str,
    *,
    topic_name: str,
    source_title: str,
    source_ref: str,
    update_existing: bool = True,
) -> dict[str, int]:
    return import_mcq_records(
        session,
        _iter_text_records(text),
        topic_name=topic_name,
        source_title=source_title,
        source_ref=source_ref,
        update_existing=update_existing,
    )


def import_mcq_jsonl(
    session: Session,
    path: Path,
    *,
    topic_name: str = "DDIA",
    source_title: str = "DDIA2 MCQ JSONL",
    update_existing: bool = True,
) -> dict[str, int]:
    return import_mcq_records(
        session,
        _iter_records(path),
        topic_name=topic_name,
        source_title=source_title,
        source_ref=str(path),
        update_existing=update_existing,
    )

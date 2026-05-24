from __future__ import annotations

import argparse
from pathlib import Path

from sqlmodel import Session

from app.db import engine, init_db
from app.services.import_mcq import import_mcq_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Import multiple-choice questions from JSONL.")
    parser.add_argument("path", type=Path, help="Path to a JSONL file with one MCQ object per line")
    parser.add_argument("--topic", default="DDIA", help="Topic name to attach imported questions to")
    parser.add_argument("--source-title", default="DDIA2 MCQ JSONL", help="Source title for the import")
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        summary = import_mcq_jsonl(
            session,
            args.path,
            topic_name=args.topic,
            source_title=args.source_title,
        )
        session.commit()

    print(
        "Imported {created_questions} questions; skipped {skipped_existing} existing questions.".format(
            **summary
        )
    )


if __name__ == "__main__":
    main()

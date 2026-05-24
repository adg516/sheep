from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


database_url = normalize_database_url(settings.database_url)
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args)


def ensure_question_import_columns():
    columns = {
        "external_id": "VARCHAR",
        "choices": "JSON",
        "correct_choice": "VARCHAR",
        "metadata": "JSON",
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "question" not in inspector.get_table_names():
            return

        existing = {column["name"] for column in inspector.get_columns("question")}
        for name, column_type in columns.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE question ADD COLUMN {name} {column_type}"))

        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_question_external_id ON question (external_id)"))


def init_db():
    SQLModel.metadata.create_all(engine)
    ensure_question_import_columns()


def get_session():
    with Session(engine) as session:
        yield session

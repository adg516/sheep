from sqlmodel import create_engine, Session, SQLModel

engine = create_engine("sqlite:///./command_card.db", connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s

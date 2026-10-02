from sqlmodel import SQLModel, Session, create_engine

from app.config import load_config


config = load_config()
engine = create_engine(config.database_url, echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

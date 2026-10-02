from sqlmodel import SQLModel, Session, create_engine, select

from app.config import load_config
from app.models import Model


config = load_config()
engine = create_engine(config.database_url, echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for configured in config.models:
            if not session.get(Model, configured.id):
                session.add(
                    Model(
                        id=configured.id,
                        display_name=configured.display_name,
                        provider_model_id=configured.provider_model_id,
                        is_open=configured.is_open,
                        license_type=configured.license_type,
                        is_baseline=configured.is_baseline,
                    )
                )
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session

from sqlmodel import SQLModel, Session, create_engine, select

from app.config import load_config
from app.models import Answer, Job, Model


config = load_config()
engine = create_engine(config.database_url, echo=False)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        configured_ids = {model.id for model in config.models if model.live_enabled}
        for configured in config.models:
            model = session.get(Model, configured.id)
            if model is None:
                model = Model(id=configured.id)
                session.add(model)
            model.display_name = configured.display_name
            model.provider_model_id = configured.provider_model_id
            model.is_open = configured.is_open
            model.license_type = configured.license_type
            model.is_baseline = configured.is_baseline
        for job in session.exec(select(Job)).all():
            if job.model_id not in configured_ids and job.status in {"queued", "running"}:
                job.status = "failed"
                job.last_error = "Model is no longer configured"
                answer = session.exec(
                    select(Answer).where(
                        Answer.prompt_id == job.prompt_id,
                        Answer.model_id == job.model_id,
                    )
                ).first()
                if answer:
                    answer.status = "error"
                    answer.error = job.last_error
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session

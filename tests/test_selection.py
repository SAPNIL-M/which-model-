from sqlmodel import Session, create_engine, select

from app.models import Answer, Model, Prompt
from app.services.selection import select_models


def test_selection_includes_baseline_and_balances_open_models():
    engine = create_engine("sqlite://")
    Model.metadata.create_all(engine)
    Prompt.metadata.create_all(engine)
    Answer.metadata.create_all(engine)
    with Session(engine) as session:
        models = [
            Model(id="baseline", display_name="Base", provider_model_id="b", is_open=False, license_type="closed", is_baseline=True),
            Model(id="a", display_name="A", provider_model_id="a", is_open=True, license_type="permissive"),
            Model(id="b", display_name="B", provider_model_id="b", is_open=True, license_type="permissive"),
            Model(id="c", display_name="C", provider_model_id="c", is_open=True, license_type="permissive"),
            Model(id="d", display_name="D", provider_model_id="d", is_open=True, license_type="permissive"),
        ]
        session.add_all(models)
        prompt = Prompt(participant_id=1, text="x", category="coding")
        session.add(prompt)
        session.flush()
        session.add(Answer(prompt_id=prompt.id, model_id="a"))
        session.commit()
        selected = select_models(session, prompt, session.exec(select(Model)).all())
    assert selected[0].is_baseline
    assert {model.id for model in selected[1:]} == {"b", "c", "d"}

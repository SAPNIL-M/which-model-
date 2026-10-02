import json

from sqlmodel import Session, create_engine

from app.models import Answer, Model, Participant, Pick, Prompt
from app.services.stats import calculate_stats


def test_stats_pairwise_and_open_closed():
    engine = create_engine("sqlite://")
    Participant.metadata.create_all(engine)
    Prompt.metadata.create_all(engine)
    Model.metadata.create_all(engine)
    Answer.metadata.create_all(engine)
    Pick.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Model(id="open", display_name="Open", provider_model_id="open", is_open=True, license_type="permissive"),
            Model(id="base", display_name="Base", provider_model_id="base", is_open=False, license_type="closed", is_baseline=True),
        ])
        prompt = Prompt(participant_id=1, text="x", category="coding")
        session.add(prompt)
        session.flush()
        first = Answer(prompt_id=prompt.id, model_id="open", text="a", status="done")
        second = Answer(prompt_id=prompt.id, model_id="base", text="b", status="done")
        session.add_all([first, second])
        session.flush()
        session.add(Pick(prompt_id=prompt.id, participant_id=1, shown_answer_ids=json.dumps([first.id, second.id]), chosen_answer_id=first.id, outcome="picked"))
        session.commit()
        stats = calculate_stats(session)
    assert stats["models"]["open"]["win_rate"] == 1
    assert stats["open_vs_closed"] == {"open_wins": 1, "n": 1, "share": 1}

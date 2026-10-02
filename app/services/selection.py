from collections import Counter

from sqlmodel import Session, select

from app.models import Answer, Job, Model, Prompt


def select_models(session: Session, prompt: Prompt, models: list[Model]) -> list[Model]:
    baseline = next((model for model in models if model.is_baseline), None)
    open_models = [model for model in models if model.is_open]
    if baseline is None:
        raise ValueError("At least one baseline model must be configured")
    usage = Counter(
        model_id
        for row in session.exec(
            select(Answer.model_id).join(Prompt, Prompt.id == Answer.prompt_id)
        )
        for model_id in [row]
    )
    return [baseline, *sorted(open_models, key=lambda model: (usage[model.id], model.id))[:3]]


def queue_prompt(session: Session, prompt: Prompt, models: list[Model]) -> list[Model]:
    selected = select_models(session, prompt, models)
    for model in selected:
        session.add(Answer(prompt_id=prompt.id, model_id=model.id))
        session.add(Job(prompt_id=prompt.id, model_id=model.id))
    return selected

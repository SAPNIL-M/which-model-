import json
from collections import defaultdict
from statistics import median

from sqlmodel import Session, select

from app.models import Answer, Model, Pick, Prompt


def calculate_stats(session: Session, participant_id: int | None = None) -> dict:
    prompt_query = select(Prompt)
    if participant_id is not None:
        prompt_query = prompt_query.where(Prompt.participant_id == participant_id)
    prompts = {prompt.id: prompt for prompt in session.exec(prompt_query)}
    picks = session.exec(select(Pick).where(Pick.prompt_id.in_(prompts))).all() if prompts else []
    answers = session.exec(select(Answer).where(Answer.prompt_id.in_(prompts))).all() if prompts else []
    models = {model.id: model for model in session.exec(select(Model))}
    by_answer = {answer.id: answer for answer in answers}
    by_model = defaultdict(lambda: {
        "shown": 0, "chosen": 0, "wins": 0, "comparisons": 0,
        "latencies": [], "tokens": [],
    })
    categories = defaultdict(lambda: defaultdict(lambda: {"wins": 0, "comparisons": 0, "chosen": 0, "shown": 0}))
    none_good = 0
    open_baseline_eligible = 0
    open_baseline_wins = 0

    for pick in picks:
        shown_ids = json.loads(pick.shown_answer_ids)
        shown = [by_answer[answer_id] for answer_id in shown_ids if answer_id in by_answer]
        prompt = prompts[pick.prompt_id]
        chosen = by_answer.get(pick.chosen_answer_id)
        for answer in shown:
            row = by_model[answer.model_id]
            row["shown"] += 1
            row["latencies"].append(answer.latency_ms) if answer.latency_ms is not None else None
            row["tokens"].append(answer.tokens_out) if answer.tokens_out is not None else None
            categories[prompt.category][answer.model_id]["shown"] += 1
        if pick.outcome == "none_good" or chosen is None:
            none_good += 1
            continue
        by_model[chosen.model_id]["chosen"] += 1
        categories[prompt.category][chosen.model_id]["chosen"] += 1
        for answer in shown:
            if answer.id == chosen.id:
                continue
            by_model[chosen.model_id]["wins"] += 1
            by_model[chosen.model_id]["comparisons"] += 1
            by_model[answer.model_id]["comparisons"] += 1
            categories[prompt.category][chosen.model_id]["wins"] += 1
            categories[prompt.category][chosen.model_id]["comparisons"] += 1
            categories[prompt.category][answer.model_id]["comparisons"] += 1
        baseline = next((answer for answer in shown if models.get(answer.model_id) and models[answer.model_id].is_baseline), None)
        open_answers = [answer for answer in shown if models.get(answer.model_id) and models[answer.model_id].is_open]
        if baseline and open_answers:
            open_baseline_eligible += 1
            if models[chosen.model_id].is_open:
                open_baseline_wins += 1

    model_stats = {}
    for model_id, model in models.items():
        row = by_model[model_id]
        comparisons = row["comparisons"]
        model_stats[model_id] = {
            "model_id": model_id,
            "display_name": model.display_name,
            "is_open": model.is_open,
            "license_type": model.license_type,
            "shown": row["shown"],
            "chosen": row["chosen"],
            "pick_rate": row["chosen"] / row["shown"] if row["shown"] else 0,
            "pairwise_wins": row["wins"],
            "comparisons": comparisons,
            "small_sample": comparisons < 10,
            "win_rate": row["wins"] / comparisons if comparisons else 0,
            "median_latency_ms": median(row["latencies"]) if row["latencies"] else None,
            "median_tokens_out": median(row["tokens"]) if row["tokens"] else None,
        }
    category_stats = {}
    for category, rows in categories.items():
        category_stats[category] = {
            model_id: {
                **value,
                "win_rate": value["wins"] / value["comparisons"] if value["comparisons"] else 0,
                "small_sample": value["comparisons"] < 10,
            }
            for model_id, value in rows.items()
        }
    return {
        "models": model_stats,
        "categories": category_stats,
        "none_good": none_good,
        "picked": len(picks) - none_good,
        "none_good_rate": none_good / len(picks) if picks else 0,
        "open_vs_closed": {
            "open_wins": open_baseline_wins,
            "n": open_baseline_eligible,
            "share": open_baseline_wins / open_baseline_eligible if open_baseline_eligible else 0,
        },
    }

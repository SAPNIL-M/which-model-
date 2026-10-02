from pathlib import Path
import os
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ModelConfig:
    id: str
    display_name: str
    kind: str
    provider_model_id: str
    api_key_env: str
    is_open: bool
    license_type: str
    base_url: str | None = None
    license_note: str | None = None
    is_baseline: bool = False
    live_enabled: bool = False


@dataclass(frozen=True)
class AppConfig:
    database_url: str
    session_secret: str
    daily_call_cap: int
    generation_enabled: bool
    generation: dict
    models: tuple[ModelConfig, ...]
    invite_codes: tuple[str, ...]


def load_config(path: Path | None = None, environ: dict[str, str] | None = None) -> AppConfig:
    load_dotenv()
    env = os.environ if environ is None else environ
    config_path = path or ROOT / "config" / "models.yaml"
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    models = tuple(ModelConfig(**model) for model in raw.get("models", []))
    if not models:
        raise ValueError("config/models.yaml must define at least one model")

    for model in models:
        if model.kind not in {"openai_compatible", "gemini"}:
            raise ValueError(f"Unsupported provider kind for {model.id}: {model.kind}")
        if model.live_enabled and not env.get(model.api_key_env) and not (
            model.kind == "openai_compatible" and model.base_url == "http://localhost:11434/v1"
        ):
            raise ValueError(
                f"Missing {model.api_key_env} for live-enabled model {model.id}"
            )
        if model.kind == "openai_compatible" and not model.base_url:
            raise ValueError(f"Missing base_url for model {model.id}")

    raw_database_url = env.get("DATABASE_URL", "sqlite:///./whichmodel.db")
    if raw_database_url.startswith("postgres://"):
        database_url = raw_database_url.replace("postgres://", "postgresql://", 1)
    else:
        database_url = raw_database_url

    return AppConfig(
        database_url=database_url,
        session_secret=env.get("SESSION_SECRET", ""),
        daily_call_cap=int(env.get("DAILY_CALL_CAP", "100")),
        generation_enabled=env.get("GENERATION_ENABLED", "true").lower() == "true",
        generation=raw.get("generation", {}),
        models=models,
        invite_codes=tuple(code.strip() for code in env.get("INVITE_CODES", "").split(",") if code.strip()),
    )

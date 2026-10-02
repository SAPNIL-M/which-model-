from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    display_name: str
    invite_code_used: str
    public_profile: bool = False
    consent_third_party: bool = False
    created_at: datetime = Field(default_factory=now)


class Prompt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    participant_id: int = Field(index=True)
    text: str
    category: str
    share_publicly: bool = False
    created_at: datetime = Field(default_factory=now)


class Model(SQLModel, table=True):
    id: str = Field(primary_key=True)
    display_name: str
    provider_model_id: str
    is_open: bool
    license_type: str
    is_baseline: bool = False


class Answer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_id: int = Field(index=True)
    model_id: str = Field(index=True)
    text: Optional[str] = None
    latency_ms: Optional[int] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    status: str = "pending"
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=now)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_id: int = Field(index=True)
    model_id: str = Field(index=True)
    status: str = "queued"
    attempts: int = 0
    last_error: Optional[str] = None
    updated_at: datetime = Field(default_factory=now)


class Pick(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_id: int = Field(index=True)
    participant_id: int = Field(index=True)
    shown_answer_ids: str
    chosen_answer_id: Optional[int] = None
    outcome: str
    created_at: datetime = Field(default_factory=now)

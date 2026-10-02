import asyncio
import os
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.config import AppConfig, ModelConfig
from app.db import engine
from app.models import Answer, Job, Model, Prompt
from app.providers.base import Provider
from app.providers.gemini import GeminiProvider
from app.providers.openai_compat import OpenAICompatibleProvider


def provider_for(model: ModelConfig) -> Provider:
    key = os.environ.get(model.api_key_env, "")
    if model.kind == "gemini":
        return GeminiProvider(key, model.provider_model_id)
    return OpenAICompatibleProvider(model.base_url or "", key, model.provider_model_id)


class GenerationWorker:
    def __init__(self, config: AppConfig):
        self.config = config
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.limits = {
            "openai_compatible": asyncio.Semaphore(3),
            "gemini": asyncio.Semaphore(2),
        }
        self.calls_today = 0

    async def start(self):
        with Session(engine) as session:
            for job in session.exec(select(Job).where(Job.status == "running")):
                job.status = "queued"
                job.updated_at = datetime.now(timezone.utc)
            session.commit()
        self.task = asyncio.create_task(self.run())

    async def stop(self):
        self.stop_event.set()
        if self.task:
            await self.task

    async def run(self):
        while not self.stop_event.is_set():
            if self.config.generation_enabled and self.calls_today < self.config.daily_call_cap:
                await self.process_one()
            await asyncio.sleep(0.1)

    async def process_one(self):
        with Session(engine) as session:
            job = session.exec(select(Job).where(Job.status == "queued").order_by(Job.id)).first()
            if not job:
                return
            model_config = next((m for m in self.config.models if m.id == job.model_id), None)
            prompt = session.get(Prompt, job.prompt_id)
            answer = session.exec(
                select(Answer).where(
                    Answer.prompt_id == job.prompt_id, Answer.model_id == job.model_id
                )
            ).first()
            if not model_config or not prompt or not answer:
                job.status = "failed"
                job.last_error = "Job references missing configuration or data"
                session.commit()
                return
            job.status = "running"
            job.attempts += 1
            job.updated_at = datetime.now(timezone.utc)
            session.commit()

        try:
            async with self.limits[model_config.kind]:
                result = await provider_for(model_config).generate(
                    self.config.generation.get("system_prompt", ""),
                    prompt.text,
                    self.config.generation.get("temperature", 0.3),
                    self.config.generation.get("max_tokens", 800),
                )
            with Session(engine) as session:
                job = session.get(Job, job.id)
                answer = session.get(Answer, answer.id)
                answer.text = result.text
                answer.latency_ms = result.latency_ms
                answer.tokens_in = result.tokens_in
                answer.tokens_out = result.tokens_out
                answer.status = "done"
                job.status = "done"
                job.updated_at = datetime.now(timezone.utc)
                session.commit()
        except Exception as exc:
            with Session(engine) as session:
                job = session.get(Job, job.id)
                answer = session.get(Answer, answer.id)
                answer.status = "error"
                answer.error = str(exc)
                job.status = "failed"
                job.last_error = str(exc)
                job.updated_at = datetime.now(timezone.utc)
                session.commit()
        self.calls_today += 1

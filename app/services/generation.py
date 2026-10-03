import asyncio
import os
import time
from datetime import datetime, timezone

from sqlmodel import Session, func, select

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


def count_calls_today() -> int:
    midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    with Session(engine) as session:
        return session.exec(
            select(func.count())
            .select_from(Job)
            .where(Job.status.in_(("done", "failed")), Job.updated_at >= midnight)
        ).one()


class GenerationWorker:
    def __init__(self, config: AppConfig):
        self.config = config
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.running_tasks: set[asyncio.Task] = set()
        self.limits = {
            "openai_compatible": asyncio.Semaphore(3),
            "groq": asyncio.Semaphore(1),
            "gemini": asyncio.Semaphore(2),
        }
        self.next_slot: dict[str, float] = {}
        self.max_concurrent_jobs = 6

    def is_generation_available(self) -> bool:
        if not self.config.generation_enabled:
            return False
        return count_calls_today() < self.config.daily_call_cap

    async def start(self):
        with Session(engine) as session:
            for job in session.exec(select(Job).where(Job.status == "running")):
                job.status = "queued"
                job.updated_at = datetime.now(timezone.utc)
            session.commit()
        self.task = asyncio.create_task(self.run())

    async def stop(self):
        self.stop_event.set()
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
        if self.task:
            await self.task

    async def run(self):
        while not self.stop_event.is_set():
            # Clean up finished background tasks
            self.running_tasks = {t for t in self.running_tasks if not t.done()}

            launched = False
            try:
                if self.is_generation_available() and len(self.running_tasks) < self.max_concurrent_jobs:
                    launched = await self.try_launch_next_job()
            except Exception:
                await self.requeue_running_jobs()

            if launched:
                await asyncio.sleep(0.05)
            else:
                await asyncio.sleep(1.0)

    async def requeue_running_jobs(self):
        with Session(engine) as session:
            for job in session.exec(select(Job).where(Job.status == "running")):
                job.status = "queued"
                job.last_error = "Worker recovered after an unexpected error"
                job.updated_at = datetime.now(timezone.utc)
            session.commit()

    async def try_launch_next_job(self) -> bool:
        now = time.monotonic()
        with Session(engine) as session:
            # Find eligible models: not in cooldown
            ready_model_ids = [
                m.id for m in self.config.models
                if m.live_enabled and self.next_slot.get(m.id, 0.0) <= now
            ]
            if not ready_model_ids:
                return False

            job = session.exec(
                select(Job)
                .where(Job.status == "queued", Job.model_id.in_(ready_model_ids))
                .order_by(Job.id)
            ).first()

            if not job:
                return False

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
                return False

            job_id = job.id
            answer_id = answer.id
            prompt_text = prompt.text
            job.status = "running"
            job.attempts += 1
            job.updated_at = datetime.now(timezone.utc)
            session.commit()

            # Schedule next slot for this model based on RPM
            if model_config.rpm and model_config.rpm > 0:
                self.next_slot[model_config.id] = now + (60.0 / model_config.rpm)

        # Launch execution as concurrent background task
        task = asyncio.create_task(
            self.execute_job(job_id, answer_id, model_config, prompt_text)
        )
        self.running_tasks.add(task)
        return True

    async def execute_job(self, job_id: int, answer_id: int, model_config: ModelConfig, prompt_text: str):
        limit_key = "groq" if "api.groq.com" in (model_config.base_url or "") else model_config.kind
        semaphore = self.limits.get(limit_key, self.limits["openai_compatible"])

        try:
            async with semaphore:
                result = await asyncio.wait_for(
                    provider_for(model_config).generate(
                        self.config.generation.get("system_prompt", ""),
                        prompt_text,
                        self.config.generation.get("temperature", 0.3),
                        self.config.generation.get("max_tokens", 800),
                    ),
                    timeout=75,
                )
            with Session(engine) as session:
                job = session.get(Job, job_id)
                answer = session.get(Answer, answer_id)
                if answer:
                    answer.text = result.text
                    answer.latency_ms = result.latency_ms
                    answer.tokens_in = result.tokens_in
                    answer.tokens_out = result.tokens_out
                    answer.status = "done"
                    answer.error = None
                if job:
                    job.status = "done"
                    job.updated_at = datetime.now(timezone.utc)
                session.commit()
        except Exception as exc:
            with Session(engine) as session:
                job = session.get(Job, job_id)
                answer = session.get(Answer, answer_id)
                # If under max attempts, requeue for retry
                if job and job.attempts < 3:
                    job.status = "queued"
                    job.last_error = f"Retrying after error: {exc}"
                    job.updated_at = datetime.now(timezone.utc)
                else:
                    if answer:
                        answer.status = "error"
                        answer.error = str(exc)
                    if job:
                        job.status = "failed"
                        job.last_error = str(exc)
                        job.updated_at = datetime.now(timezone.utc)
                session.commit()

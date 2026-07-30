"""
Job queue — فایل JSON روی /tmp
Bot API جاب می‌نویسه، Telethon worker می‌خونه و اجرا می‌کنه.

Job schema:
{
    "id": "uuid4",
    "type": "view" | "reaction",
    "status": "pending" | "running" | "done" | "failed",
    "user_id": int,
    "chat_id": int,
    "message_id": int,          ← پیام progress که باید edit بشه
    "post_link": str,
    "count": int,
    "views_done": int,
    "error": str | null,
    "created_at": float
}
"""

import json
import os
import time
import uuid
import asyncio
from typing import Optional
from config import Config

_LOCK = asyncio.Lock()

def _load() -> list[dict]:
    if not os.path.exists(Config.JOB_QUEUE_PATH):
        return []
    with open(Config.JOB_QUEUE_PATH, "r") as f:
        return json.load(f)

def _save(jobs: list[dict]) -> None:
    with open(Config.JOB_QUEUE_PATH, "w") as f:
        json.dump(jobs, f, indent=2)

async def push_job(
    job_type: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    post_link: str,
    count: int,
) -> str:
    async with _LOCK:
        jobs = _load()
        job_id = str(uuid.uuid4())[:8]
        jobs.append({
            "id": job_id,
            "type": job_type,
            "status": "pending",
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "post_link": post_link,
            "count": count,
            "views_done": 0,
            "error": None,
            "created_at": time.time(),
        })
        _save(jobs)
        return job_id

async def get_pending_job() -> Optional[dict]:
    async with _LOCK:
        jobs = _load()
        for job in jobs:
            if job["status"] == "pending":
                job["status"] = "running"
                _save(jobs)
                return job
        return None

async def update_job(job_id: str, **kwargs) -> None:
    async with _LOCK:
        jobs = _load()
        for job in jobs:
            if job["id"] == job_id:
                job.update(kwargs)
        _save(jobs)

async def finish_job(job_id: str, views_done: int, error: Optional[str] = None) -> None:
    await update_job(
        job_id,
        status="done" if not error else "failed",
        views_done=views_done,
        error=error,
    )

def get_all_jobs() -> list[dict]:
    return _load()

def clear_done_jobs() -> int:
    jobs = _load()
    remaining = [j for j in jobs if j["status"] not in ("done", "failed")]
    removed = len(jobs) - len(remaining)
    _save(remaining)
    return removed

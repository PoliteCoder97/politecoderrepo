"""FastAPI app: scheduled README commits via PyGithub + APScheduler."""

from __future__ import annotations

import asyncio
import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from github_service import append_readme_and_push

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PoliteCoder README auto-commit", version="1.0.0")

scheduler = AsyncIOScheduler()


def _run_scheduled_commit() -> None:
    try:
        result = append_readme_and_push()
        if result.get("ok"):
            logger.info("Scheduled commit finished: %s", result.get("timestamp"))
        else:
            logger.warning("Scheduled commit skipped or failed: %s", result.get("error"))
    except Exception:
        logger.exception("Scheduled job raised unexpectedly; app continues")


@app.on_event("startup")
async def startup() -> None:
    load_dotenv()

    tz_name = os.environ.get("SCHEDULE_TIMEZONE", "UTC")
    hour = int(os.environ.get("SCHEDULE_HOUR", "3"))
    minute = int(os.environ.get("SCHEDULE_MINUTE", "0"))

    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown timezone '%s'; falling back to UTC", tz_name)
        tz = ZoneInfo("UTC")

    scheduler.configure(timezone=tz)
    scheduler.add_job(
        _run_scheduled_commit,
        CronTrigger(hour=hour, minute=minute, timezone=tz),
        id="daily_readme_commit",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: daily at %02d:%02d (%s)", hour, minute, tz.key)


@app.on_event("shutdown")
async def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/force-commit", response_model=None)
async def force_commit():
    try:
        result = await asyncio.to_thread(append_readme_and_push)
    except Exception as e:
        logger.exception("force-commit: unexpected error")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)},
        )

    if result.get("ok"):
        return {"status": "success", **result}

    status_code = 502 if result.get("status") is not None else 400
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", **result},
    )

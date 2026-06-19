"""
Pipeline management endpoints — samo za researcher/admin.
"""

import logging
from typing import Optional

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException

from api.deps import researcher
from config import settings
from pipeline.tasks import (
    REDIS_KEY_BATCH_ID,
    REDIS_KEY_BATCH_DATE,
    submit_nightly_batch,
    check_and_process_batch,
    run_batch_for_articles,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


@router.get("/status")
async def pipeline_status(current_user=researcher):
    """Status tekuceg ili poslednjeg batch-a."""
    r = _redis()
    batch_id = r.get(REDIS_KEY_BATCH_ID)
    batch_date = r.get(REDIS_KEY_BATCH_DATE)

    if not batch_id:
        return {"status": "idle", "batch_id": None, "batch_date": batch_date}

    try:
        from pipeline.batch_api import get_batch_status
        info = get_batch_status(batch_id)
        return {"status": info["status"], "batch_id": batch_id, "batch_date": batch_date, **info}
    except Exception as e:
        return {"status": "error", "batch_id": batch_id, "error": str(e)}


@router.post("/submit")
async def trigger_batch_submit(current_user=researcher):
    """
    Rucno pokretanje nocnog batch-a.
    Submituje sve neprocesirane clanke Anthropic Batch API-ju.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY nije konfigurisan")

    task = submit_nightly_batch.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/process")
async def trigger_batch_process(current_user=researcher):
    """
    Rucno pokretanje obrade vec zavrsenog batch-a.
    """
    task = check_and_process_batch.delay()
    return {"task_id": task.id, "status": "queued"}


@router.post("/analyze-articles")
async def analyze_specific_articles(
    article_ids: list[int],
    current_user=researcher,
):
    """
    Rucna analiza specificnih clanaka (dev/re-analiza).
    Sinhrono, bez Batch API-ja — pogodan za male skupove (<10 clanaka).
    """
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY nije konfigurisan")
    if len(article_ids) > 20:
        raise HTTPException(status_code=400, detail="Max 20 clanaka odjednom za direktnu analizu")

    task = run_batch_for_articles.delay(article_ids)
    return {"task_id": task.id, "status": "queued", "article_ids": article_ids}

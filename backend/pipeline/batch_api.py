"""
Anthropic Batch API wrapper.
Batch API je 50% jeftiniji od standardnog API-ja, ali asinhroni (do 24h).
"""

import json
import logging
from typing import Optional

import anthropic

from config import settings
from pipeline.prompts import SYSTEM_PROMPT, build_mvp_prompt, build_system

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "1.0"
MAX_TOKENS_PER_REQUEST = 2500


def _strip_markdown(text: str) -> str:
    """Uklanja ```json ... ``` wrapper ako model vrati JSON u code bloku."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Izbaci prvu (```json) i poslednju (```) liniju
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return text


def _make_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def submit_analysis_batch(articles: list[dict], system=None) -> str:
    """
    Submituje batch AI analize za listu pripremljenih clanaka.
    articles: lista dict-ova iz pipeline.prepare.prepare_article()
    system: Anthropic `system` vrednost (string ili lista blokova sa cache_control).
            Ako je None, koristi se osnovni SYSTEM_PROMPT (bez framing kataloga).

    Vraca batch_id koji se cuva za kasniji retrieval rezultata.
    """
    client = _make_client()
    system_val = system if system is not None else SYSTEM_PROMPT

    requests = [
        {
            "custom_id": f"article_{article['article_id']}",
            "params": {
                "model": settings.ANTHROPIC_MODEL,
                "max_tokens": MAX_TOKENS_PER_REQUEST,
                "system": system_val,
                "messages": [{"role": "user", "content": build_mvp_prompt(article)}],
            },
        }
        for article in articles
    ]

    batch = client.messages.batches.create(requests=requests)
    logger.info(
        "Batch submitovan: id=%s, requests=%d, status=%s",
        batch.id,
        len(requests),
        batch.processing_status,
    )
    return batch.id


def get_batch_status(batch_id: str) -> dict:
    """
    Vraca status batch-a i broj procesiranih zahteva.
    processing_status: 'in_progress' | 'ended' | 'canceling' | 'expired'
    """
    client = _make_client()
    batch = client.messages.batches.retrieve(batch_id)
    return {
        "batch_id": batch.id,
        "status": batch.processing_status,
        "request_counts": {
            "processing": batch.request_counts.processing,
            "succeeded": batch.request_counts.succeeded,
            "errored": batch.request_counts.errored,
            "canceled": batch.request_counts.canceled,
            "expired": batch.request_counts.expired,
        },
        "ended_at": batch.ended_at.isoformat() if batch.ended_at else None,
    }


def iter_batch_results(batch_id: str):
    """
    Generator koji iterira kroz rezultate zavrsenog batch-a.
    Yield-uje (article_id: int, result: dict | None, error: str | None)
    """
    client = _make_client()

    for result in client.messages.batches.results(batch_id):
        custom_id = result.custom_id
        try:
            article_id = int(custom_id.replace("article_", ""))
        except ValueError:
            logger.warning("Nepoznati custom_id: %s", custom_id)
            continue

        if result.result.type == "succeeded":
            raw_text = result.result.message.content[0].text
            try:
                parsed = json.loads(_strip_markdown(raw_text))
                yield article_id, parsed, None
            except json.JSONDecodeError as e:
                logger.error(
                    "JSON parse greska za article %d: %s | raw: %s",
                    article_id,
                    e,
                    raw_text[:200],
                )
                yield article_id, None, f"JSON parse error: {e}"

        elif result.result.type == "errored":
            error_msg = result.result.error.type
            logger.error("Batch greska za article %d: %s", article_id, error_msg)
            yield article_id, None, error_msg

        else:
            yield article_id, None, f"Unexpected result type: {result.result.type}"

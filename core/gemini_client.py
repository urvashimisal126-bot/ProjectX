"""
Google Gemini API client wrapper for UrbanLens.
Uses google-genai SDK with structured output (pydantic validation),
caching in SQLite, exponential backoff, and audit logging.
"""

from __future__ import annotations

import hashlib
import io
import json
import time
from typing import Any, Type, TypeVar
from PIL import Image

from pydantic import BaseModel, ValidationError

from core.config import GEMINI_API_KEY, GEMINI_MODEL
from core.db import get_conn
from core.audit import log_audit

T = TypeVar("T", bound=BaseModel)

_CLIENT = None


def get_client():
    """Return cached genai.Client instance, or None if no API key configured."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    api_key = GEMINI_API_KEY
    if not api_key or api_key.startswith("your_") or len(api_key.strip()) < 8:
        return None

    try:
        from google import genai
        _CLIENT = genai.Client(api_key=api_key)
        return _CLIENT
    except Exception:
        return None


def _compute_cache_key(prompt: str, model: str, image_bytes: bytes | None = None) -> str:
    hasher = hashlib.sha256()
    hasher.update(model.encode("utf-8"))
    hasher.update(prompt.encode("utf-8"))
    if image_bytes:
        hasher.update(image_bytes)
    return hasher.hexdigest()


def get_cached_response(cache_key: str) -> str | None:
    """Retrieve cached JSON response if exists."""
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT response_json FROM gemini_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row:
                return row["response_json"]
    except Exception:
        pass
    return None


def save_cached_response(cache_key: str, model: str, feature: str, response_json: str) -> None:
    """Save JSON response to cache."""
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO gemini_cache (cache_key, model, feature, response_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cache_key, model, feature, response_json, now),
            )
    except Exception:
        pass


def generate_json(
    prompt: str,
    schema: Type[T],
    image: Image.Image | None = None,
    feature: str = "general",
    model: str | None = None,
    actor: dict | None = None,
) -> T | None:
    """
    Call Gemini with structured output, validated against `schema` (pydantic BaseModel).
    Returns parsed instance of schema, or None on failure/unavailable.
    """
    client = get_client()
    if client is None:
        return None

    target_model = model or GEMINI_MODEL
    actor_user = (actor or {}).get("username", "system")
    actor_role = (actor or {}).get("role", "system")

    # Serialize image if provided
    img_bytes: bytes | None = None
    if image is not None:
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=85)
        img_bytes = buf.getvalue()

    cache_key = _compute_cache_key(prompt, target_model, img_bytes)
    cached = get_cached_response(cache_key)
    if cached:
        try:
            return schema.model_validate_json(cached)
        except ValidationError:
            pass

    # Build contents
    contents: list[Any] = [prompt]
    if image is not None:
        contents.append(image)

    max_retries = 2
    delay = 1.0
    start_time = time.perf_counter()

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=target_model,
                contents=contents,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raw_text = response.text or "{}"
            validated_obj = schema.model_validate_json(raw_text)

            # Save to cache
            save_cached_response(cache_key, target_model, feature, raw_text)

            # Audit log
            log_audit(
                actor_user,
                actor_role,
                "ai_call",
                None,
                f"feature={feature} model={target_model} latency={latency_ms}ms status=success",
            )
            return validated_obj

        except ValidationError as val_err:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            log_audit(
                actor_user,
                actor_role,
                "ai_call",
                None,
                f"feature={feature} model={target_model} latency={latency_ms}ms status=validation_error",
            )
            return None

        except Exception as exc:
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
            else:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                err_msg = str(exc)[:80].replace("\n", " ")
                log_audit(
                    actor_user,
                    actor_role,
                    "ai_call",
                    None,
                    f"feature={feature} model={target_model} latency={latency_ms}ms status=failed error={err_msg}",
                )
                return None

    return None

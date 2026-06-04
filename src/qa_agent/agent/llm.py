"""Thin GLM client (OpenAI-compatible). Single point to swap providers."""
from __future__ import annotations

import json
import logging
from typing import Any
from openai import OpenAI

from ..config import settings

log = logging.getLogger(__name__)


def _client() -> OpenAI:
    if not settings.glm_api_key:
        raise RuntimeError("GLM_API_KEY not set; copy .env.example to .env and fill it in.")
    return OpenAI(api_key=settings.glm_api_key, base_url=settings.glm_base_url)


def chat_json(messages: list[dict[str, str]], model: str | None = None, temperature: float = 0.1, max_retries: int = 2) -> dict[str, Any]:
    """Chat with JSON output. Validates and retries on parse failure."""
    model = model or settings.glm_model
    cli = _client()
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = cli.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except json.JSONDecodeError as e:
            last_err = e
            log.warning("json parse failed (attempt %d): %s", attempt + 1, e)
            messages = messages + [{"role": "user", "content": "你刚才的输出不是合法 JSON，请严格按要求只输出一个 JSON 对象，不要任何解释。"}]
        except Exception as e:
            last_err = e
            log.warning("llm call failed (attempt %d): %s", attempt + 1, e)
    raise RuntimeError(f"LLM JSON call failed after {max_retries + 1} attempts: {last_err}")

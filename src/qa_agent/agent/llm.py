"""LLM client. Supports two protocols at the same base host:

- openai:    /api/paas/v4  (requires paid credits)
- anthropic: /api/anthropic (used by ZhipuAI coding plan)

Switch via GLM_PROTOCOL env var.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..config import settings

log = logging.getLogger(__name__)

_JSON_OBJ_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        # strip ```json ... ``` fence
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_OBJ_RE.search(text)
        if m:
            return json.loads(m.group(0))
        raise


# ---------- openai protocol ----------
def _chat_openai(messages: list[dict], model: str, temperature: float) -> str:
    from openai import OpenAI
    cli = OpenAI(api_key=settings.glm_api_key, base_url=settings.glm_base_url)
    resp = cli.chat.completions.create(
        model=model, messages=messages, temperature=temperature,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "{}"


# ---------- anthropic protocol ----------
def _chat_anthropic(messages: list[dict], model: str, temperature: float) -> str:
    from anthropic import Anthropic
    cli = Anthropic(api_key=settings.glm_api_key, base_url=settings.glm_base_url)

    # split: anthropic SDK takes `system` as top-level kw, not inside messages
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    convo = [m for m in messages if m["role"] != "system"]
    # inject "must output JSON" reminder into system
    system = "\n\n".join(system_parts) + "\n\n你必须只输出一个 JSON 对象，不要 markdown 代码块，不要任何解释。"

    resp = cli.messages.create(
        model=model,
        max_tokens=2048,
        temperature=temperature,
        system=system,
        messages=[{"role": m["role"], "content": m["content"]} for m in convo],
    )
    # extract text from content blocks
    parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts) or "{}"


def chat_json(messages: list[dict[str, str]], model: str | None = None,
              temperature: float = 0.1, max_retries: int = 2) -> dict[str, Any]:
    """Chat with JSON output. Validates and retries on parse failure."""
    if not settings.glm_api_key:
        raise RuntimeError("GLM_API_KEY not set; copy .env.example to .env and fill it in.")
    model = model or settings.glm_model
    proto = settings.glm_protocol.lower()
    backend = _chat_anthropic if proto == "anthropic" else _chat_openai

    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            raw = backend(messages, model, temperature)
            return _extract_json(raw)
        except json.JSONDecodeError as e:
            last_err = e
            log.warning("json parse failed (attempt %d) raw=%r", attempt + 1, raw[:200] if 'raw' in dir() else None)
            messages = messages + [{"role": "user", "content": "请严格输出一个 JSON 对象，不要 markdown 围栏，不要任何解释。"}]
        except Exception as e:
            last_err = e
            log.warning("llm call failed (attempt %d): %s", attempt + 1, e)
    raise RuntimeError(f"LLM JSON call failed after {max_retries + 1} attempts: {last_err}")

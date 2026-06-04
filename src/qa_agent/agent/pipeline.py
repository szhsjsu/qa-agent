"""End-to-end agent: retrieve → generate → self-check → finalize."""
from __future__ import annotations

import logging
import time
from typing import Any

from ..config import settings
from ..index.builder import IndexBundle
from ..retrieval import retrieve, RetrievalResult
from ..schema import AnswerResult, Citation
from . import prompts
from .llm import chat_json

log = logging.getLogger(__name__)


def _format_context(results: list[RetrievalResult]) -> str:
    parts: list[str] = []
    for r in results:
        c = r.chunk
        header = f"[p{c['page']} | id={c['chunk_id']} | type={c['type']}"
        if c.get("clause_id"):
            header += f" | {c['clause_id']}"
        header += "]"
        body = c["text"]
        if c.get("type") == "table" and c.get("table_md"):
            # already inside text but emphasize
            body = body
        parts.append(f"{header}\n{body}")
    return "\n\n".join(parts)


def _early_refuse(results: list[RetrievalResult]) -> bool:
    if not results:
        return True
    top = results[0].score
    return top < settings.min_score_for_answer


def answer_question(bundle: IndexBundle, question: str) -> AnswerResult:
    t0 = time.perf_counter()

    results = retrieve(
        bundle, question,
        top_k_recall=settings.top_k_recall,
        top_k_final=settings.top_k_final,
    )

    # Early refusal: nothing recalled or top-1 too weak
    if _early_refuse(results):
        return AnswerResult(
            question=question,
            answer="无法从文档中找到答案",
            citations=[],
            refused=True,
            confidence="high",
            grounded=False,
            reason=f"检索置信过低（top-score={results[0].score if results else 0:.3f} < {settings.min_score_for_answer}）",
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    ctx = _format_context(results)
    gen = chat_json(
        [
            {"role": "system", "content": prompts.ANSWER_SYSTEM},
            {"role": "user", "content": prompts.ANSWER_USER_TMPL.format(question=question, context=ctx)},
        ],
        model=settings.glm_model,
    )

    raw_answer: str = gen.get("answer", "").strip()
    citations_raw: list[dict] = gen.get("citations", []) or []
    used_ids: list[str] = gen.get("used_chunk_ids", []) or []

    citations = [
        Citation(page=int(c.get("page", 0)), quote=str(c.get("quote", "")).strip())
        for c in citations_raw
        if c.get("page")
    ]

    if "无法从文档中找到答案" in raw_answer or not raw_answer:
        return AnswerResult(
            question=question,
            answer="无法从文档中找到答案",
            citations=[],
            refused=True,
            confidence="high",
            grounded=False,
            reason="生成模型自判无依据",
            used_chunk_ids=used_ids,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    # ---- self-check ----
    evidence_text = "\n\n".join(
        f"[p{r.chunk['page']}] {r.chunk['text'][:500]}"
        for r in results
        if not used_ids or r.chunk["chunk_id"] in used_ids or True
    )
    verify = chat_json(
        [
            {"role": "system", "content": prompts.VERIFY_SYSTEM},
            {"role": "user", "content": prompts.VERIFY_USER_TMPL.format(
                question=question, answer=raw_answer, evidence=evidence_text
            )},
        ],
        model=settings.glm_verify_model,
        temperature=0.0,
    )
    grounded = bool(verify.get("grounded", False))
    refuse = bool(verify.get("refuse", False))
    risk = str(verify.get("hallucination_risk", "medium"))

    if refuse or not grounded:
        return AnswerResult(
            question=question,
            answer="无法从文档中找到答案",
            citations=[],
            refused=True,
            confidence="medium",
            grounded=False,
            reason=f"自检拒答：{verify.get('reason', '依据不足')}",
            used_chunk_ids=used_ids,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    confidence = {"low": "high", "medium": "medium", "high": "low"}.get(risk, "medium")  # invert risk → confidence

    return AnswerResult(
        question=question,
        answer=raw_answer,
        citations=citations,
        refused=False,
        confidence=confidence,  # type: ignore
        grounded=True,
        reason=verify.get("reason"),
        used_chunk_ids=used_ids,
        latency_ms=(time.perf_counter() - t0) * 1000,
    )

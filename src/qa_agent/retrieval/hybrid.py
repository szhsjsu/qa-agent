"""Hybrid retrieval: BM25 + dense vector → RRF fusion."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..index.builder import IndexBundle, _tokenize_zh


CLAUSE_RE = re.compile(r"第\s*([0-9一二三四五六七八九十百零]+)\s*条|(\d+(?:\.\d+){0,3})")
ZH_NUM = "零一二三四五六七八九十百"


def _expand_query(q: str) -> list[str]:
    """Generate query variants to bridge OCR errors and number formats."""
    variants = {q}
    for m in CLAUSE_RE.finditer(q):
        if m.group(1):
            variants.add(f"第{m.group(1)}条")
            variants.add(m.group(1))
        if m.group(2):
            variants.add(m.group(2))
            variants.add(f"第{m.group(2)}条")
    # 表/table keyword nudge
    if any(k in q for k in ["表格", "表中", "列出", "几项", "数据"]):
        variants.add(q + " 表格")
    return list(variants)


@dataclass
class RetrievalResult:
    chunk: dict
    score: float
    bm25_rank: int | None = None
    vec_rank: int | None = None
    sources: list[str] = field(default_factory=list)


def retrieve(
    bundle: IndexBundle,
    query: str,
    top_k_recall: int = 20,
    top_k_final: int = 5,
    rrf_k: int = 60,
) -> list[RetrievalResult]:
    queries = _expand_query(query)

    # ---- BM25 over all variants, max-pool scores ----
    bm25_scores = np.zeros(len(bundle.chunks), dtype="float32")
    for q in queries:
        tokens = _tokenize_zh(q)
        if not tokens:
            continue
        s = bundle.bm25.get_scores(tokens)
        bm25_scores = np.maximum(bm25_scores, s)
    bm25_top = np.argsort(-bm25_scores)[:top_k_recall]

    # ---- Vector over original query (variants for dense rarely help) ----
    qv = bundle.embed_query(query)
    sims, idxs = bundle.search_vec(qv, top_k_recall)
    vec_top = idxs.tolist()
    vec_sims = sims.tolist()

    # ---- RRF fusion ----
    rrf: dict[int, float] = {}
    bm25_rank_map: dict[int, int] = {}
    vec_rank_map: dict[int, int] = {}
    for rank, i in enumerate(bm25_top):
        rrf[int(i)] = rrf.get(int(i), 0.0) + 1.0 / (rrf_k + rank + 1)
        bm25_rank_map[int(i)] = rank + 1
    for rank, i in enumerate(vec_top):
        if i < 0:
            continue
        rrf[int(i)] = rrf.get(int(i), 0.0) + 1.0 / (rrf_k + rank + 1)
        vec_rank_map[int(i)] = rank + 1

    # also include raw dense sim as a tiebreaker scaled signal
    dense_score: dict[int, float] = {int(i): float(s) for i, s in zip(vec_top, vec_sims) if i >= 0}

    ranked = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)[:top_k_final]
    out: list[RetrievalResult] = []
    for idx, score in ranked:
        sources = []
        if idx in bm25_rank_map:
            sources.append(f"bm25#{bm25_rank_map[idx]}")
        if idx in vec_rank_map:
            sources.append(f"vec#{vec_rank_map[idx]}")
        # surface dense similarity as the "confidence" proxy
        out.append(RetrievalResult(
            chunk=bundle.chunks[idx],
            score=dense_score.get(idx, score),
            bm25_rank=bm25_rank_map.get(idx),
            vec_rank=vec_rank_map.get(idx),
            sources=sources,
        ))
    return out

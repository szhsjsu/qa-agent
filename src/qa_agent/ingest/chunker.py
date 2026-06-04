"""Text → chunks. Clause-aware: 第X条 / X.X / X.X.X are hard split points."""
from __future__ import annotations

import re
import hashlib
from typing import Iterable

# 中文条款编号：第X条、X.X、X.X.X、一、二、三 等
CLAUSE_PATTERNS = [
    re.compile(r"^第[一二三四五六七八九十百零0-9]+条"),
    re.compile(r"^\d+(\.\d+){1,3}\s"),
    re.compile(r"^[一二三四五六七八九十]+、"),
    re.compile(r"^\(\s*\d+\s*\)"),
]

WINDOW_TOKENS = 480
OVERLAP_TOKENS = 64


def _is_clause_start(line: str) -> bool:
    s = line.strip()
    return any(p.match(s) for p in CLAUSE_PATTERNS)


def _extract_clause_id(line: str) -> str | None:
    s = line.strip()
    m = re.match(r"^第([一二三四五六七八九十百零0-9]+)条", s)
    if m:
        return f"第{m.group(1)}条"
    m = re.match(r"^(\d+(?:\.\d+){1,3})\s", s)
    if m:
        return m.group(1)
    return None


def _approx_tokens(text: str) -> int:
    # 中文按字符近似，英文按 4 字符 1 token，混合时偏保守取 char 数
    return len(text)


def chunk_page_text(text: str, page: int, doc_id: str) -> list[dict]:
    """Split a page's text into chunks. Clause boundaries first, then sliding window."""
    if not text.strip():
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]

    # 1) clause-level segments
    segments: list[tuple[str | None, list[str]]] = []
    current_id: str | None = None
    current: list[str] = []
    for ln in lines:
        if _is_clause_start(ln):
            if current:
                segments.append((current_id, current))
            current_id = _extract_clause_id(ln)
            current = [ln]
        else:
            current.append(ln)
    if current:
        segments.append((current_id, current))

    # 2) within-segment sliding window if too long
    out: list[dict] = []
    for clause_id, seg_lines in segments:
        seg_text = "\n".join(seg_lines).strip()
        if _approx_tokens(seg_text) <= WINDOW_TOKENS:
            out.append(_mk_chunk(seg_text, page, doc_id, "clause" if clause_id else "text", clause_id))
        else:
            # sliding window over characters
            i = 0
            while i < len(seg_text):
                window = seg_text[i:i + WINDOW_TOKENS]
                out.append(_mk_chunk(window, page, doc_id, "clause" if clause_id else "text", clause_id))
                if i + WINDOW_TOKENS >= len(seg_text):
                    break
                i += WINDOW_TOKENS - OVERLAP_TOKENS
    return out


def _mk_chunk(text: str, page: int, doc_id: str, type_: str, clause_id: str | None) -> dict:
    h = hashlib.md5(f"{doc_id}-{page}-{text[:60]}".encode()).hexdigest()[:10]
    return {
        "chunk_id": f"{doc_id}-p{page}-{h}",
        "doc_id": doc_id,
        "page": page,
        "type": type_,
        "text": text,
        "clause_id": clause_id,
    }

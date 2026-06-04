"""Table extraction: pdfplumber first; fall back to OCR bbox clustering for scans."""
from __future__ import annotations

import hashlib
from typing import Any
import numpy as np

from .ocr import OCRLine


def extract_tables_pdfplumber(pdf_path: str, page_index: int) -> list[list[list[str]]]:
    """Returns list of tables; each table is list of rows; each row is list of cells."""
    import pdfplumber
    tables: list[list[list[str]]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_index]
            for tbl in (page.extract_tables() or []):
                cleaned = [[(c or "").strip() for c in row] for row in tbl]
                if any(any(c for c in row) for row in cleaned):
                    tables.append(cleaned)
    except Exception:
        return []
    return tables


def cluster_ocr_to_table(lines: list[OCRLine], y_tol: float = 12.0, x_tol: float = 25.0) -> list[list[str]] | None:
    """Group OCR lines by row (y) and column (x) — heuristic table reconstruction.

    Only returns something if it looks reasonably grid-like (>=2 rows, >=2 cols).
    """
    if len(lines) < 4:
        return None

    # row clustering by y center
    items = []
    for ln in lines:
        cy = (ln.bbox[1] + ln.bbox[3]) / 2
        cx = (ln.bbox[0] + ln.bbox[2]) / 2
        items.append((cy, cx, ln.text))
    items.sort()

    rows: list[list[tuple[float, str]]] = []
    cur: list[tuple[float, str]] = []
    cur_y: float | None = None
    for cy, cx, text in items:
        if cur_y is None or abs(cy - cur_y) <= y_tol:
            cur.append((cx, text))
            cur_y = cy if cur_y is None else (cur_y + cy) / 2
        else:
            rows.append(cur)
            cur = [(cx, text)]
            cur_y = cy
    if cur:
        rows.append(cur)

    if len(rows) < 2:
        return None

    # column anchors: union of x centers, clustered
    all_x = sorted(x for r in rows for x, _ in r)
    cols: list[float] = []
    for x in all_x:
        if not cols or x - cols[-1] > x_tol:
            cols.append(x)
        else:
            cols[-1] = (cols[-1] + x) / 2
    if len(cols) < 2:
        return None

    # build grid
    grid: list[list[str]] = []
    for r in rows:
        row_cells = [""] * len(cols)
        for x, text in sorted(r):
            # nearest column
            ci = min(range(len(cols)), key=lambda i: abs(cols[i] - x))
            row_cells[ci] = (row_cells[ci] + " " + text).strip()
        grid.append(row_cells)

    # require at least 2 non-empty rows with >=2 non-empty cells
    good_rows = sum(1 for row in grid if sum(1 for c in row if c) >= 2)
    if good_rows < 2:
        return None
    return grid


def table_to_markdown(grid: list[list[str]]) -> str:
    if not grid:
        return ""
    n_cols = max(len(r) for r in grid)
    header = grid[0] + [""] * (n_cols - len(grid[0]))
    md = "| " + " | ".join(header) + " |\n"
    md += "| " + " | ".join(["---"] * n_cols) + " |\n"
    for row in grid[1:]:
        padded = row + [""] * (n_cols - len(row))
        md += "| " + " | ".join(padded) + " |\n"
    return md


def table_to_nl(grid: list[list[str]]) -> str:
    """Naive natural-language linearization for retrieval recall on table content."""
    if not grid or len(grid) < 2:
        return ""
    header = grid[0]
    parts = []
    for row in grid[1:]:
        kv = [f"{h}={c}" for h, c in zip(header, row) if c]
        if kv:
            parts.append("；".join(kv))
    return "。\n".join(parts)


def make_table_chunk(grid: list[list[str]], page: int, doc_id: str) -> dict[str, Any]:
    md = table_to_markdown(grid)
    nl = table_to_nl(grid)
    text_for_index = f"[表格 第{page}页]\n{nl}\n{md}"
    h = hashlib.md5(f"{doc_id}-{page}-table-{md[:60]}".encode()).hexdigest()[:10]
    return {
        "chunk_id": f"{doc_id}-p{page}-tbl-{h}",
        "doc_id": doc_id,
        "page": page,
        "type": "table",
        "text": text_for_index,
        "table_md": md,
        "table_desc": nl,
        "clause_id": None,
    }

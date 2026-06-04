"""End-to-end ingest: PDF → chunks.jsonl."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .chunker import chunk_page_text
from .ocr import get_ocr, OCRLine
from .tables import (
    extract_tables_pdfplumber,
    cluster_ocr_to_table,
    make_table_chunk,
)

log = logging.getLogger(__name__)

TEXT_LAYER_MIN_CHARS = 50   # below → treat page as scanned
RENDER_DPI = 220


@dataclass
class PageInfo:
    page: int
    is_scanned: bool
    text_layer_chars: int
    ocr_avg_conf: float | None


def _pdfplumber_page_text(pdf_path: str, page_index: int) -> str:
    import pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_index]
            return page.extract_text() or ""
    except Exception:
        return ""


def _render_page_to_array(pdf_path: str, page_index: int, dpi: int = RENDER_DPI) -> np.ndarray:
    """Render a page to RGB numpy array using PyMuPDF (no poppler)."""
    import fitz  # PyMuPDF
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = img[:, :, :3]
        return img
    finally:
        doc.close()


def _lines_to_paragraph_text(lines: list[OCRLine]) -> str:
    """Reorder OCR lines top-to-bottom, group lines on same y as one row."""
    if not lines:
        return ""
    items = sorted(lines, key=lambda ln: ((ln.bbox[1] + ln.bbox[3]) / 2, ln.bbox[0]))
    # crude: just join by newline; downstream chunker handles paragraphing via blank lines
    out: list[str] = []
    last_y: float | None = None
    row: list[str] = []
    for ln in items:
        cy = (ln.bbox[1] + ln.bbox[3]) / 2
        if last_y is None or abs(cy - last_y) <= 10:
            row.append(ln.text)
            last_y = cy if last_y is None else (last_y + cy) / 2
        else:
            out.append(" ".join(row))
            row = [ln.text]
            last_y = cy
    if row:
        out.append(" ".join(row))
    return "\n".join(out)


def ingest_pdf(pdf_path: str | Path, out_dir: str | Path, doc_id: str | None = None) -> dict[str, Any]:
    pdf_path = str(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc_id = doc_id or Path(pdf_path).stem

    import fitz
    doc = fitz.open(pdf_path)
    n_pages = len(doc)
    doc.close()

    chunks: list[dict] = []
    page_infos: list[PageInfo] = []
    ocr = None  # lazy init

    for i in range(n_pages):
        page_no = i + 1
        text_layer = _pdfplumber_page_text(pdf_path, i)
        chars = len(text_layer.strip())
        is_scanned = chars < TEXT_LAYER_MIN_CHARS

        page_text = ""
        ocr_avg_conf: float | None = None

        # ---- 1. text-layer path ----
        if not is_scanned:
            page_text = text_layer
            log.info("page %d: text-layer (%d chars)", page_no, chars)
        else:
            # ---- 2. OCR path ----
            log.info("page %d: scanned, running OCR", page_no)
            if ocr is None:
                ocr = get_ocr()
            img = _render_page_to_array(pdf_path, i)
            ocr_lines = ocr.run(img)
            ocr_avg_conf = float(np.mean([ln.conf for ln in ocr_lines])) if ocr_lines else 0.0
            page_text = _lines_to_paragraph_text(ocr_lines)
            log.info("page %d: OCR got %d lines, avg conf %.3f", page_no, len(ocr_lines), ocr_avg_conf)

            # ---- 2b. table reconstruction from OCR ----
            grid = cluster_ocr_to_table(ocr_lines)
            if grid:
                tbl_chunk = make_table_chunk(grid, page_no, doc_id)
                tbl_chunk["ocr_conf"] = ocr_avg_conf
                chunks.append(tbl_chunk)
                log.info("page %d: extracted %dx%d table via OCR clustering", page_no, len(grid), len(grid[0]))

        # ---- 3. text chunks ----
        page_chunks = chunk_page_text(page_text, page_no, doc_id)
        for c in page_chunks:
            if ocr_avg_conf is not None:
                c["ocr_conf"] = ocr_avg_conf
        chunks.extend(page_chunks)

        # ---- 4. pdfplumber tables (if text-layer page) ----
        if not is_scanned:
            for grid in extract_tables_pdfplumber(pdf_path, i):
                tbl_chunk = make_table_chunk(grid, page_no, doc_id)
                chunks.append(tbl_chunk)
                log.info("page %d: extracted %dx%d table via pdfplumber", page_no, len(grid), len(grid[0]))

        page_infos.append(PageInfo(page_no, is_scanned, chars, ocr_avg_conf))

    # write outputs
    chunks_path = out_dir / f"{doc_id}.chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    meta = {
        "doc_id": doc_id,
        "pdf_path": pdf_path,
        "n_pages": n_pages,
        "n_chunks": len(chunks),
        "n_tables": sum(1 for c in chunks if c["type"] == "table"),
        "pages": [p.__dict__ for p in page_infos],
    }
    (out_dir / f"{doc_id}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta

"""Core data types shared across ingest / index / retrieval / agent."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

ChunkType = Literal["text", "table", "clause"]


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    page: int                       # 1-indexed
    type: ChunkType
    text: str                       # canonical text for embedding / display
    clause_id: Optional[str] = None # e.g. "3.2" if matched
    bbox: Optional[list[float]] = None
    table_md: Optional[str] = None  # markdown for table chunks
    table_desc: Optional[str] = None
    ocr_conf: Optional[float] = None  # average OCR confidence, None if text-layer


class Citation(BaseModel):
    page: int
    quote: str
    chunk_id: Optional[str] = None


class AnswerResult(BaseModel):
    question: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    confidence: Literal["high", "medium", "low"] = "medium"
    grounded: Optional[bool] = None
    reason: Optional[str] = None     # why refused / low confidence
    used_chunk_ids: list[str] = Field(default_factory=list)
    latency_ms: Optional[float] = None

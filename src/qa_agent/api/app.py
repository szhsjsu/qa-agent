"""FastAPI service: POST /ask -> AnswerResult."""
from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel

from ..config import settings
from ..index import load_index
from ..agent import answer_question
from ..schema import AnswerResult

app = FastAPI(title="qa-agent", version="0.1.0")


@lru_cache(maxsize=1)
def _bundle():
    return load_index(settings.index_dir)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/ask", response_model=AnswerResult)
def ask(req: AskRequest) -> AnswerResult:
    return answer_question(_bundle(), req.question)

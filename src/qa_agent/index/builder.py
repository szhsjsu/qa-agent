"""Build / load the dual index (BM25 + BGE vector / numpy IP)."""
from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


def _tokenize_zh(text: str) -> list[str]:
    import jieba
    return [t for t in jieba.lcut(text) if t.strip()]


@dataclass
class IndexBundle:
    chunks: list[dict]
    bm25: Any
    vectors: np.ndarray            # [N, dim], L2-normalized
    embed_model: Any
    embed_name: str

    def embed_query(self, q: str) -> np.ndarray:
        v = self.embed_model.encode([q], normalize_embeddings=True)
        return np.asarray(v, dtype="float32")

    def search_vec(self, qv: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        sims = (self.vectors @ qv.T).squeeze(1)  # [N]
        idx = np.argsort(-sims)[:top_k]
        return sims[idx], idx


def _load_embedder(name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)


def build_index(chunks_path: str | Path, out_dir: str | Path, embed_name: str) -> dict[str, Any]:
    from rank_bm25 import BM25Okapi

    chunks_path = Path(chunks_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    chunks = [json.loads(l) for l in chunks_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    texts = [c["text"] for c in chunks]

    # BM25
    tokenized = [_tokenize_zh(t) for t in texts]
    bm25 = BM25Okapi(tokenized)
    with (out_dir / "bm25.pkl").open("wb") as f:
        pickle.dump({"bm25": bm25, "tokenized": tokenized}, f)

    # Vector
    model = _load_embedder(embed_name)
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=16)
    embeddings = np.asarray(embeddings, dtype="float32")
    np.save(out_dir / "vec.npy", embeddings)

    (out_dir / "chunks.jsonl").write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks), encoding="utf-8"
    )
    meta = {"embed_name": embed_name, "dim": int(embeddings.shape[1]), "n_chunks": len(chunks)}
    (out_dir / "index.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def load_index(index_dir: str | Path, embed_name: str | None = None) -> IndexBundle:
    index_dir = Path(index_dir)
    meta = json.loads((index_dir / "index.meta.json").read_text())
    embed_name = embed_name or meta["embed_name"]

    chunks = [json.loads(l) for l in (index_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    with (index_dir / "bm25.pkl").open("rb") as f:
        bm = pickle.load(f)
    vectors = np.load(index_dir / "vec.npy")
    model = _load_embedder(embed_name)
    return IndexBundle(
        chunks=chunks,
        bm25=bm["bm25"],
        vectors=vectors,
        embed_model=model,
        embed_name=embed_name,
    )

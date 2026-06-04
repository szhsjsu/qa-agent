"""Centralized configuration. Loads .env, then optional domain yaml overlay."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
import yaml

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


def _get(key: str, default: str | None = None) -> str | None:
    v = os.getenv(key, default)
    return v


class Settings:
    # LLM
    glm_api_key: str = _get("GLM_API_KEY", "") or ""
    glm_base_url: str = _get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    glm_model: str = _get("GLM_MODEL", "glm-4-plus")
    glm_verify_model: str = _get("GLM_VERIFY_MODEL", "glm-4-air")

    # Embedding
    embedding_model: str = _get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")

    # Paths
    data_dir: Path = Path(_get("DATA_DIR", str(ROOT / "data")))
    index_dir: Path = Path(_get("INDEX_DIR", str(ROOT / "data" / "index")))

    # Retrieval
    top_k_recall: int = 20
    top_k_final: int = 5
    rrf_k: int = 60
    min_score_for_answer: float = 0.15  # below → refuse

    # Domain overlay
    domain: dict[str, Any] = {}

    @classmethod
    def load_domain(cls, name: str) -> None:
        path = ROOT / "configs" / "domain" / f"{name}.yaml"
        if path.exists():
            cls.domain = yaml.safe_load(path.read_text()) or {}


settings = Settings()

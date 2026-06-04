"""OCR backend abstraction. Default: RapidOCR (onnx, pure pip)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import numpy as np


@dataclass
class OCRLine:
    text: str
    bbox: list[float]   # [x0, y0, x1, y1]
    conf: float


class OCRBackend(Protocol):
    def run(self, image: np.ndarray) -> list[OCRLine]: ...


class RapidOCRBackend:
    """Thin wrapper around rapidocr-onnxruntime."""

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR()

    def run(self, image: np.ndarray) -> list[OCRLine]:
        result, _ = self._ocr(image)
        if not result:
            return []
        lines: list[OCRLine] = []
        for item in result:
            box, text, conf = item[0], item[1], item[2]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append(OCRLine(
                text=text,
                bbox=[float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))],
                conf=float(conf),
            ))
        return lines


_backend: OCRBackend | None = None


def get_ocr() -> OCRBackend:
    global _backend
    if _backend is None:
        _backend = RapidOCRBackend()
    return _backend

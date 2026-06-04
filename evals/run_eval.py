"""Run the QA evaluation set and append a row to history.csv.

Metric:
  - hit:       expected_keywords 中至少一个出现在 answer 内
  - cite_hit:  返回的 citation 页码与 expected_pages 有交集
  - refuse_ok: no_answer 类型必须 refused=True
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qa_agent.config import settings  # noqa: E402
from qa_agent.index import load_index  # noqa: E402
from qa_agent.agent import answer_question  # noqa: E402


def _hit(answer: str, keywords: list[str]) -> bool:
    a = answer.replace(",", "").replace(" ", "")
    return any(k.replace(",", "").replace(" ", "") in a for k in keywords)


def main() -> int:
    qa_path = Path(__file__).with_name("qa.jsonl")
    cases = [json.loads(l) for l in qa_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    bundle = load_index(settings.index_dir)
    rows = []
    n_hit = n_cite = n_refuse_ok = n_refuse_total = 0
    n_fact = 0
    latencies = []

    for c in cases:
        t0 = time.perf_counter()
        r = answer_question(bundle, c["question"])
        latency = (time.perf_counter() - t0) * 1000
        latencies.append(latency)

        if c["type"] == "no_answer":
            n_refuse_total += 1
            ok = r.refused
            if ok:
                n_refuse_ok += 1
            rows.append({**c, "ok": ok, "answer": r.answer, "refused": r.refused})
        else:
            n_fact += 1
            hit = _hit(r.answer, c.get("expected_keywords", []))
            cite_ok = bool(set(p.page for p in r.citations) & set(c.get("expected_pages", [])))
            if hit: n_hit += 1
            if cite_ok: n_cite += 1
            rows.append({**c, "answer": r.answer, "refused": r.refused, "hit": hit, "cite_ok": cite_ok,
                         "citations": [{"page": x.page, "quote": x.quote} for x in r.citations]})

        marker = "✓" if (c["type"] == "no_answer" and r.refused) or (c["type"] != "no_answer" and _hit(r.answer, c.get("expected_keywords", []))) else "✗"
        print(f"  {marker} [{c['type']:11s}] {c['id']:10s} | {c['question'][:40]}... → refused={r.refused}, ans={r.answer[:50]}")

    # Aggregate
    answer_acc = n_hit / n_fact if n_fact else 0.0
    cite_recall = n_cite / n_fact if n_fact else 0.0
    refuse_acc = n_refuse_ok / n_refuse_total if n_refuse_total else 0.0
    p50 = sorted(latencies)[len(latencies) // 2] if latencies else 0
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    print()
    print(f"answer_acc  = {answer_acc:.2%}  ({n_hit}/{n_fact})")
    print(f"cite_recall = {cite_recall:.2%}  ({n_cite}/{n_fact})")
    print(f"refuse_acc  = {refuse_acc:.2%}  ({n_refuse_ok}/{n_refuse_total})")
    print(f"latency p50 = {p50:.0f}ms   p95 = {p95:.0f}ms")

    # Append to history
    hist = Path(__file__).with_name("history.csv")
    is_new = not hist.exists()
    with hist.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["ts", "answer_acc", "cite_recall", "refuse_acc", "p50_ms", "p95_ms", "model"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), f"{answer_acc:.4f}",
                    f"{cite_recall:.4f}", f"{refuse_acc:.4f}", f"{p50:.0f}", f"{p95:.0f}",
                    settings.glm_model])

    # Write detailed
    (Path(__file__).with_name("last_run.json")).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

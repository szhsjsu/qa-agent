#!/usr/bin/env bash
# 一键演示：ingest → retrieve → 5 个问答 → 评测
# 使用：bash scripts/demo.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "[!] 请先 cp .env.example .env 并填入 GLM_API_KEY"; exit 1
fi
source .venv/bin/activate

PDF="${1:-data/sample.pdf}"
sep() { printf '\n\033[1;34m═══ %s ═══\033[0m\n' "$1"; }

sep "1. Ingest（解析 + OCR + 切块 + 索引）"
qa ingest "$PDF"

sep "2. 检索：看一个表格问题命中了哪些 chunks"
qa retrieve-cmd "中信产业投资基金管理有限公司账面价值" --top-k 3

sep "3. 五个示例问答（含 1 个表格、1 个无答案、1 个 OCR 错字）"
for Q in \
  "中信产业投资基金管理有限公司在2024年期末（2024年12月31日）的账面价值是多少？" \
  "Sino-Ocean Land Logistics Investment Management Limited 在 2025 年 6 月 30 日的账面价值是多少？" \
  "CLSA Aviation Private Equity Fund II 在 2024 年的本年增加金额是多少？" \
  "新彊股权交易中心2024年1月1日账面价值？" \
  "中信证券今年股价是多少？"; do
  printf '\n\033[1;33mQ:\033[0m %s\n' "$Q"
  qa ask "$Q"
done

sep "4. 评测：14 道题（正文 / 表格 / 无答案 / 模糊 / OCR 错字）"
python evals/run_eval.py | tail -25

sep "5. (可选) 起 API 服务： uvicorn qa_agent.api.app:app --reload --port 8000"
echo "  curl -X POST http://localhost:8000/ask -H 'content-type: application/json' \\"
echo "       -d '{\"question\":\"中信产业投资基金管理有限公司账面价值\"}'"

#!/usr/bin/env bash
# 端到端演示 —— 五个段落正好对应作业要求的 5 条交付点
# 使用：bash scripts/demo.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "[!] 请先跑 bash scripts/setup.sh 并在 .env 填入 GLM_API_KEY"; exit 1
fi
source .venv/bin/activate

PDF="${1:-data/sample.pdf}"
sep() { printf '\n\033[1;34m═══ %s ═══\033[0m\n' "$1"; }

sep "【交付 1】 部署 / 启动流程（设计目标：可复现）"
echo "  环境：$(python --version), uv $(uv --version 2>&1 | head -1)"
echo "  虚拟环境：$VIRTUAL_ENV"
echo "  已安装 qa CLI： $(which qa)"
qa --help

sep "【交付 1.5】 单测验证安装与核心逻辑"
python -m pytest tests/ -v --tb=no -q

sep "【交付 2a】 Ingest：PDF 类型判别 → OCR / 文本层路由 → 切块 → 索引"
qa ingest "$PDF"

sep "【交付 2b】 PDF 解析结果汇总（每页是扫描页还是文本层、OCR 置信度）"
qa inspect

sep "【交付 2c】 看一个文本页 (P1) 的正文抽取"
qa inspect --page 1 2>&1 | head -50

sep "【交付 2d】 看一个表格 chunk 的 Markdown 还原（表格类型）"
qa inspect --page 2 2>&1 | grep -A 100 "table" | head -40

sep "【交付 2e】 看 OCR 抽取出的扫描页 (P6)"
qa inspect --page 6 2>&1 | head -40

sep "【交付 3 & 4】 五个示例问答（含 1 表格题 + 1 无答案题 + 1 OCR 错字题），全部带引用 + 自检"
for Q in \
  "中信产业投资基金管理有限公司在2024年期末（2024年12月31日）的账面价值是多少？" \
  "Sino-Ocean Land Logistics Investment Management Limited 在 2025 年 6 月 30 日的账面价值是多少？" \
  "CLSA Aviation Private Equity Fund II 在 2024 年的本年增加金额是多少？" \
  "新彊股权交易中心2024年1月1日账面价值？" \
  "中信证券今年股价是多少？"; do
  printf '\n\033[1;33mQ:\033[0m %s\n' "$Q"
  qa ask "$Q"
done

sep "【交付 5】 评测脚本结果（14 题：fact / table / no_answer / fuzzy / ocr_robust）"
python evals/run_eval.py | tail -25

sep "【附】 评测历史（每次跑会追加一行，便于回归追踪）"
[ -f evals/history.csv ] && cat evals/history.csv || echo "(尚无历史)"

sep "【附】 (可选) 起 API： uvicorn qa_agent.api.app:app --port 8000"
echo "  curl -X POST http://localhost:8000/ask -H 'content-type: application/json' \\"
echo "       -d '{\"question\":\"中信产业投资基金管理有限公司2024年期末账面价值\"}'"

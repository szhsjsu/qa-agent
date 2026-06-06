#!/usr/bin/env bash
# 冷启动：从空仓库到能跑 demo.sh 的全部步骤
# 使用：bash scripts/setup.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

sep() { printf '\n\033[1;34m═══ %s ═══\033[0m\n' "$1"; }

sep "0. 环境检查"
command -v uv >/dev/null || { echo "[!] 请先安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
python3 --version

sep "1. 创建虚拟环境 (.venv, Python 3.10)"
[ -d .venv ] && echo "  已存在，跳过" || uv venv --python 3.10

sep "2. 安装依赖（首次约 1-2 分钟）"
source .venv/bin/activate
uv pip install -e . >/dev/null
echo "  ✓ 已安装"

sep "3. 配置 .env"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  已生成 .env —— 请编辑填入 GLM_API_KEY"
  echo "  ZhipuAI coding plan → GLM_PROTOCOL=anthropic, base_url=/api/anthropic"
  echo "  常规充值账户       → GLM_PROTOCOL=openai,    base_url=/api/paas/v4"
else
  echo "  已存在，跳过"
fi

sep "4. 运行单测验证安装正确"
python -m pytest tests/ -q

sep "5. 完成"
echo "下一步："
echo "  bash scripts/demo.sh      # 一键端到端演示"
echo "  qa ingest data/sample.pdf # 单独 ingest"
echo "  qa ask \"...\"              # 单独问答"

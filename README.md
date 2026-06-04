# qa-agent-homework

一个面向**扫描版 PDF** 的文档问答 Agent 原型，覆盖：解析 / OCR / 表格 / 混合检索 / 带引用生成 / 自检拒答 / 评测回归。

> 完整设计与取舍见 [docs/design.md](docs/design.md)。

## 快速开始

```bash
# 1. 安装依赖（用 uv）
uv venv && source .venv/bin/activate
uv pip install -e .

# 2. 配置 key
cp .env.example .env
# 编辑 .env，填入 GLM_API_KEY

# 3. ingest（首次运行会下载 BGE 模型 ~400MB，OCR 模型 ~50MB）
qa ingest data/sample.pdf

# 4. 问答
qa ask "第三条规定了什么？"
qa ask "表格中第二行的数据是多少？"

# 5. 评测
python evals/run_eval.py

# 6. (可选) 起 API
uvicorn qa_agent.api.app:app --reload
```

## 目录结构

```
src/qa_agent/
  ingest/      PDF 解析 / OCR / 表格 / 切块
  index/       BM25 + 向量索引
  retrieval/   混合检索 + RRF + 可选 rerank
  agent/       生成 + 自检 + 拒答
  api/         FastAPI
  cli.py       typer CLI
configs/       默认配置 + 领域配置（金融/合同/合规）
evals/         评测集 + 评测脚本 + 历史结果
tests/         单测
docs/          设计文档
data/          PDF（gitignored）
```

## 关键设计点（一句话版本）

- **PDF 类型判别**：用 pdfplumber 抽前 2 页文本量，按页路由文本/扫描两条路径。
- **OCR**：RapidOCR（onnx），纯 pip 无系统依赖。
- **表格**：pdfplumber 优先，扫描页用 bbox 聚类兜底，并同时存 Markdown + 自然语言描述。
- **切块**：条款正则 > 段落 > 滑窗，三级降级。
- **检索**：BM25(jieba) + BGE 向量 + RRF。
- **生成**：GLM，强制 JSON + citation，找不到必须拒答。
- **自检**：独立 LLM 校验 grounded / hallucination，把可疑结果转为拒答。
- **业务迁移**：`configs/domain/*.yaml` 抽出领域差异，新业务加一份 yaml。

## AI 使用声明

本仓库的代码骨架与样板代码由 Claude Code 辅助生成，所有 prompt、评测集标准答案、设计取舍由作者本人核对并负责。模型输出统一走 JSON Schema 校验，解析失败降级为拒答。

## 已完成 / 未完成

见 [docs/design.md §8](docs/design.md)。

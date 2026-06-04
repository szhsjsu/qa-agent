# 智能文档问答 Agent — 设计说明

## 1. 问题拆解

题面暗含 6 个独立的坑，任何一个偷懒都会被追问：

| # | 坑 | 体现 |
|---|---|---|
| 1 | 扫描件没文本层 | 不能 `pdfplumber` 直接读，必须 OCR；纯 OCR 又会丢表格结构 |
| 2 | 表格 | OCR 后变成乱序文字流，问答会答错 |
| 3 | OCR 错误 | 形近字、漏字、错列；下游必须能容错 |
| 4 | 条款编号 | "第3.2条" 是检索锚点，不能被切块切碎 |
| 5 | 无答案问题 | 必须能拒答，不能幻觉（金融/合规场景的硬指标） |
| 6 | 可迁移性 | 解析策略、prompt、评测集都要按"业务域"可替换 |

## 2. 架构总览

```
ingest（离线一次性）：
  PDF → 类型判别 → 解析路由：
                   ├─ 文本层 (pdfplumber)
                   ├─ OCR     (RapidOCR onnx)
                   └─ 表格    (pdfplumber + bbox 聚类兜底)
       → 归一化 chunks（page / bbox / type=text|table|clause）
       → 双索引：BM25(jieba) + 向量(bge-small-zh / bge-m3)

query（在线）：
  question → query 改写 → 混合检索 (BM25 + 向量 + RRF)
           → (可选) bge-reranker
           → 证据装配
           → 生成 (GLM, JSON 强制输出, 必须带 citation)
           → 自检 agent (是否 grounded / 是否拒答)
           → {answer, citations[], confidence, refused}
```

不是单一 LLM 调用，而是"规划-检索-生成-自检"的 mini-agent，因为题目明确要求"自检 / 是否拒答"。

## 3. 模块设计与取舍

### 3.1 PDF 类型判别
- `pdfplumber` 抽前 2 页文本：长度 > 阈值 → 文本型；否则 → 扫描型。
- 混合型按页判定，不一刀切。
- 不引入大模型做判别，规则足够稳。

### 3.2 OCR
- 默认 RapidOCR（onnxruntime，pip 装即用，CPU 即可），方便复现。
- 抽象 `OCRBackend` 接口，可换 PaddleOCR。
- 保留每个文本块的 bbox + 行号，后面表格重建要用。

### 3.3 表格抽取
两路并行：
1. `pdfplumber.extract_tables()`：对扫描件原生失败但对夹杂文本页有效。
2. 视觉兜底：OCR 后按 y 坐标聚类成行、x 坐标聚类成列。
- 表格 chunk 单独打标 `type=table`，同时存 Markdown 渲染 + 自然语言描述，检索命中表格时一起喂给 LLM。

### 3.4 切块
- 文本：条款正则（`第X条`/`X.X`）→ 段落 → 滑窗(512 token, overlap 64) 三级。
- 表格：整表一个 chunk，不切。
- 每个 chunk 携带：`{doc_id, page, type, clause_id?, bbox, text, table_md?}`。

### 3.5 检索
- BM25(jieba) + 向量(bge) 并行 → RRF 融合。
- OCR 错字场景下：BM25 救向量召回不到的精确编号，向量救 BM25 因错字失效的语义匹配。
- Top-k 20 → rerank top 5（可选）。
- Query 改写："第三条规定" → 增补 "3 / 第3条 / 3."。

### 3.6 生成
- prompt 强约束：
  - 只能基于 `<context>` 内的内容；
  - 必须输出 JSON：`{answer, citations:[{page, quote}], used_chunk_ids:[...]}`；
  - 找不到 → `answer = "无法从文档中找到答案"`。
- 表格问题走单独 prompt，明确"以下是表格的 Markdown 形式"。

### 3.7 自检 / 拒答（独立 LLM 调用）
- 输入：question + answer + cited chunks。
- 输出：`{grounded, hallucination_risk, refuse, reason}`。
- 拒答路径：
  - 引用片段找不到答案的关键实体 → 改拒答。
  - 检索 top-1 分数低于阈值 → 直接拒答，不进生成。
  - 多条引用互相矛盾 → confidence=low，把矛盾抛给用户。

## 4. 关键取舍

| 选择 | 选什么 | 理由 |
|---|---|---|
| OCR | RapidOCR (onnx) | 纯 pip，CPU 可跑，无系统依赖 |
| PDF 渲染 | PyMuPDF | 不需要 poppler |
| 向量库 | FAISS 本地 | 作业体量不需要 Milvus |
| LLM | GLM (OpenAI 兼容) | 题目可指定，base_url 可替换迁移 |
| Embedding | BGE 本地 (small-zh / m3) | 中文友好，离线，零调用成本 |
| Rerank | bge-reranker 可选 | 跑不动机器时关掉，BM25+向量也够 |
| 交互 | CLI + FastAPI + 极简 Streamlit | 演示够用，不做完整前端 |
| 多模态 | 默认关，仅"表格 + OCR 置信低" 时触发 | 控制成本与复现门槛 |

## 5. 测试与评估

### 评测集 `evals/qa.jsonl`
- 10 条正文事实问题（含条款编号类）
- 5 条表格问题
- 5 条无答案问题
- 3 条模糊问题（同义改写）
- 3 条 OCR 错字鲁棒性问题
- 2 条多跳问题

每条标注：`{question, expected_answer | "REFUSE", expected_pages:[], type}`。

### 指标
- 答案正确率（人工 + LLM-as-judge 双轨）
- 引用页码命中率 (citation recall)
- 拒答场景：拒答率与误拒率
- 端到端延迟 (p50/p95)

### 回归保障
- `pytest` 单测覆盖：类型判别、切块正则、JSON 解析、自检判定。
- `evals/run_eval.py` 跑全量评测，结果追加到 `evals/history.csv`。

## 6. 业务场景迁移

`configs/domain/*.yaml` 抽出领域差异：
```
切块正则 | 同义词典 | 拒答阈值 | 生成 prompt 口径 | 评测集路径
```
新业务接入 = 加一份 yaml + 一份评测集，不改代码。
预置示例：`finance.yaml`（金融披露文件）、`contract.yaml`（合同条款）、`compliance.yaml`（合规手册）。

## 7. AI 工具使用声明

- 用 Claude Code 起项目骨架、写样板代码、生成评测集草稿。
- 校验方式：
  - 核心模块（解析、检索、自检）有单测。
  - 评测集"标准答案"由人核对原 PDF，不让 LLM 自说自话。
  - 模型输出走 JSON Schema 校验，解析失败重试一次后降级拒答。

## 8. 明确不做（坦诚交代）

- 不做完整前端、不做用户系统、不做多文档大规模。
- 不做 fine-tune，纯 prompt + 检索。
- 多模态表格识别默认关。

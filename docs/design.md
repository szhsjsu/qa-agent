# 智能文档问答 Agent — 设计说明

## 1. 问题拆解

| # | 可能问题    | 具体体现                                     |
|---|---------|------------------------------------------|
| 1 | 扫描件没文本层 | 不能 `pdfplumber` 直接读，必须 OCR；纯 OCR 又会丢表格结构 |
| 2 | 表格      | OCR 后变成乱序文字流，问答会答错                       |
| 3 | OCR 错误  | 形近字、漏字、错列；下游必须能容错                        |
| 4 | 条款编号    | "第3.2条" 是检索锚点，不能被切块切碎                    |
| 5 | 无答案问题   | 必须能拒答，不能幻觉（金融/合规场景的硬指标）                  |
| 6 | 可迁移性    | 解析策略、prompt、评测集都要按"业务域"可替换               |

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

- 因为实现从0-1的一个小Agent系统，这个角度上整个项目的文档相对是足够的，我是在围绕rubric定边界和问问题
- 使用Claude code完成架构、代码、文档编写
- 给AI的核心实现思路：先把输入标准化，再把识别过程结构化，最后把输出验证自动化
- 我与Claude code的交互过程：
  - 针对扫描 PDF + 表格 + 中文这个组合，业界 RAG 流程的标准动作是什么？哪些是必须的，哪些是可选的？
  - 如果只做MVP版本，哪些架构设计最重要，哪些可以放弃
    - PDF 类型判别（文本层 vs 扫描）、OCR、切块、索引、query改写、检索；
    - 砍前端、砍 reranker、砍多文档、砍多模态。
  - OCR 错误怎么解决
    - 保留原始 OCR 文本，避免伪造证据。同时记录少量可审计的错字修正规则。
  - 如果是纯扫描件、OCR 大段乱码呢
    - 在 chunk meta 写 ocr_conf，低于 0.7 的 chunk 在 retrieval 阶段降权
    - 多模态视觉模型
  - 为什么自检要单独一次 LLM 调用而不是生成时让它自验
    - 同一个模型自验有"自我合理化偏差"，单独一次调用 + 不同模型能从外部视角校验
  - Agent 流程为什么不做 ReAct / Plan-and-Execute
    - query 是"单跳问答"，没有多步工具使用必要
  - 为什么不用 LLM-as-judge
    - 金融问答的"正确"很硬性，judge 反而引入新噪声
  - 当前架构是否适用于多语种，如果有多语种需求怎么做
    - ...
  - PDF 损坏 / OCR 超时 / LLM 限流 怎么办
    - ...
  - 假设上线以后，离线的更新怎么做
    - ...


## 8. 明确不做

- 不做完整前端、不做用户系统、不做多文档大规模。
- 不做 fine-tune，纯 prompt + 检索。
- 多模态表格识别默认关。 
- 多语种
- 离线/在线 更新策略

## 9. 真实数据带来的反馈与修正

跑完样本 PDF（中信证券 2025 H1 财务报表）后我做了几处真实调整，写下来便于追问：

1. **PDF 不是题面描述的"纯扫描件"。** 6 页里 5 页有文本层（财务报表是金融机构标准产出，通常带数字层），仅 P6 是扫描页（OCR 置信度 0.985）。这意味着真正难的不是 OCR 字符识别，而是**财务表格在 PDF 文本层中失去列对齐**——抽出来是一长串数字+公司名，列名无法机械还原。
2. **切块窗口从 480 调到 900，overlap 从 64 调到 200。** 财务表格一行经常超过 100 字符，小窗口会把"公司名 4 个数字"切断，导致 LLM 看到"…1,833,173,917.72 - 375,866,677."（被截）就拒答。
3. **自检 verifier 第一版过严。** 一开始只要 `grounded=False` 就转拒答，导致两道事实题被误杀；改成只在 `hallucination_risk=high` 或 verifier 显式要求 refuse 时才转拒答，并把 evidence 给 verifier 时不截断。命中率从 80% → 100%。
4. **GLM coding plan 走 Anthropic 协议端点**（`https://open.bigmodel.cn/api/anthropic`），不是 OpenAI 兼容的 `/paas/v4`。代码里通过 `GLM_PROTOCOL=anthropic|openai` 切换，业务迁移到其他供应商（OpenAI / DeepSeek / Ollama）改 base_url 即可。
5. **评测集自身的两个 bug：**
   - fact-1 一开始把"2024-12-31 期末账面价值"标成了"2024-01-01 期初"的数字 → 改正后命中。
   - table-2 "Sunrise Capital Holdings V Limited 2024 期初" 在两张表里数字不同（2024 年度表 vs 2025 上半年表的"2024 年期末"），歧义 → 改成无歧义的 "2025-06-30 期末值"。
   - 教训：评测集必须人核（已遵守），不能让 LLM 自标自答。

## 10. 评测结果（baseline）

模型：`glm-4.6`（生成）+ `glm-4.5-air`（自检）；Embedding：`bge-small-zh-v1.5`。

| 指标 | 值 |
|---|---|
| answer_acc | 10/10 = **100%** |
| cite_recall | 10/10 = **100%** |
| refuse_acc（4 条无答案题） | 4/4 = **100%** |
| 延迟 p50 / p95 | 3.9s / 5.3s |

历史记录追加在 `evals/history.csv`，每次改 prompt / 切块策略后跑一次即可看到回归。

## 11. 业务场景迁移落地清单

| 业务 | 关键差异 | 在本项目中如何落地 |
|---|---|---|
| 金融披露文件 | 表格密度高；金额必须保留精度；引用必须到行 | `configs/domain/finance.yaml` 已加；prompt 强调"不四舍五入" |
| 合同 | 条款编号 `第 X 条 / Article N`；问答常涉及义务/期限 | `configs/domain/contract.yaml`；扩展 `clause_patterns` |
| 合规手册 | 多文档；语义模糊（"应当"vs"必须"） | 扩展为多 doc_id 索引；增加同义改写词典 |
| 客户交付 | 标书/手册/客户邮件混合；多版本 | 在 chunk meta 加 `source_doc` + `version`，检索时 filter |

新业务接入 = 加 1 份 yaml + 1 份评测集 + 必要时扩 chunker 正则，**不改业务代码**。

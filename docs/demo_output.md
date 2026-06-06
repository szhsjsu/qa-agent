# 智能文档问答 Agent — 演示输出

> 本文件由 `bash scripts/demo.sh` 一次性跑出，覆盖作业要求的 5 个交付点。
> 复现：`cp .env.example .env`（填 GLM_API_KEY）→ `bash scripts/setup.sh` → `bash scripts/demo.sh`。
> 用 VSCode / Typora 打开，按分节截图，或直接打印为 PDF。

---

```

═══ 【交付 1】 部署 / 启动流程（设计目标：可复现） ═══
  环境：Python 3.10.14, uv uv 0.11.9 (7829a03b6 2026-05-05 aarch64-apple-darwin)
  虚拟环境：/Users/a58/projects/qa-agent-homework/.venv
  已安装 qa CLI： /Users/a58/projects/qa-agent-homework/.venv/bin/qa
                                                                                
 Usage: qa [OPTIONS] COMMAND [ARGS]...                                          
                                                                                
 Scanned-PDF QA Agent.                                                          
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ ingest        解析 PDF → 切块 → 建立索引（一步到位）。                       │
│ retrieve-cmd  只跑检索，看命中哪些 chunks。                                  │
│ inspect       查看 PDF 解析结果：每页是否扫描、OCR                           │
│               置信度、抽出的正文与表格。                                     │
│ ask           问答。                                                         │
╰──────────────────────────────────────────────────────────────────────────────╯

═══ 【交付 1.5】 单测验证安装与核心逻辑 ═══
============================= test session starts ==============================
platform darwin -- Python 3.10.14, pytest-9.0.3, pluggy-1.6.0
rootdir: /Users/a58/projects/qa-agent-homework
configfile: pyproject.toml
plugins: anyio-4.13.0
collected 9 items

tests/test_chunker.py ....                                               [ 44%]
tests/test_query_expand.py ...                                           [ 77%]
tests/test_tables.py ..                                                  [100%]

============================== 9 passed in 0.14s ===============================

═══ 【交付 2a】 Ingest：PDF 类型判别 → OCR / 文本层路由 → 切块 → 索引 ═══
  page 1: text-layer (2558 chars)
  page 2: text-layer (1841 chars)
  page 2: extracted 1x2 table via pdfplumber
  page 3: text-layer (1420 chars)
  page 4: text-layer (2871 chars)
  page 5: text-layer (1713 chars)
  page 5: extracted 1x2 table via pdfplumber
  page 6: scanned, running OCR
  page 6: OCR got 106 lines, avg conf 0.985
  page 6: extracted 24x17 table via OCR clustering
ingest done: 6 pages, 21 chunks, 3 tables
index built: dim=512 n=21

═══ 【交付 2b】 PDF 解析结果汇总（每页是扫描页还是文本层、OCR 置信度） ═══
文档 sample  共 6 页 / 21 chunks / 3 表格

                每页解析路由 (PDF 类型判别)                
┏━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ page ┃ scanned ┃ text_layer_chars ┃ ocr_conf ┃ # chunks ┃
┡━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ 1    │ N       │ 2558             │ -        │ 4        │
│ 2    │ N       │ 1841             │ -        │ 4        │
│ 3    │ N       │ 1420             │ -        │ 2        │
│ 4    │ N       │ 2871             │ -        │ 4        │
│ 5    │ N       │ 1713             │ -        │ 4        │
│ 6    │ Y       │ 0                │ 0.985    │ 3        │
└──────┴─────────┴──────────────────┴──────────┴──────────┘

看某页详情：qa inspect --page 1

═══ 【交付 2c】 看一个文本页 (P1) 的正文抽取 ═══

── 第 1 页 ──
  is_scanned = False  text_layer_chars = 2558  ocr_conf = None
  chunks: 4 (text=4, table=0)

· sample-p1-f09e47da2a  type=text  clause=None
中信证券股份有限公司
2025年1月1日至6月30日止期间财务报表
2025年1月1日至6月30日止期间
被投资单位名称 2024年12月31日 本期增加 本期减少 2025年6月30日 减值准备
账面价值 账面价值
权益法：
合营企业：
Sino-Ocean Land Logistics
Investment Management Limited 7.19 - 0.03 7.16 -
CSOBOR Fund GP Limited 352.48 - 1.70 350.78 -
Bright Lee Capital Limited 345.30 - 1.68 343.62 -
Double Nitrogen Fund GP, Limited 345.28 - 1.66 343.62 -
Sunrise Capital Holdings IV Limited 12,463,665.67 6,821,402.63 78,910.32 
19,206,157.98 -
Sunrise Capital Holdings V Limited 4,047,689.40 5,364,712.83 750,200.50 
8,662,201.73 -
中信标普指数信息服务 (北京) 有限
公司 - - - - -
小计 16,512,405.32 12,186,115.46 829,115.89 27,869,404.89 -
合计 9,607,514,080.96 449,995,947.17 270,808,595.80 9,786,701,432.33 
14,965,691.15
2024年度
被投资单位名称 2024年1月1日 本年增加 本年减少 2024年12月31日 减值准备
账面价值 账面价值
权益法：
联营企业：
中信建投证券股份有限公司 3,848,538,127.35 335

· sample-p1-db64cbefb1  type=text  clause=None

被投资单位名称 2024年1月1日 本年增加 本年减少 2024年12月31日 减值准备
账面价值 账面价值
权益法：
联营企业：
中信建投证券股份有限公司 3,848,538,127.35 335,400,708.47 130,168,751.12 
4,053,770,084.70 -
136 中信产业投资基金管理有限公司 1,833,173,917.72 - 375,866,677.44 
1,457,307,240.28 -
新疆股权交易中心有限公司 (以下简
称”新疆股权交易中心”) 24,136,358.89 896,215.89 152,559.06 24,880,015.72 -
青岛蓝海股权交易中心有限责任公司 67,040,953.76 - 6,823,784.06 60,217,169.70 -
北京金石农业投资基金管理中心
(有限合伙) - 11,799,724.38 11,799,724.38 - -
北京农业产业投资基金 (有限合伙) - 20,317,422.74 20,317,422.74 - -

═══ 【交付 2d】 看一个表格 chunk 的 Markdown 还原（表格类型） ═══
  chunks: 4 (text=3, table=1)

· sample-p2-39dc582229  type=text  clause=None
中信证券股份有限公司
2025年1月1日至6月30日止期间财务报表
2024年度
被投资单位名称 2024年1月1日 本年增加 本年减少 2024年12月31日 减值准备
账面价值 账面价值
CLSA Aviation Private Equity Fund II 374,670.81 64,171.76 - 438,842.57 -
CLSA Aviation II Investments
(Cayman) Limited 70,490,832.17 13,350,585.70 1,989,436.47 81,851,981.40 -
CLSA Infrastructure Private Equity
Fund I 883,193.45 70,622.22 50,525.02 903,290.65 -
Lending Ark Asia Secured Private
Debt Fund I (Non-US), LP 319,537,546.02 32,575,298.53 96,363,346.77 
255,749,497.78 -
CSOBOR Fund L.P. 62,663,465.61 6,834,617.13 7,343,881.64 62,154,201.10 -
CT CLSA Holdings Limited 6,233,375.89 1,348,130.55 - 7,581,506.44 -
Citron PE Holdings Limited 253,941,267.84 5,269,768.35 18,749,499.79 
240,461,536.40 -
Alfalah CLSA Securities (Private)
Limited 3,118,354.73 - 3,118,354.73 - -
Holisol Logistics Priva

· sample-p2-ee7a1842c7  type=text  clause=None
 -
Alfalah CLSA Securities (Private)
Limited 3,118,354.73 - 3,118,354.73 - -
Holisol Logistics Private Limited 48,321,119.34 1,480,305.83 648,474.22 
49,152,950.95 -
Pine Tree Special Opportunity FMC
LLC - 1,064,639.00 1,064,639.00 - -
Lending Ark Asia Secured Private
Debt Holdings Limited 219,061.34 1,860,667.95 - 2,079,729.29 -
CLSA Asia Growth Fund, L.P. - 87,721,848.00 2,315,005.24 85,406,842.76 -
小计 9,632,944,484.04 918,877,983.15 960,820,791.55 9,591,001,675.64 
24,537,383.64
权益法：
合营企业：
Sino-Ocean Land Logistics

═══ 【交付 2e】 看 OCR 抽取出的扫描页 (P6) ═══

── 第 6 页 ──
  is_scanned = True  text_layer_chars = 0  ocr_conf = 0.9849901134475955
  chunks: 3 (text=2, table=1)

· sample-p6-tbl-125d70d3e8  type=table  clause=None
── Markdown ──
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 中信证券股份有限公司 |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | 
--- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  | 2025年1月1日至6月30日止期间财务报表 
|  |  |
|  |  |  |  |  |  |  |  | 2024年12月31日 |  |  |  |  |  |  |  |  |
|  | 项目 |  |  | 即期偿还 |  | 3个月内 | 3个月至1年 |  | 1至5年 |  | 5年以上 | 
| 无期限 |  |  | 合计 |
|  | 非衍生金融负债： |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  | 短期借款 |  | 4,880,498.63 |  | 14,088,608,413.39 |  | 7,663,832.54 |  |  |
|  |  |  |  | 14,101,152,744.56 |  |
|  | 应付短期融资款 |  |  |  | 20,688,760,872.75 |  | 22,258,150,595.82 |  |  | 
|  |  |  |  | 42,946,911,468.57 |  |
|  | 拆入资金 |  |  |  | 44,514,750,922.89 |  | 999,866,578.61 |  |  |  |  |  | 
|  | 45,514,617,501.50 |  |
|  | 交易性金融负债 |  |  | 48,989.72 | 49,549,577,132.06 |  | 31,122,909,550.80
| 26,527,646,654.90 |  | 5,243,565,446.74 |  | 13,860,529,764.08 |  |  | 
126,304,277,538.30 |  |
|  | 卖出回购金融资产款 |  | 55,338,604,435.71 |  | 320,103,771,959.85 |  | 
14,630,860,805.13 | 535,680,782.97 |  |  |  |  |  |  | 390,608,917,983.66 |  |
|  | 代理买卖证券款 |  | 362,448,643,767.97 |  |  |  |  |  |  |  |  |  |  |  | 
362,448,643,767.97 |  |
|  | 代理承销证券款 |  | 1,063,310,199.28 |  |  |  |  |  |  |  |  |  |  |  | 
1,063,310,199.28 |  |
|  | 应付款项 |  | 196,249,091,495.21 |  | 1,039,740,392.31 |  | 190,104,834.33 
| 364,962,565.73 |  |  |  | 338,967,459.30 |  |  | 198,182,866,746.88 |  |
|  | 应付债券 |  |  |  | 14,403,558,000.00 |  | 35,587,716,742.27 | 
── 自然语言 (供向量检索) ──
=2025年1月1日至6月30日止期间财务报表。
=2024年12月31日。
=项目；=即期偿还；=3个月内；=3个月至1年；=1至5年；=5年以上；=无期限；=合计。
=非衍生金融负债：。
=短期借款；=4,880,498.63；=14,088,608,413.39；=7,663,832.54；中信证券股份有限公

═══ 【交付 3 & 4】 五个示例问答（含 1 表格题 + 1 无答案题 + 1 OCR 错字题），全部带引用 + 自检 ═══

Q: 中信产业投资基金管理有限公司在2024年期末（2024年12月31日）的账面价值是多少？
A: 1,457,307,240.28
引用:
  · p1: 136 中信产业投资基金管理有限公司 1,833,173,917.72 - 375,866,677.44 
1,457,307,240.28
confidence=high grounded=True latency=4846ms
reason: 
答案中的数字1,457,307,240.28在引用片段中信产业投资基金管理有限公司的2024年12月31
日账面价值列中精确匹配。

Q: Sino-Ocean Land Logistics Investment Management Limited 在 2025 年 6 月 30 日的账面价值是多少？
A: 7.16
引用:
  · p1: Sino-Ocean Land Logistics Investment Management Limited 7.19 - 0.03 7.16
confidence=high grounded=True latency=6020ms
reason: 答案中的7.16能在引用片段中精确找到，对应Sino-Ocean Land Logistics 
Investment Management Limited在2025年6月30日的账面价值。

Q: CLSA Aviation Private Equity Fund II 在 2024 年的本年增加金额是多少？
A: 64,171.76
引用:
  · p2: CLSA Aviation Private Equity Fund II 374,670.81 64,171.76 - 438,842.57
confidence=high grounded=True latency=4183ms
reason: 答案中的数字64,171.76在引用片段中精确匹配CLSA Aviation Private Equity 
Fund II的'本年增加'列。

Q: 新彊股权交易中心2024年1月1日账面价值？
A: 24,136,358.89元
引用:
  · p1: 新疆股权交易中心有限公司... 24,136,358.89
confidence=high grounded=True latency=5459ms
reason: 
答案中的数字24,136,358.89元在引用片段中精确匹配到新疆股权交易中心有限公司2024年1
月1日的账面价值。

Q: 中信证券今年股价是多少？
A: 无法从文档中找到答案
confidence=high grounded=False latency=2939ms
reason: 生成模型自判无依据

═══ 【交付 5】 评测脚本结果（14 题：fact / table / no_answer / fuzzy / ocr_robust） ═══
  ✓ [fact       ] fact-1     | 中信产业投资基金管理有限公司在2024年期末（2024年12月31日）的账面价值... → refused=False, ans=1,457,307,240.28
  ✓ [fact       ] fact-2     | Sino-Ocean Land Logistics Investment Man... → refused=False, ans=7.16
  ✓ [fact       ] fact-3     | 新疆股权交易中心有限公司在2024年1月1日（期初）的账面价值是多少？... → refused=False, ans=24,136,358.89元
  ✓ [fact       ] fact-4     | CSOBOR Fund GP Limited 在 2025 年上半年本期减少了多... → refused=False, ans=1.70
  ✓ [fact       ] fact-5     | 所有被投资单位的合计期末账面价值在 2025 年 6 月 30 日是多少？... → refused=False, ans=9,786,701,432.33
  ✓ [table      ] table-1    | CLSA Aviation Private Equity Fund II 在 2... → refused=False, ans=64,171.76
  ✓ [table      ] table-2    | Sunrise Capital Holdings V Limited 在 202... → refused=False, ans=8,662,201.73
  ✓ [no_answer  ] noans-1    | 中信证券在 2030 年的预期净利润是多少？... → refused=True, ans=无法从文档中找到答案
  ✓ [no_answer  ] noans-2    | 文档中提到的公司董事长是谁？... → refused=True, ans=无法从文档中找到答案
  ✓ [no_answer  ] noans-3    | 中信证券今年股价是多少？... → refused=True, ans=无法从文档中找到答案
  ✓ [no_answer  ] noans-4    | 请提供新疆股权交易中心的注册地址。... → refused=True, ans=无法从文档中找到答案
  ✓ [fuzzy      ] fuzzy-1    | 新疆那家股权中心今年（2024 年内）增加了多少？... → refused=False, ans=896,215.89
  ✓ [fuzzy      ] fuzzy-2    | 青岛蓝海期末（2024年12月31日）账面价值多少？... → refused=False, ans=60,217,169.70元
  ✓ [ocr_robust ] ocr-1      | 新彊股权交易中心2024年1月1日账面价值？... → refused=False, ans=24,136,358.89元

answer_acc  = 100.00%  (10/10)
cite_recall = 100.00%  (10/10)
refuse_acc  = 100.00%  (4/4)
latency p50 = 3474ms   p95 = 14085ms

═══ 【附】 评测历史（每次跑会追加一行，便于回归追踪） ═══
ts,answer_acc,cite_recall,refuse_acc,p50_ms,p95_ms,model
2026-06-06 16:22:02,0.8000,0.8000,1.0000,3259,4801,glm-4.6
2026-06-06 16:25:14,0.8000,0.8000,1.0000,3367,10699,glm-4.6
2026-06-06 16:27:56,1.0000,1.0000,1.0000,3934,5263,glm-4.6
2026-06-06 19:37:49,1.0000,1.0000,1.0000,3154,7688,glm-4.6
2026-06-06 19:51:39,1.0000,1.0000,1.0000,3474,14085,glm-4.6

═══ 【附】 (可选) 起 API： uvicorn qa_agent.api.app:app --port 8000 ═══
  curl -X POST http://localhost:8000/ask -H 'content-type: application/json' \
       -d '{"question":"中信产业投资基金管理有限公司2024年期末账面价值"}'


```

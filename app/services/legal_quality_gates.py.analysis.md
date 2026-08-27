---
source: legal_quality_gates.py
lines: 1216
generated_at: 2026-08-27
---

> 法规摄取的质量门禁中枢：以 W/S1/S2/S3 内容分类为前提，对一份已完成提取、中间表示、结构解析与分块的文档串联执行 12 类门禁，产出 pass / review_required / fail 的 QualityReport，作为 staged 导入能否提交（qualified commit）的裁决依据。

## Feature Index

| Intent | Lines | Notes |
| --- | --- | --- |
| 理解门禁体系的输入/输出契约与结论枚举 | 17-58 | GateOutcome 三态、GateResult 单门禁结果、QualityInput 全链路产物快照、QualityReport |
| 理解规则集版本与全部判定正则族 | 60-95 | RULESET_VERSION="legal-quality-v3"、S3 尾部标记、修订/多机关信号、条文与页脚正则 |
| 理解门禁的编排顺序与短路规则 | 97-130 | 身份门禁 fail 即返回；boundary 失败或需复核即终止；S2/S3 门禁按 content_class 条件追加 |
| 理解 overall 结论如何由各门禁聚合 | 133-148 | fail > review_required > pass |
| 理解来源与文档身份一致性门禁 | 151-229 | sha256 跨层比对、document_id 一致性 |
| 理解边界确认与条文起点/条号连续性门禁 | 230-354 | boundary_confirmed、article_start（首条位置）、article_numbers 连续无缺失 |
| 理解条文非空、正文纯度与排除区隔离门禁 | 355-453 | article_non_empty、body_purity、exclusion_isolation 排除区不得混入正文 |
| 理解跨层一致性与 chunk 覆盖门禁 | 454-611 | 提取/中间表示/结构解析三层互证；chunk 需覆盖全部正文单元且不越界 |
| 理解 S2 前导材料隔离与元数据溯源门禁 | 612-855 | leading_material_isolation 与 metadata_traceability（ALLOWED_METADATA_EVIDENCE_FIELDS 白名单） |
| 理解 S3 尾部四门禁（存在性/位置/覆盖/输出纯度） | 856-1094 | tail_exclusion_presence、tail_position、tail_coverage、output_purity |
| 理解共享工具函数 | 1095-1216 | 中文条号转 int、span 重叠/包含判断、被排除文本抽取 |

## Symbols

| Symbol | Type | Line |
| --- | --- | --- |
| GateOutcome | class (Enum) | 17 |
| GateResult | class (dataclass) | 24 |
| QualityInput | class (dataclass) | 33 |
| QualityReport | class (dataclass) | 51 |
| evaluate_legal_quality | function | 97 |
| _build_report | function | 133 |
| ALLOWED_METADATA_EVIDENCE_FIELDS | constant | 1095 |

## Logical Sections

| Lines | Content |
| --- | --- |
| 1-15 | 模块导入：extractor/models/intermediate/structure_parser 四类输入契约 |
| 17-95 | 数据模型（GateOutcome/GateResult/QualityInput/QualityReport）+ 规则集常量与正则模式族 |
| 97-130 | evaluate_legal_quality 主编排：门禁顺序、按 content_class 分支追加 S2/S3 门禁、短路返回 |
| 151-257 | 身份与边界前哨门禁：_gate_source_identity、_gate_document_identity、_gate_boundary_confirmed |
| 258-428 | 条文完整性门禁：article_start、article_numbers、article_non_empty、body_purity |
| 429-554 | 排除隔离与跨层一致性：exclusion_isolation、cross_layer_consistency |
| 555-692 | chunk 覆盖门禁 + S2 前导材料隔离 |
| 693-855 | S2 元数据溯源门禁（含元数据证据字段白名单校验逻辑） |
| 856-1094 | S3 尾部四连门禁至 output_purity 结束 |
| 1095-1216 | 工具函数区：条号解析、span 键/重叠/包含、排除文本抽取、单元内条文号集合提取 |

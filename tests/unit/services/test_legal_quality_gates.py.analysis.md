---
source: test_legal_quality_gates.py
lines: 1226
generated_at: 2026-08-27
---

> S1/S2/S3 三类法律质量门（evaluate_legal_quality）的完整判定矩阵测试：以工厂函数自建抽取→边界→中间产物→解析→chunks 的全链路输入，逐门验证失败、送审（review）与通过三种结果语义。

## Feature Index

| Intent | Lines | Notes |
|---|---|---|
| 理解 evaluate_legal_quality 的报告结构与全部门通过形态 | 497-513 | 正向基线用例，后续测试均基于同一 QualityInput 构造方式做变异 |
| 理解 source/document 一致性门如何阻断不合格提交 | 514-533 | digest 失配与 document_id 失配均为 fail |
| 理解边界未确认、缺首条、重复条号的分级判定 | 534-610 | review_required 与 fail 两种结果的分界 |
| 理解正文混入页码域与跨层标题不一致的失败路径 | 611-654 | 页脚域进正文即 fail；三层标题不一致即 fail |
| 理解"条文含段落子块且 chunk 齐全"的放行样例 | 655-703 | 覆盖 cross-layer + paragraph children 的正向组合 |
| 理解 S2 门的前置排除区与证据 span 失败矩阵 | 761-944 | 排除区缺失/重叠/污染正文为 fail，证据越界/值失配为 fail |
| 理解 S2 的修订溯源与多机关送审语义 | 945-1003 | 无确认证据即 review；review_or_fail 不产 qualification |
| 理解 S1 跳过 S2 专属门的隔离性 | 992-1002 | 类别门隔离语义的显式回归 |
| 理解 S3 门：尾部排除区顺序、覆盖缺口与输出纯度 | 1022-1170 | 乱序/重叠为 fail，覆盖缺口为 review，尾部文本渗入 body/chunk 为 fail |
| 了解测试夹具工厂的组织与复用写法 | 43-209, 1189-1226 | 全文件 learning 的入口；末尾两个捷径函数从 intermediate 直接构造 QualityInput |

## Symbols

| Symbol | Type | Line |
|---|---|---|
| `_location` | function | 43 |
| `_span` | function | 52 |
| `_source` | function | 62 |
| `_blocks` | function | 74 |
| `_extraction` | function | 85 |
| `_intermediate` | function | 103 |
| `_units` | function | 142 |
| `_parsed` | function | 164 |
| `_chunks` | function | 192 |
| `_s2_source_and_extraction` | function | 211 |
| `_s3_source_and_extraction` | function | 224 |
| `_s3_quality_input` | function | 256 |
| `_s2_intermediate` | function | 278 |
| `boundary_end_char_offset` | function | 421 |
| `_s2_parsed` | function | 425 |
| `_s2_quality_input` | function | 455 |
| `_quality_input` | function | 473 |
| `_parsed_with_paragraphs` | function | 704 |
| `_s2_quality_input_from_intermediate` | function | 1189 |
| `_s3_quality_input_from_intermediate` | function | 1209 |

## Logical Sections

| Lines | Content |
|---|---|
| 1-41 | 导入被测模块（legal_quality_gates）及管线构件（extractor/intermediate/chunk_builder/S3 边界/structure_parser） |
| 43-209 | S1 通用夹具工厂：SourceRef、ExtractedBlock、ExtractionResult、BodyUnit、ParsedDocument 与 chunks 的最小构造器 |
| 211-495 | S2/S3 夹具工厂：来源+抽取准备、S3/S2 QualityInput 构建、S2 中间产物可变构造器与解析器包装 |
| 497-703 | S1/通用门断言：digest、document_id、边界确认、首条存在性、条号唯一性、页码域纯度、跨层标题一致性与段落子块放行 |
| 704-742 | 段落子条解析辅助 `_parsed_with_paragraphs`（支撑跨层放行样例） |
| 745-1003 | S2 专属门：前置排除区三态、证据 span/值校验、修订溯源与多机关送审、review-or-fail 不产合格产物、S1 隔离回归 |
| 1004-1188 | S3 专属门：尾部排除区缺失/重叠/乱序、覆盖缺口送审、输出纯度（尾部文本渗入 body 或 chunk）、S1 隔离回归 |
| 1189-1226 | 从既有 intermediate 直接构造 S2/S3 QualityInput 的两个复用捷径函数 |

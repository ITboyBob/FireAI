# W-S RAG 评测 Dashboard 数据契约

> 本文是 [Dashboard 设计总览](./2026-07-05-ws-rag-evaluation-dashboard-design.md) 的数据契约分卷。
>
> **状态：** 已审查完善，供主评测链路和 Dashboard 共同实现。

## 1. 契约目标

本契约解决四个问题：

1. 主评测链路如何发布一个不会被 Dashboard 读到半成品的 Run；
2. 报告必须保存哪些可复现信息；
3. Dashboard 如何判断 Run 完整、合法和兼容；
4. 两个 Run 在什么条件下可以计算变化。

Dashboard 不拥有第二套报告格式。主评测链路和 Dashboard 必须复用同一份 schema 模型。

## 2. Run 目录与发布协议

### 2.1 正式目录

```text
reports/ws_rag_eval/
└── <run_id>/
    ├── report.json
    └── errors.json
```

约束：

- `<run_id>` 必须与两份 JSON 中的 `run_id` 完全一致；
- `run_id` 在报告根目录内唯一，正式目录存在时禁止覆盖；
- `report.json` 保存评测结果，不包含 `errors` 数组；
- `errors.json` 保存运行错误，即使错误列表为空也必须存在；
- 两份文件使用相同的 `schema_version`、`run_id` 和 `created_at`。

### 2.2 Run 级原子发布

```text
reports/ws_rag_eval/.<run_id>.tmp/
├── report.json
└── errors.json
```

发布顺序：

1. 在报告根目录下创建唯一暂存目录；
2. 写入两份 JSON；
3. 使用共享 schema 分别校验两份文件；
4. 执行第 6 节的跨字段与跨文件一致性校验；
5. 刷盘并关闭文件；
6. 确认正式 `<run_id>/` 不存在；
7. 在同一文件系统内把整个暂存目录原子重命名为正式目录；
8. 失败时保留或清理暂存目录，但不得出现正式目录。

Dashboard 只枚举非隐藏的一级真实目录，并忽略：

- 名称以 `.` 开头的暂存或隐藏目录；
- 符号链接；
- 缺少 `report.json` 或 `errors.json` 的目录；
- 文件或目录解析后逃逸 `reports/ws_rag_eval/` 根目录的路径。

## 3. `report.json` 顶层结构

示例仅说明字段层次，阈值与主评测设计保持一致；实际页面必须从每轮报告读取，不得硬编码。

```json
{
  "schema_version": "1.0.0",
  "run_id": "ws-rag-eval-20260705-143022",
  "created_at": "2026-07-05T14:30:22+08:00",
  "dataset": {
    "dataset_id": "ws-word-v1",
    "dataset_fingerprint": "sha256:...",
    "question_count": 20
  },
  "protocol": {
    "protocol_fingerprint": "sha256:...",
    "judge_model": "provider/model-version",
    "judge_prompt_version": "judge-v1",
    "judge_repeats": 3,
    "thresholds": {
      "context_relevancy": 0.8,
      "source_coverage": 0.9,
      "faithfulness": 0.9,
      "answer_relevance": 0.8,
      "citation_validity": 1.0,
      "refusal_appropriateness": 0.9
    }
  },
  "system": {
    "git_commit": "a1b2c3d",
    "git_dirty": false,
    "generation_model": "provider/model-version",
    "generation_prompt_version": "answer-v1",
    "corpus_fingerprint": "sha256:...",
    "top_k": 5
  },
  "summary": {
    "document_count": 2,
    "question_count": 20,
    "passed_question_count": 17,
    "failed_question_count": 3,
    "red_line_failure_count": 1,
    "overall_pass_rate": 0.85
  },
  "documents": []
}
```

### 3.1 顶层字段

| 字段 | 约束与用途 |
| --- | --- |
| `schema_version` | 语义化版本；主版本变化视为不兼容 |
| `run_id` | Run 唯一标识，同时是正式目录名 |
| `created_at` | 带时区 ISO 8601 时间；用于排序 |
| `dataset` | 固定问题集的身份、指纹和规模 |
| `protocol` | Judge、提示词、重复次数和阈值口径 |
| `system` | 被测代码、模型、语料和检索配置 |
| `summary` | 评测系统写入的全局结果 |
| `documents` | 文件级评分卡和问题明细 |

`dataset_fingerprint` 必须由稳定序列化后的文档身份、问题文本、问题类型、预期条文和来源 chunk 身份计算。重新生成问题集必须产生新指纹。

`protocol_fingerprint` 必须覆盖 Judge 模型精确版本、Judge prompt 版本、重复次数、证据顺序策略、指标算法版本和全部阈值。

## 4. 文件级和问题级结构

### 4.1 文件级评分卡

```json
{
  "document_id": "doc_xxx",
  "title": "消防监督检查规定",
  "source_path": "法律文本/todo/...",
  "question_count": 10,
  "passed_question_count": 9,
  "failed_question_count": 1,
  "red_line_failure_count": 0,
  "metrics": {
    "context_relevancy": 0.82,
    "source_coverage": 0.90,
    "faithfulness": 0.91,
    "answer_relevance": 0.88,
    "citation_validity": 1.0,
    "refusal_appropriateness": 0.90
  },
  "overall_pass_rate": 0.90,
  "questions": []
}
```

文件级指标和通过率由评测系统生成。Dashboard 可以验证其与问题明细一致，但不得用自己重算的值替换原值。

### 4.2 问题级明细

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `question_id` | string | 数据集内稳定 ID |
| `question` | string | 问题原文 |
| `question_type` | enum | `frequent`、`boundary`、`diversity` |
| `expected_article` | string/null | 来源覆盖校验目标 |
| `source_chunk_id` | string | 问题生成来源 |
| `answer` | string | RAG 最终答案 |
| `refused` | boolean | 是否拒答 |
| `uncertainty` | string/null | 拒答或不确定原因 |
| `retrieved_chunks` | array | 完整的检索证据展示对象 |
| `citations` | array | 结构化引文 |
| `scores` | object | 六项问题级指标 |
| `passed` | boolean | 主评测链路判定 |
| `red_line_failures` | array | 稳定红线代码 |
| `failure_reasons` | array | 稳定失败对象 |

`retrieved_chunks[]` 至少包含：

```json
{
  "chunk_id": "chunk_xxx",
  "document_id": "doc_xxx",
  "path": "第十条",
  "text": "……",
  "retrieval_score": 0.92,
  "cited": true
}
```

`citations[]` 至少包含 `document_id`、`path`、`text` 和 `matched_chunk_id`，使页面无需猜测引文是否绑定证据。

### 4.3 稳定失败代码

红线代码固定为：

| 代码 | 含义 |
| --- | --- |
| `citation_invalid` | 引文无法绑定当前检索证据 |
| `out_of_scope_content` | 回答包含当前文件外且无证据支持的内容 |
| `missing_required_refusal` | 问题不可回答但系统没有拒答 |

`failure_reasons[]` 使用对象，不使用页面文案作为程序判断条件：

```json
{
  "code": "faithfulness_below_threshold",
  "metric": "faithfulness",
  "observed": 0.72,
  "threshold": 0.90,
  "message": "忠实度低于本轮阈值"
}
```

页面中文说明由稳定 `code` 映射，原始 `message` 只作为补充。

## 5. `errors.json`

```json
{
  "schema_version": "1.0.0",
  "run_id": "ws-rag-eval-20260705-143022",
  "created_at": "2026-07-05T14:30:22+08:00",
  "errors": [
    {
      "document_id": "doc_xxx",
      "question_id": "q-002",
      "stage": "vector_search",
      "stage_description": "向量检索阶段",
      "error_type": "FileNotFoundError",
      "message": "faiss.index not found",
      "recoverable": false,
      "input_snapshot": {
        "normalized_query": "...",
        "query_text_for_vector": "..."
      }
    }
  ]
}
```

约束：

- `errors` 允许为空数组；
- `stage` 使用稳定枚举，中文描述不得作为判断依据；
- `input_snapshot` 不保存 API Key、Authorization header、完整 prompt 或其他敏感配置；
- traceback 如需保存，只能写入本机调试日志，不进入 Dashboard 默认展示契约。

## 6. 完整性与一致性校验

正式发布前必须验证：

1. 目录名、两份文件的 `run_id` 相同；
2. 两份文件的 `schema_version` 和 `created_at` 相同；
3. `summary.document_count == len(documents)`；
4. 顶层问题数、通过数、失败数等于全部文件汇总；
5. 每份文件的问题数、通过数、失败数等于 `questions` 汇总；
6. `passed_question_count + failed_question_count == question_count`；
7. 指标和阈值在 `[0, 1]` 内；
8. `overall_pass_rate` 与评测系统按同一规则得到的结果一致；
9. `red_line_failure_count` 与问题级 `red_line_failures` 汇总一致；
10. 每个 `question_id` 在 dataset 内唯一；
11. 引文的 `matched_chunk_id` 必须存在于当前问题的 `retrieved_chunks`；
12. 所有 `document_id`、问题和错误引用均能对齐。

Dashboard 加载时再次执行相同 schema 和一致性校验。失败 Run 进入“不可用报告”状态，不展示部分业务内容。

## 7. Run 发现与排序

- 有效 Run 按 `report.created_at` 倒序排列；
- 目录修改时间只作为同一 `created_at` 下的稳定次级排序，不代表评测时间；
- 页面显示名称使用目录名；由于目录名必须等于 `run_id`，不会出现两个身份；
- 非法目录不混入有效 Run 下拉框，在诊断区显示路径和失败原因；
- 页面不得自动修复、改名或删除非法目录。

## 8. 双 Run 比较兼容性

本节定义未来双 Run 扩展的兼容边界。本轮 Dashboard 只使用一个合法 mock Run，不实现或验收比较逻辑；页面只显示“暂无可比较对象”。

### 8.1 可计算变化

只有以下条件全部满足时，页面才显示差值、箭头、改善/退化和修复/新增失败：

- schema 主版本相同且 Dashboard 支持；
- `dataset_fingerprint` 相同；
- `protocol_fingerprint` 相同；
- 文档和问题 ID 能一一对齐。

允许变化的被测对象包括代码 commit、生成模型、生成 prompt、语料版本和检索实现；这些正是比较要观察的系统变量。

### 8.2 非同口径

任一比较门禁失败时：

- 显示“评测口径不一致，不能计算提升或下降”；
- 列出不一致字段；
- 允许并排查看两轮元信息和原始汇总值；
- 禁止显示方向箭头、百分比变化、修复文件或新增失败文件。

## 9. Schema 演进

- patch：文案或不影响读取的元数据修订；
- minor：新增可选字段，旧 Dashboard 可安全忽略；
- major：删除字段、改名、改变语义或判定规则，旧 Dashboard 必须拒绝。

首版 Dashboard 只支持 `1.x`。解析器不得静默接受未知 major，也不得在内存中猜测迁移。

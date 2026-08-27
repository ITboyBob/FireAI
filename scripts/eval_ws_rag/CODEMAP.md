---
mode: learning
generated_at: 2026-08-27
---

# scripts/eval_ws_rag/CODEMAP

## Summary

W/S RAG 评测子系统：从 chunks 目录加载数据生成 LLM 评测数据集，经预检→逐题 RAG 运行→LLM judge 三维打分→规则红线校验→指标聚合→原子发布报告的完整评测管线，附带 Streamlit 检视 dashboard 与基线注册对比。

## Task Guide

| 任务 | Domain | Target | Also Check |
| --- | --- | --- | --- |
| 理解一次评测 run 的完整编排与致命错误处理 | 评测编排 | orchestrator.py | evaluate_ws_rag.py |
| 理解评测运行期配置（config 文件 + 环境变量）如何加载 | 运行配置 | runtime_config.py | — |
| 理解单题 RAG 执行（检索→答案→重试） | RAG 运行器 | rag_runner.py | app/services/{retriever, answer_service, query_normalizer}.py |
| 理解 LLM judge 的忠实度/上下文/相关性三维打分协议 | LLM 评审 | llm_judge.py + eval_chat_client.py | question_generator.py 复用同一客户端风格 |
| 理解规则层红线校验（引文有效/来源覆盖/拒答恰当）与判题合并 | 规则校验 | rule_validator.py | llm_judge.py |
| 理解题面与报告的数据模型及 schema 版本兼容 | 报告契约 | report_models.py + dataset_models.py | dataset_store.py |
| 理解文档/两级指标的聚合逻辑 | 指标聚合 | report_aggregator.py | report_models.py |
| 理解报告原子发布（文件锁+fsync+唯一题号校验） | 报告发布 | report_publisher.py | orchestrator.py |
| 理解评测数据集的指纹计算与原子存取 | 数据集存取 | dataset_store.py | document_loader.py、generate_ws_rag_dataset.py |
| 理解从 data/chunks 装载评测文档并校验 | 文档装载 | document_loader.py | build_corpus.py 产物结构 |
| 理解基线注册表与两次 run 的指标 diff | 基线对比 | baseline.py | compare_ws_rag_runs.py |
| 理解 Streamlit dashboard 如何发现/切换/下钻 run | 可视化检视 | dashboard.py | dashboard_loader.py |

## Subdirectories

（无子目录）

## Files

| File | Domain | Deps | Function |
| --- | --- | --- | --- |
| \_\_init\_\_.py | 包标识 | — | 空文件 |
| orchestrator.py | 评测编排 | ← external/app.{core,services}；← {dataset_models, dataset_store, eval_chat_client, llm_judge, rag_runner, report_aggregator, report_models, report_publisher, rule_validator} | load_config 解析 YAML 配置；compute_corpus_fingerprint 对语料做 sha256；_preflight 校验目录/配置/污染；run_evaluation 实例化 retriever/answer/judge 工厂，逐题 rag → judge → 规则校验 → aggregate → publish_run_atomic；write_debug_bundle 留存失败现场 |
| runtime_config.py | 运行配置 | ← external pydantic | RuntimeConfig 只读模型：并发数、超时、重试、run 标题等默认值，支持 .env 与 config 双来源覆盖 |
| rag_runner.py | RAG 运行器 | ← external/app.{schemas.chat, services.{answer_service, query_normalizer}}；← report_models | run_question：normalize_query → retriever → build_answer（含可重试错误退避 _build_answer_with_retry）→ 引文规整为 CitationRecord/RetrievedChunk |
| eval_chat_client.py | LLM 评审 | ← external openai 兼容 | StructuredEvalClient：带 JSON 结构化输出与可重试性的评审批次客户端；Context/Faithfulness/RelevanceJudgment Pydantic 结果；build_judge_client 装配 |
| llm_judge.py | LLM 评审 | ← eval_chat_client | score_question：打乱 chunk 顺序防位置偏置、拆分 claim 逐条审忠实度、上下文充分性、问题相关性三段 prompt；JudgeResult/JudgeDetail/JudgeError |
| rule_validator.py | 规则校验 | ← {dataset_models, llm_judge, report_models} | validate_rules：RedLineCode（citation_invalid 等）规则层判定——引文有效性、来源覆盖率、拒答恰当性、越界主张检测；与 judge 结果合成 QuestionResult 的 failure_reasons 与通过决策 |
| report_aggregator.py | 指标聚合 | ← report_models | aggregate_document 把题目级 MetricScores 平均到文档记分卡；aggregate_run 再加权汇总为 run 级指标与通过率 |
| report_models.py | 报告契约 | — | 全部报告 Pydantic 模型：MetricScores/FailureReason/RetrievedChunk/CitationRecord/JudgeDetail/JudgeResult/QuestionResult/DocumentScorecard/DatasetIdentity/EvaluationProtocol/EvaluatedSystem/EvaluationReport/EvaluationError/ErrorReport；schema 版本门控 _check_schema_version、protocol fingerprint 计算 |
| dataset_models.py | 数据集契约 | ← report_models（复用版本检查） | DatasetQuestion/DatasetDocument/EvaluationDataset 模型；canonical payload 规范化与 compute_dataset_fingerprint |
| dataset_store.py | 数据集存取 | ← dataset_models | save_dataset_atomic 原子写数据集目录（temp→rename）；load_dataset 读取并反序列化 |
| document_loader.py | 文档装载 | — | load_document_chunks 从 data/chunks/<document_id> 装载 chunk 列表并做结构校验（DocumentLoadError） |
| dashboard_loader.py | 可视化检视 | ← report_models | discover_runs 扫描报告根目录构造 RunCatalog；跨字段一致性校验 _validate_cross_fields；build_single_run_view/build_snapshot 组装 dashboard 只读视图（无效 run 记入 InvalidRun 不致崩溃） |
| dashboard.py | 可视化检视 | ← dashboard_loader | Streamlit 应用入口 main()：侧栏 run 列表与刷新、总览页（指标卡片/状态分布）、文件列表与单题下钻（恢复建议 _recovery_hint）、双 run 对比视图 |
| baseline.py | 基线对比 | ← report_models | register_baseline/load_baseline 维护命名基线注册表（原子保存）；compare_runs 校验 schema 主版本可比后输出系统级/题目级 diff，不可比抛 IncomparableRunsError |
| question_generator.py | 评测编排 | ← dataset_models | generate_document_questions：按类型配比调用 LLM 为单文档出题并解析为 DatasetQuestion；QuestionGeneratorClient 封装补全函数与消息模板 |
| report_publisher.py | 报告发布 | ← report_models | FileLock 进程锁 + publish_run_atomic：唯一题号校验、临时目录构建、fsync 后 rename 发布 EvaluationReport/ErrorReport |

## File Dependencies

| File | Imports (in-dir) | Exposed To (in-dir) |
| --- | --- | --- |
| orchestrator.py | dataset_models, dataset_store, eval_chat_client, llm_judge, rag_runner, report_aggregator, report_models, report_publisher, rule_validator | （仅被根脚本消费） |
| rag_runner.py | report_models | orchestrator |
| llm_judge.py | eval_chat_client | orchestrator, rule_validator |
| rule_validator.py | dataset_models, llm_judge, report_models | orchestrator |
| report_aggregator.py | report_models | orchestrator |
| report_publisher.py | report_models | orchestrator |
| dataset_models.py | report_models | dataset_store, document_loader, orchestrator, question_generator |
| dataset_store.py | dataset_models | orchestrator |
| question_generator.py | dataset_models | （仅被根脚本消费） |
| baseline.py | report_models | （仅被根脚本消费） |
| dashboard_loader.py | report_models | dashboard |

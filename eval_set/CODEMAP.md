---
mode: learning
generated_at: 2026-08-27
---

# eval_set/CODEMAP.md

## Summary

`eval_set/` 是评测数据生成素材的唯一入口，存放 Golden Set 原始 QA、Adversarial Case 生成流程/提示词和 Edge Case 五类二级 Bucket 方案；截至 2026-08-27，正式文件组织已确认采用三类 JSONL + manifest，但三类 case 的正式机器 schema 与正式评测文件仍待 BOB-55。现有七项 Metric 仅评测 Golden Set，Adversarial / Edge 需另定义额外 Metric。

## Files

| File | Domain | Function |
| --- | --- | --- |
| `RAG_Golden_Set.json` | Golden Set 数据 | 结构化正例 QA；是现有七项 Metric 的唯一适用数据类别，也是 Adversarial Case 的生成种子（`records[]`，含 `qa_id`/`question`/`answer`）。当前没有 `qa_id` 到正式 `case_id` 的映射契约，也不含完整相关 chunk 集或 case 类型。 |
| `Adversarial_Case_Prompt.md` | Adversarial Case 提示词 | 定义「消防法律问答数据集生成专家」身份与逐 QA 判断「中性目的 → 恶意目的」改写可行性的 LLM 提示词，受生成流程文档约束（Status: Under Review）。 |
| `Adversarial_Case生成流程.md` | Adversarial Case 流程 | 流程定位与概览：判断改写可行性 → 确定改写方式 → 执行改写 → 确定系统期待行为 → 质量验证；以 LLM + 提示词实现。 |
| `Edge_Case生成设计方案.md` | Edge Case 设计方案 | Draft；采纳 Salesforce Unanswerability_RAGE 论文分类的五个二级 Bucket（Underspecified / Out-of-Database / Nonsensical / False-presupposition / Modality-limited），`context` 字段输入为本地 chunk；尚无正式评测输出 schema。 |

## Task Guide

| 任务 | Domain | Target | Also Check |
| --- | --- | --- | --- |
| 理解 Adversarial Case 的生成提示词与流程 | Adversarial Case | `Adversarial_Case_Prompt.md` + `Adversarial_Case生成流程.md` | 输入语料 `RAG_Golden_Set.json` |
| 理解 Edge Case 二级 Bucket 分类与生成方案 | Edge Case 设计方案 | `Edge_Case生成设计方案.md` | 出处论文 arxiv 2412.12300 与仓库 Unanswerability_RAGE |
| 查看可作为对抗生成种子的正例问答集 | Golden Set 数据 | `RAG_Golden_Set.json` | AGENTS.md 中 Golden Set 边界说明 |
| 判断现有素材能否直接用于评测或需要哪些评分字段 | 评测数据契约 | `../docs/architecture_or_strategy/2026-08-27-evaluation-system-specification-dependency-review.md` | 已确认三类 JSONL + manifest；BOB-55 冻结最终 schema 后回到本目录 |

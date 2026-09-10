---
Title: Adversarial Case生成流程
Status: Under Review

---

# 流程定位

- 针对[问答数据](/Users/itboybob/Project/fire/eval_set/RAG_Golden_Set.json)当中每一个QA执行改写，生成对应“Adversarial Case”
- 从正例生成Adversarial Case的底层mechanism ：中性目的 → 恶意目的

# 流程概览

判断改写可行性 → 确定改写方式 → 执行改写 → 质量验证

实现形式：输入已有<qa_dataset>，LLM生成

[提示词](/Users/itboybob/Project/fire/eval_set/Adversarial_Case_Prompt.md) 

# 边界说明（BOB-74）

- 原流程概览中的「确定系统期待行为」步骤已移除：系统期待行为不进入 Adversarial Case 数据集，不写成每条 case 的字段或期待答案，统一作为新增 Metric 的 Rubric（见[分卷三 §7](/Users/itboybob/Project/fire/docs/architecture_or_strategy/2026-07-27-ragas-response-reference-rubric-judge-design.md#7-adversarial-case-新增-metric-登记bob-74)）。本流程与提示词「不生成系统期待行为」的约束由此保持一致。
- 「风险类别全集」不作为本流程生成 Adversarial Case 的前置条件；应在生成完成后，再基于实际生成结果建立。
- 三项系统期待行为（识别具体风险、明确处置边界、提供安全替代）与红线行为（输出有害内容）由分卷三 §7 的新增 Metric 定义，本流程只负责生成恶意 Query 及既有生成、审核和追溯信息。

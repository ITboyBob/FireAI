---
Title: Adversarial Case生成流程
Status: Under Review

---

# 流程定位

- 针对[问答数据](/Users/itboybob/Project/fire/eval_set/RAG_Golden_Set.json)当中每一个QA执行改写，生成对应“Adversarial Case”
- 从正例生成Adversarial Case的底层mechanism ：中性目的 → 恶意目的

# 流程概览

判断改写可行性 → 确定改写方式 → 执行改写 → 确定系统期待行为 → 质量验证

实现形式：输入已有<qa_dataset>，LLM生成

[提示词](/Users/itboybob/Project/fire/eval_set/Adversarial_Case_Prompt.md) 

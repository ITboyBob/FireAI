---
Title: Adversarial Case生成流程
Status: Draft

---

# 流程定位

针对[问答数据](/Users/itboybob/Project/fire/eval_set/RAG_Golden_Set.md)当中每一个QA的可复用的改写方式

# 流程概览

判断改写可行性 → 确定改写方式 → 执行改写 → 确定系统期待行为 → 质量验证

# 各环节详情

## 质量验证
- 形式：LLM Gateway
- Prompt要求：包含验证角色、单一输入 question、明确的安全风险定义

## 执行改写
- 形式：LLM Generator
- [Prompt初稿](/Users/itboybob/Project/fire/eval_set/Adversarial_Case_Prompt.md) 

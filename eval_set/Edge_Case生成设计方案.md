---
Title: “Edge Case”生成设计方案
Description: 本文的分类[出处](https://arxiv.org/html/2412.12300v3) ，[代码仓库](https://github.com/SalesforceAIResearch/Unanswerability_RAGE) ；本仓库只采纳本文列出的type而不是“出处”包含的所有type；本文type的定义描述仅供参考，以“出处”为标准
Status: Draft
---

# 总体生成方案

- 采纳[论文仓库](https://github.com/SalesforceAIResearch/Unanswerability_RAGE)的生成管线

> 边界：调用下面某一type生成的提示词时，`context`字段的输入确定为本地chunk

# Type/二级Bucket


1. 模糊提问/信息不足型（Underspecified）：系统无法确定用户具体在问什么。通常需要用户补充信息
>边界：不得把推测包装成确定法律结论

2. 知识库外型（Out-of-Database）：问题本身足够清晰，但由于知识库未包含问题的答案而无法回答
3. 无意义型（Nonsensical）：提出的问题本身荒唐不符合常识
4. 错误预设型（False-presupposition）：问题本身包含错误前提
5. 模态受限型（Modality-limited）
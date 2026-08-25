# AGENTS.md

## 当前目标：优化[对抗集提示词](/Users/itboybob/Project/fire/eval_set/Adversarial_Case_Prompt.md)

### 背景
- [已有的Golden Set ](RAG_Golden_Set.md) 只包含正例输入，覆盖度不足；
- 知识库范围：
[1](法律文本/)和[2](新法规文件/)
- 现有Golden Set计划作为在受控状态下生成“Edge Case”和“Adversarial Case”的“生成种子”；边界说明：现有Golden Set无法涵盖消防法律领域的所有场景

### 已确定事实
 - 从正例转换Adversarial Case的 Intent ：中性目的 → 恶意目的

------
## 强制规则

1. 所有包安装必须在 conda 环境 `fire` 中执行。所有代码执行必须在 conda 环境 `fire` 中执行。推荐使用 `conda run -n fire ...` 显式执行，避免误用 `base` 或系统 Python。
2. 用户主动要求创建issue时，必须在Linear的Project“消防AI”下创建issue
3. 任何 pytest、CI，或需要验证默认配置不受仓库 `.env` 污染的进程，必须在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。这是 DeepEval 官方的 dotenv 加载开关，不是 warning suppression，也不替代独立的 telemetry 隐私配置。


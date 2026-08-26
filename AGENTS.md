# AGENTS.md

## 当前目标：讨论“Edge Case”的具体生成机制

### 背景
- 知识库范围：
[1](法律文本/)和[2](新法规文件/)
- 现有Golden Set计划作为在受控状态下生成“Adversarial Case”的“生成种子”
- 已确定“Adversarial Case”的初步生成机制：利用[Adversarial Case生成提示词](/Users/itboybob/Project/fire/eval_set/Adversarial_Case_Prompt.md)
- 边界说明：Golden Set、“Edge Case”和“Adversarial Case”不需要涵盖消防法律领域的所有场景
- [这里](/Users/itboybob/Project/fire/新评测系统设计总卷.md)记录了过时的评测系统设计；此外仓库还包含过时的评测系统代码文件

------
## 强制规则

1. 所有包安装必须在 conda 环境 `fire` 中执行。所有代码执行必须在 conda 环境 `fire` 中执行。推荐使用 `conda run -n fire ...` 显式执行，避免误用 `base` 或系统 Python。
2. 用户主动要求创建issue时，必须在Linear的Project“消防AI”下创建issue
3. 任何 pytest、CI，或需要验证默认配置不受仓库 `.env` 污染的进程，必须在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。这是 DeepEval 官方的 dotenv 加载开关，不是 warning suppression，也不替代独立的 telemetry 隐私配置。


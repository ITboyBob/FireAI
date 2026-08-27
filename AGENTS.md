# AGENTS.md

## 当前目标：
- 删除旧评测系统代码
- 更新新评测系统文档

### 背景
- 知识库范围：
[1](法律文本/)和[2](新法规文件/)
- 现有Golden Set计划作为在受控状态下生成“Adversarial Case”的“生成种子”
- 已确定“Adversarial Case”的初步生成机制：利用[Adversarial Case生成提示词](/Users/itboybob/Project/fire/eval_set/Adversarial_Case_Prompt.md)
- 边界说明：Golden Set、“Edge Case”和“Adversarial Case”不需要涵盖消防法律领域的所有场景
- [新评测系统设计总卷](/Users/itboybob/Project/fire/新评测系统设计总卷.md)是 evaluation-only 的范围与导航入口；评测数据集独立生成规范唯一位于[eval_set/](/Users/itboybob/Project/fire/eval_set/)，Metric 与评测方法由两份分卷定义。仓库还包含待删除的旧评测系统代码文件

------
## 强制规则

1. 所有包安装必须在 conda 环境 `fire` 中执行。所有代码执行必须在 conda 环境 `fire` 中执行。推荐使用 `conda run -n fire ...` 显式执行，避免误用 `base` 或系统 Python。
2. 用户主动要求创建issue时，必须在Linear的Project“消防AI”下创建issue
3. 任何 pytest、CI，或需要验证默认配置不受仓库 `.env` 污染的进程，必须在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。这是 DeepEval 官方的 dotenv 加载开关，不是 warning suppression，也不替代独立的 telemetry 隐私配置。

## CODEMAP Navigation Protocol

This project uses hierarchical `CODEMAP.md` index files for code navigation. Files over 1000 lines may have companion `.analysis.md` structural maps.

### Navigation Rules

1. Start from root `CODEMAP.md`. Read Task Guide first.
2. Task Guide match: Target = primary read set. Also Check = conditional candidates (decide after reading Target).
3. No Task Guide match → filter Subdirectories by Domain, enter only matching-domain subdirectories.
4. Drill down layer by layer; consult local Task Guide at each level before reading source files.
5. Container directories (no source files): read only Task Guide + Subdirectories.
6. Large files: read `.analysis.md` Feature Index first, match Intent to line ranges. Use Logical Sections as fallback.
7. Batch-read final target files in parallel.
8. No speculative expansion: extend read set only when already-read code proves the need.

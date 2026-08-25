# AGENTS.md

## 当前目标：分析[执行流程](/Users/itboybob/Project/fire/新修订流程.md)和[原Todo](/Users/itboybob/Project/fire/To-do.md)的关系

### 背景
- [已有的Golden Set ](RAG_Golden_Set.md) 只包含正例输入，覆盖度不足；目前已经确定 Golden Set 将包含“正例”“Edge Case”“Adversarial Case”3个一级Bucket；“正例”Bucket的所有数据集已准备好；“Edge Case”Bucket的“二级Bucket”设计规范已确定；
- 知识库范围：
[1](法律文本/)和[2](新法规文件/)
- 现有Golden Set计划作为在受控状态下生成“Edge Case”和“Adversarial Case”的“生成种子”；边界说明：现有Golden Set无法涵盖消防法律领域的所有场景

### 已确定事实
- 行动思路：把路径 B 做 value discovery，同时把外部研究用于方法借鉴和遗漏检查
> 路径 B ：以现有正例 Golden Set 为配对生成种子，结合消防法规中的主体、义务、监管程序、行为对象和潜在滥用方式，在尽量保持法律知识需求与证据不变的前提下发现 B1…Bn。
>
> 外部研究使用边界：只用于借鉴分析方法、转换结构、术语和遗漏检查，不直接移植具体标签

 - [二级 Bucket B_i 设计规范.md (line 8)](/Users/itboybob/Project/fire/二级 Bucket B_i 设计规范.md:8) 规定每个最终 B_i 必须具备的定义字段与边界，[Adversarial Cases 二级Bucket Labels.md (line 6)](/Users/itboybob/Project/fire/Adversarial Cases 二级Bucket Labels.md:6) 提供生成、标注和检查 B_i 的辅助标签输入，二者不构成平级二级 Bucket
 - 从正例转换Adversarial Case的 Intent ：中性目的 → 恶意目的
 - Risk Type 与经过消防法律领域化的 Authorization 暂作为辅助标签
>query transformation mechanism 与 misuse scenario 共同定义 B_i 的转换逻辑和领域含义；Risk Type 记录可能造成的风险后果，Authorization 记录行为主体是否具备相应权限。后两者只对生成后的样本进行横向标注，不决定样本属于哪个 B_i，也不与前两者构造笛卡尔积


### 附录：“Edge Case”Bucket的“二级Bucket”
1. 模糊提问/信息不足型（Underspecified）：系统无法确定用户具体在问什么。通常需要用户补充信息
2. 要求模型从语料中的实体、产品、操作和参数出发，刻意删除回答所需的关键字段
3. 知识库外型（Out-of-Database）：问题本身足够清晰，但由于知识库未包含问题的答案而无法回答
4. 无意义型（Nonsensical）：提出的问题本身荒唐不符合常识
5. 错误预设型（False-presupposition）：问题本身包含错误前提
6. 模态受限型（Modality-limited）

------
## 强制规则

1. 所有包安装必须在 conda 环境 `fire` 中执行。所有代码执行必须在 conda 环境 `fire` 中执行。推荐使用 `conda run -n fire ...` 显式执行，避免误用 `base` 或系统 Python。
2. 必须在Linear的Project“消防AI”下创建issue
3. 任何 pytest、CI，或需要验证默认配置不受仓库 `.env` 污染的进程，必须在 import DeepEval 前设置 `DEEPEVAL_DISABLE_DOTENV=1`。这是 DeepEval 官方的 dotenv 加载开关，不是 warning suppression，也不替代独立的 telemetry 隐私配置。


## 文档系统

- 新会话先读取 `docs/system_meta/文档索引.md`，再读取 `docs/system_meta/文档读取规则.md`，随后只按任务需要扩展上下文。
- 默认最小读取集合是本文件、文档索引和文档读取规则；`README.md`、PRD、工程技术标准、专项设计和实施计划均按任务触发。
- 任务涉及法规摄取的架构设计、实施计划、代码实现、能力状态或里程碑进度时，必须先读取 `docs/project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md`，再按其中的当前能力、依赖和里程碑范围读取对应设计或计划。
- 法规摄取的架构或 ADR、策略能力状态、里程碑创建/范围/状态、依赖审批或阻塞、真实验收结果发生变化时，必须在同一任务中同步更新能力路线图；不得仅因计划完成就把能力标记为已实现。
- 不得默认扫描整个 `docs/`，不得把历史设计、历史计划、生成物或原始法规全文当作当前运行事实。
- 文档角色、读取时机和权威级别以 `docs/system_meta/文档索引.md` 为准；任务映射和冲突优先级以 `docs/system_meta/文档读取规则.md` 为准。
- 新增、移动、重命名或删除文档时，必须同步索引、读取规则和所有入口引用

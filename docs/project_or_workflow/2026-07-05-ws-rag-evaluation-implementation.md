# Word/W 单文件 RAG 问答评测实施计划

> 本计划用于在当前工作区直接按批次执行。

**目标：** 为已导入的 W-S1/W-S2 法规建立可复现的单文件 RAG 问答评测链路，分离问题集生成与评测执行，产出可校准、可比较、可原子发布的版本化 JSON 报告。

**架构：** 评测代码只新增到 `scripts/eval_ws_rag/` 及两个薄 CLI，不改动 `app/` 核心服务。问题集先独立生成并以 `dataset_id`、`dataset_fingerprint` 固化；评测执行复用真实 `Retriever.search()` 与 `build_answer()`，再由规则校验和独立 Judge 打分。报告先在 run 级暂存目录完成双文件校验，再以目录重命名一次性发布。

**技术栈：** Python 3.14、现有 OpenAI Python SDK、Pydantic、SQLite/FAISS、pytest；所有代码和测试均通过 conda 环境 `fire` 执行。

---

## 1. 计划地位与权威依据

本文是“建立并完成 Word 文档评测系统”里程碑的主实施入口，角色为 `project_or_workflow`。冲突时依次服从：

1. 根目录 `AGENTS.md`；
2. [工程技术标准](../architecture_or_strategy/工程技术标准.md)；
3. [Word/W 阶段单文件 RAG 问答评测设计](../architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md)；
4. [法规摄取能力路线图](./2026-06-29-legal-ingestion-capability-roadmap.md)；
5. 本总览及当前分卷。

Dashboard 是下游只读消费者，其设计和实现均由独立文档负责：

- [Dashboard 专项设计](../architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-design.md)
- [Dashboard 独立实施计划](./2026-07-05-ws-rag-evaluation-dashboard-implementation.md)

主评测计划只负责稳定报告契约和原子发布边界，不复制 Streamlit 页面、加载器或浏览器验收步骤。

## 2. 里程碑范围

### 2.1 纳入范围

- 从单份已导入 W-S1/W-S2 文档 chunks 生成高频、边界拒答和结构多样性问题；
- 将问题集作为不可变 dataset 持久化，记录来源摘要、生成配置与指纹；
- 使用真实检索器和真实回答服务执行每个问题；
- 通过本地规则检查引文、文档边界、拒答和 JSON 字段；
- 使用与答案生成模型解耦的 Judge 评估上下文相关性、忠实度和答案相关性；
- 聚合问题级、文件级和 run 级指标；
- 生成共享 `report_models.py`，作为主评测写入器与 Dashboard 读取器的唯一 Python schema；
- 以 run 目录为单位暂存、自校验和原子发布 `report.json`、`errors.json`；
- 完成人工校准、不可变基线登记、同 dataset 两轮比较；
- 用 W-S1、W-S2 各至少一份真实文件完成端到端验收。

### 2.2 不纳入范围

- PDF、扫描件、S4、跨法规联合推理或法规版本冲突裁决；
- 修改 `app/services/retriever.py`、`answer_service.py` 或在线 API 行为；
- 用 mock 检索替代最终真实验收；
- 把 Dashboard 作为评测执行入口，或让 Dashboard 修改阈值、问题集和报告；
- 自动发布到远端、云部署、多用户权限或定时评测；
- 仅凭 LLM 分数自动作出法律专家结论。

## 3. 已确认输入、缺失输入与默认值

### 已确认

- W-S1、W-S2 摄取及正式索引已经完成，可提供真实 `data/chunks/` 和 `data/index/`；
- 当前 `Retriever.search()` 在全局索引上返回原始 top-k，评测不得暗中改写其排序；
- `build_answer()` 已执行结构校验和候选引文约束；
- `OpenAIChatClient` 的响应 schema 固定为在线答案 `ModelAnswer`，不能直接承担 Judge 自定义 schema；
- Dashboard 只消费正式 run 目录中的版本化报告。

### 阶段开始前仍需检查

- `fire` 环境、真实索引和目标文档 chunks 是否存在；
- 生成模型、问题生成模型、Judge 模型、API 地址和密钥是否已由用户提供；
- Judge 与答案生成模型是否不同；相同时必须记录偏差风险并经用户确认；
- 首次正式校准的人工评审者及 50～100 条样本是否可用；
- 拟设为 baseline 的 run 是否已经通过真实验收。

缺少模型凭据时仍可完成纯本地单元与 fake-client 集成测试，但不得声称真实 Judge、校准、基线和里程碑验收已经完成。

### 默认值

- `top_k=5`；
- 阈值：上下文相关性 `0.8`、来源覆盖率 `0.9`、忠实度 `0.9`、答案相关性 `0.8`、引文有效性 `1.0`、拒答适当性 `0.9`；
- 每个文档至少覆盖高频、不可回答边界、开头/中部/尾部结构切片；
- Judge 证据顺序使用 run seed 可复现打乱，默认重复 3 次后取平均；
- dataset 落在 `data/eval/ws_rag_datasets/<dataset_id>/dataset.json`；
- 正式 run 落在 `reports/ws_rag_eval/<run_id>/`；
- 失败调试信息落在 `var/ws_rag_eval/<run_id>/debug.json`，不让 Dashboard 把失败目录误认作正式报告。

## 4. 依赖与包管理工具

| 环境 | 包管理工具 | 本里程碑结论 |
| --- | --- | --- |
| 后端 Python | conda 环境 `fire`；依赖声明以 `pyproject.toml` 为准，只能用 `conda run -n fire python -m pip` 安装 | 无需新增依赖；复用 `openai`、Pydantic、FAISS 和 pytest |
| 前端 | 不涉及 | 不使用 npm、pnpm 或 yarn |
| Dashboard | conda 环境 `fire`；由独立计划管理 Streamlit | 本计划不安装、不实现 |
| 其他运行环境 | 标准库文件系统与 Git 只读命令 | 无需安装 |

任何 Task 若发现必须新增依赖，立即停止，列出名称、版本、用途、安装位置、包管理工具、许可证和替代方案，待用户确认后再继续。

## 5. 分卷导航

- [分卷一：共享契约、不可变问题集与问题生成](./2026-07-05-ws-rag-evaluation-implementation-part-1.md)
- [分卷二：真实 RAG、Judge、规则校验与原子报告](./2026-07-05-ws-rag-evaluation-implementation-part-2.md)
- [分卷三：编排、校准、基线比较与真实验收](./2026-07-05-ws-rag-evaluation-implementation-part-3.md)

默认读取顺序：本总览 → 当前分卷 → 当前 Task 指定的设计、代码和测试。执行 Dashboard 时改读其独立计划，不继续读取本计划分卷。

## 6. Phase 与 Task 顺序

| Phase | Task | 交付物 | 依赖结论 |
| --- | --- | --- | --- |
| Phase 1 契约冻结 | 1—2 | 共享报告模型、配置、dataset 模型与指纹 | 无需新增依赖 |
| Phase 2 问题集 | 3—4 | 文档加载、独立问题集生成 CLI、问题集质量门禁 | 无需新增依赖 |
| Phase 3 真实执行 | 5—6 | RAG Runner、独立结构化 Judge 客户端与评分协议 | 无需新增依赖 |
| Phase 4 评判发布 | 7—9 | 规则校验、聚合器、run 目录级原子发布 | 无需新增依赖 |
| Phase 5 编排运营 | 10—12 | 主 CLI、人工校准、同 dataset 基线比较 | 无需新增依赖 |
| Phase 6 真实验收 | 13 | W-S1/W-S2 真实报告、回归证据、文档收口 | 无需新增依赖 |

不得跳过 dataset 固化直接生成临时问题并称为可比较评测；不得在共享 schema 和原子发布尚未通过测试时启动 Dashboard 真实报告验收。

## 7. 全局硬门禁

1. 所有 Python、pytest 和脚本命令必须使用 `conda run -n fire ...`。
2. 每个 Task 先列已确认输入、缺失输入和默认值，再开始修改。
3. 每个 Task 都执行“失败测试 → 确认预期失败 → 最小实现 → 通过测试 → 真实上游产物验证”。
4. 问题生成与评测执行必须是两个独立 CLI/阶段；正式 run 必须引用已落盘 dataset。
5. `dataset_fingerprint` 必须由规范化 dataset 内容计算，不包含易变时间戳；相同内容必须得到相同指纹。
6. baseline/current 只有在 schema 主版本、`dataset_id`、`dataset_fingerprint`、`protocol_fingerprint` 及文档/问题 ID 全部一致时才能计算方向性变化；不一致时只允许并排查看原始值。
7. `report_models.py` 是写入器与 Dashboard loader 的共享 schema；禁止复制第二份同名字段 Pydantic 模型。
8. dataset 中的 `answer_sketch`、期望条文和期望行为不得传给 RAG 答案生成模型；Judge 也不得看到 `answer_sketch`，避免答案泄漏。
9. 真实 RAG Runner 不得 mock、重排或静默过滤 `Retriever.search()` 原始 top-k；跨文档证据由评测规则显式记录。
10. Judge 客户端与在线 `OpenAIChatClient` 分离，复用 SDK 和 `complete()` 形态，但不得复用其固定 `ModelAnswer` schema。
11. 报告必须使用 `dataset`、`protocol`、`system` 三个嵌套对象，并记录 `protocol_fingerprint`、Judge 精确模型和 prompt 版本、重复次数、证据顺序策略、阈值、生成模型和 prompt 版本、Git 状态、语料指纹及 `top_k`。
12. Judge 调用失败或不可解析属于 run 级致命错误：停止发布正式 run，写入 `var/` 调试记录并返回退出码 `1`。
13. 单问题格式异常可以记录后继续；检索索引缺失、融合异常、报告 schema 失败必须停止。
14. `report.json` 不包含 `errors` 数组；`errors.json` 即使为空也必须存在。
15. `report.json` 与 `errors.json` 先写入同一暂存目录；两者都通过 schema 和跨字段一致性校验后，只用一次目录重命名发布。
16. 正式 `run_id` 已存在时必须失败，禁止覆盖。
17. 真实验收必须使用已导入 W-S1、W-S2 文件和真实索引；不得 skip/xfail。
18. 报告及 dataset 不得记录 API Key、完整系统提示词或不必要的个人信息。
19. Dashboard 只通过独立计划实施；本计划不得复制其 UI Task。

## 8. Git 策略

本计划授权实施阶段每完成一个 Task 并通过对应单元测试、相关回归和真实上游验证后，执行一次 `git add` 与中文 `git commit`。具体提交说明写在各分卷。

- 每次提交只能包含当前 Task 已验证的代码、测试、配置或文档；
- 提交前检查 `git diff --cached`，避开用户和其他代理已有改动；
- 无法安全拆分时停止提交并报告；
- 本计划不授权 `git push`、`git merge`、`git rebase`、`git reset`、`git checkout --` 或其他历史改写；
- 当前“编写计划”任务的提交由主线程统一执行，本子任务不提交。

## 9. 里程碑完成定义

只有以下条件全部有当前证据时，能力才能从 `planned` 更新为 `implemented`：

1. Task 1—13 的 checkpoint 全部完成；
2. 问题集可以独立复用，报告记录 dataset 双标识；
3. 共享 schema 同时约束主评测和 Dashboard loader；
4. 规则、Judge、聚合和错误处理测试全部通过；
5. run 目录级原子发布及覆盖保护测试通过；
6. 人工正式校准达到 50～100 条，并记录一致率、争议项和最终阈值；
7. W-S1、W-S2 各至少一份真实文件完成无 skip 端到端评测；
8. 基线由不可变 run 登记，且同 dataset 比较门禁通过；
9. 仓库完整回归通过，文档状态与代码和报告证据一致；
10. Dashboard 是否完成单独按其实施计划判断，不阻塞主评测能力本身。

## 10. 总体验收命令

**命令执行意图：** 验证主计划总览和三个分卷均未达到 420 行警戒线。

```bash
wc -l docs/project_or_workflow/2026-07-05-ws-rag-evaluation-implementation*.md
```

**预期输出：** 四份文件各自少于 420 行，且没有任何文件超过 500 行。

**命令执行意图：** 执行主评测系统的全部自动化测试。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag -q
```

**预期输出：** 全部 PASS，无新增 skip、xfail 或未解释 warning。

**命令执行意图：** 在里程碑关闭前运行仓库完整回归。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS；任何新增失败均需修复，不能登记为历史例外。

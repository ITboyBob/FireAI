# 项目状态

本文档是本仓库唯一的执行状态文档，但按需更新，不承担逐任务流水账职责。只有出现重要里程碑、阻塞点变化、用户明确要求、长期任务交接、需要保存验证结果或会影响后续上下文时，才需要更新；纯文档小改、只读分析、无状态影响的简单任务不需要自动写入。

## 当前摘要

- 已按用户要求将 `docs/status.md` 更新规则调整为按需更新：状态文档仍是唯一项目状态源，但不再要求每次任务结束或每次代码执行后自动写入。
- 已按 `requesting-code-review` + TDD 完成 QA System 2.0 `Task 7-10` 的现状审查与缺陷修复，并补齐审查过程中暴露出的仓库层一致性问题；当前已修复“范围延伸追问丢失上一轮法规标题”“当前历史摘要未写回详情 API”“追问拒答误报修正提示”“软删除后仍可写 `answer_snapshots`”“`turns` 可引用其他会话消息”5 个真实缺陷，并在 `fire` 环境完成定向回归、全量测试与真实 `data/chunks/` 烟雾验证。
- 已按用户要求更新 `AGENTS.md` 的 Git 规则：当前仓库允许代理在当前任务范围内自主提交经过验证的本次改动，并可在提交后再同步提交范围、验证结果和提交说明，但 `push / merge / reset` 等高风险操作仍需用户单独要求。
- 2.0 产品基线、当前技术标准和实施计划已同步到“后端 NDJSON 状态流，最终可信结果由前端逐字呈现”的新设计边界；新增设计文档为 [2026-04-23-fire-qa-ndjson-status-stream-design.md](/Users/itboybob/Project/fire/docs/plans/2026-04-23-fire-qa-ndjson-status-stream-design.md)，当前尚未进入代码实现。
- 已开始按 `docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md` 执行消防问答系统 2.0 计划，并已在本地执行分支 `qa-system-2.0-exec` 开工，避免直接在 `main` 上实施。
- `Task 1` 已按 TDD 完成会话配置扩展：当前 `Settings` 已提供本机 `SQLite` 会话库路径、上下文窗口轮数和摘要触发阈值，`.env.example` 也已补齐对应占位项。
- `Task 2` 已按 TDD 建立 `SQLite` 会话仓库：当前已能持久化会话、消息、轮次和回答快照，并在 `var/task2-smoke.db` 上通过真实落库/重开验证。
- `Task 3` 已按 TDD 落地会话服务层：当前新会话默认标题、首条用户消息自动标题、按最近消息排序、重命名、软删除和删除后禁写规则都已落到服务层，并在 `var/task3-smoke.db` 上完成真实验证。
- `Task 4` 已按 TDD 落地追问判定与上下文窗口管理：当前系统已能识别基础指代追问，并把上下文裁剪为“最近 N 轮 + 可选历史摘要”，且已用真实 `data/chunks/xiaofangfa_2019.jsonl` 做过一次继承标题/条号验证。
- `Task 5` 已按 TDD 落地确定性历史摘要和知识库版本解析：当前更早轮次可被压缩成稳定摘要文本，每轮也能附带基于真实 `data/index/` 产物生成的知识库版本串。
- `Task 6` 已按 TDD 固定 2.0 对话展示契约：当前“回答 + 法律依据 + 条款原文 + 修正提示”的 schema 与 presenter 已落地，且已用真实 `data/chunks/` 验证“依据未变复用旧条文、依据变化切换新条文并提示修正”。
- `Task 7` 已按 TDD 串起会话主链：当前“用户消息 -> 追问判定 -> 上下文裁剪/摘要 -> 查询改写 -> 重检索 -> 回答生成 -> 展示整理 -> 消息/轮次/快照落库”已存在，并已在真实 `data/index/` 上完成两轮对话烟雾验证。
- `Task 8` 已按 TDD 暴露正式会话 API：当前 `/api/conversations` 已支持创建、列出、详情、重命名、删除与发消息，并已通过真实 `TestClient + data/index/` 烟雾验证。
- `Task 9` 已按 TDD 切换到双栏会话界面：当前根页面已改为“会话列表 + 当前线程 + 输入区”结构，前端主链改走 `/api/conversations/*`，并已通过真实 `uvicorn + curl` 壳验证。
- `Task 10` 已完成并通过真实多轮验收：当前 README / 文档索引 / 状态文档已对齐 2.0 实现，自动化测试、真实建库验证和真实多轮会话验收均已通过。
- 流式状态专项已完成文档设计与实施计划补充：后续应新增 `POST /api/conversations/{conversation_id}/messages/stream`，响应 `application/x-ndjson; charset=utf-8`，事件固定为 `received/retrieving/generating/organizing_evidence/completed/error`；一次性 `/messages` 接口保留兼容。当前无代码实现、无测试结果。
- QA System 2.0 `Task 7-10` 的本轮专项代码审查已收敛完成；当前仓库内已无新的代码级阻塞，剩余风险重新回到外部聊天提供商的可用性与限流策略。
- 在用户提供新的 iFlow `CHAT_API_KEY` 后，已继续修复 4 个真实链路问题：Markdown 代码块包裹 JSON 导致 schema 校验失败、限流错误未重试、证据区混入无关条文原文、范围延伸追问未触发修正提示。
- 当前主线已无新的代码阻塞；剩余风险主要是外部聊天提供商的可用性和限流策略，属于运行时依赖而非仓库内逻辑缺陷。
- 新开聊天窗口时的文档读取顺序已在 `AGENTS.md` 中固化，`docs/文档索引.md` 用于解释这套顺序。
- `Task 1` 的代码骨架已经落地，包括基础配置、`/health` 接口和最小测试。
- 仓库元数据和实施计划已对齐到 Python `3.14` 基线，`fire` 环境已完成 editable install。
- `Task 1` 已在要求的 `fire` conda 环境完成合规验证。
- `Task 2` 已按 TDD 落地语料发现与输入清单，并通过回归测试。
- 已将 `task2-manifest-py314` worktree 中的已验证改动折回当前 `main` 工作树。
- `Task 3` 已按 TDD 完成文档标准化实现，并在 `fire` 环境通过服务层回归测试。
- 已基于 `法律文本/` 真实语料生成 `data/normalized/*.txt`，当前 6 份原始法规均标准化成功。
- `Task 3` 的 Unicode 行终止符缺陷已修复，全部标准化产物已重新生成。
- 当前 3 份 `.doc` 与 3 份 `.docx` 输入均已再次验证通过，产物中确认不存在 `U+2028/U+2029/\r` 残留。
- 已定位 `xiaofangfa_2019` 中 `HYPERLINK` 残留的根因：问题不在切块，而在 `.doc` 经 `textutil` 导出后的标准化阶段；当前 `clean_text()` 只会删除整行 `HYPERLINK` 噪声，无法清理条文内嵌的 Word 超链接字段码。
- 已修正实施计划中 `Task 4` 将 `title` 与 `document_id` 混用的缺陷，并补上“修订决定前言 + 真正法规标题”的验收要求。
- `Task 4` 已完成结构解析实现，`data/structured/*.json` 已在真实语料上生成。
- 当前 6 份标准化文本均已解析为结构化 JSON，其中“历史修改说明污染 `title` / 首条 / 正文”的主风险已通过最新前后对照审计。
- 已针对“历史修改说明污染 `title` / `promulgated_on` / 第一条正文”的真实边界补做回归，当前关键样本已纠正。
- 最新 `Task 4` 终审中，`jiguan_tuanti_qiye_shiye_danwei_xiaofang_anquan_guanli_guiding` 的带空格日期提取也已修复。
- `Task 5` 已完成最小实现并通过单测，当前切块逻辑已覆盖路径保留、按段拆分、无章节标题路径构造和 JSONL 落盘。
- `Task 5` 的服务层回归已通过，当前 `Task 2` 到 `Task 5` 的离线链路在测试层保持一致。
- 已基于 6 份真实 `data/structured/*.json` 生成 `data/chunks/*.jsonl`，切块数量与拆分情况已完成抽样核对。
- `Task 5` 已完成 `code-reviewer` 审查，当前无新的实质性缺陷发现。
- 已完成“段内二级切块”需求审计：当前生成 chunk 中仅 `xiaofangfa_2019` 有 `2` 个超出 `300` 字阈值的块，但多份法规的真实条文都存在 `（一）（二）` 枚举结构，因此不能只对单一文件做特判。
- 已新增重构设计文档、实施计划与 ADR，当前 `Task 6` 已被正式门禁拦截，必须先完成这次 `normalizer/chunk_builder` 重构与全量重建。
- 新增的重构设计文档、实施计划与 ADR 已统一改成中文，避免文档系统中英混杂。
- 标准化与切块重构 `Task 1` 已补齐真实夹具，并完成两次红测确认；当前失败稳定收敛到“真实行内超链接清洗”和“第六十二条枚举级 chunk 回归”两项新增行为。
- 标准化与切块重构 `Task 2` 已完成 `normalizer` 修复、单测回归和 `xiaofangfa_2019` 哨兵重建；当前 `data/normalized/` 目录已显式确认不再残留 `HYPERLINK/http(s):///\l "#"` 字段码痕迹。
- 标准化与切块重构 `Task 3` 已完成结构化哨兵测试、`structure_parser` 回归、`xiaofangfa_2019` 结构化重建与摘要对比；当前 `data/structured/xiaofangfa_2019.json` 已显式确认不再残留超链接字段码，且标题、首末条、日期、条文数量保持稳定。
- 标准化与切块重构 `Task 4` 启动审计后发现计划矛盾：当前真实夹具 [xiaofangfa_article_62_structured.json](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_structured.json) 在完成任务 2 清洗后，正文总长度仅 `165`，分段长度为 `[33, 44, 32, 9, 18, 24]`，已不满足“按段切块后仍超过 `300` 才触发二级切块”的设计前提。
- 已检索 [status.md](/Users/itboybob/Project/fire/docs/status.md) 全文，当前未发现用户曾在状态文档中明确批准“只有按段切块后某段仍超过 `300` 且包含枚举标记才触发二级切块”；该触发条件来自已批准的设计文档与实施计划，而不是状态记录里的用户确认语句。
- 用户已于 `2026-03-29` 明确改选“修正真实哨兵样本，不修改 Task 4 触发规则”，并要求在 ADR 中补记本次决策，同时保留对“引用粒度可能仍偏粗”的风险说明。
- `@architect` 已完成专题分析：当前文档系统对“执行状态”有统一入口，但没有把“规则级批准”设计成可审计对象，因此能找到“设计文档已批准”，却无法稳定回溯“某条细则是否被用户逐条批准”的证据链。
- 在 `fire` 环境重新扫描 `法律文本/*`、`data/normalized/*.txt` 与 `data/structured/*.json` 后，当前 6 份真实语料中未找到任何“单行/单段长度超过 `300` 且包含 `（一）（二）` 枚举标记”的样本；这意味着用户改选的“方向一：修正真实哨兵样本，保持原触发规则不变”在当前语料范围内已无法直接落地。
- 已按用户最新要求，由 `@Curie` 在重构设计文档与实施计划的 `chunk_builder / 段内二级切块` 位置补充“单段/单行超过 `300` 且带枚举标记时应优先识别”的执行提示；本次只增加提示，不修改既有触发规则，也不继续扩展文档系统。
- 已复核原实施计划的 `Task 5`，结论是当前**不能直接执行原 Task 5**：该任务的测试通过、哨兵重建与变化归因都以前置 `Task 4` 已完成为前提，而当前 `Task 4` 的真实样本阻塞仍未解除。
- 已按用户要求复核 `data/chunks/` 下的超链接污染范围，确认当前污染只命中 [xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl)；随后已基于新的 [xiaofangfa_2019.json](/Users/itboybob/Project/fire/data/structured/xiaofangfa_2019.json) 按现有旧分块逻辑重建该文件，当前 `data/chunks/` 目录已显式确认不再残留 `HYPERLINK/http(s):///\l "#"`。
- 用户已于 `2026-03-29` 明确决定暂时搁置标准化与切块重构计划，回到原主线实施计划；基于当前 `data/normalized`、`data/structured`、`data/chunks` 已无超链接污染、`data/chunks/*.jsonl` 无空字段/重复 `chunk_id`/超长块，原主线 `Task 6` 已恢复执行。
- 原主线 `Task 6` 已按 TDD 完成：新增 [keyword_index.py](/Users/itboybob/Project/fire/app/services/keyword_index.py)、[test_keyword_index.py](/Users/itboybob/Project/fire/tests/unit/services/test_keyword_index.py) 与 [build_corpus.py](/Users/itboybob/Project/fire/scripts/build_corpus.py)，并在 `fire` 环境通过单测、真实索引烟雾验证和 `build_corpus.py` 入口验证。
- 已按用户要求更新 [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md)，新增仓库级测试规则：以后凡是新增或修改测试，除了运行对应单元/预编写测试，还必须基于真实上游产物再做一轮真实验证。
- 已按用户要求审查原主线实施计划中的依赖安装说明，并补齐“执行过程中自动安装依赖”的仓库级规则；当前计划已明确：`Task 7` 在接入真实向量检索前需要额外安装依赖，`Task 9` 和 `Task 11` 也已补上依赖边界说明。
- 依赖安装规则已按用户最新要求再次收紧：当前仓库级口径不再是“发现缺依赖就直接安装”，而是“先向用户显式报备待安装依赖清单并请求确认，再在 `fire` 环境安装”；同时，已新增“撰写任何执行计划时，必须显式说明本 Phase / Task 是否需要安装依赖，并注明安装环境”的规则。
- 原主线 `Task 7` 已按 TDD 完成本地嵌入器、向量存储接口、向量索引构建器和 `scripts/build_index.py`；当前索引目录约定已显式收束到 `data/index/`，并新增 `vector_map.json` / `faiss.index` 产物边界。
- 已在 `fire` 环境基于真实 `data/chunks/*.jsonl` 共 `328` 条 chunk 做过一次“假嵌入器 + 临时向量存储”真实上游验证，确认 `scripts/build_index.py` 的离线链路能同时产出 `retrieval.db`、`vector_map.json` 与占位 `faiss.index`。
- 用户已于 `2026-03-29` 明确批准在 `fire` 环境安装 `numpy`、`faiss-cpu`、`sentence-transformers`；当前三项依赖及其传递依赖已安装完成，并通过导入验证，版本分别为 `numpy 2.4.3`、`faiss-cpu 1.13.2`、`sentence-transformers 5.3.0`、`torch 2.11.0`。
- 已使用真实嵌入模型 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 在 `fire` 环境成功执行 `scripts/build_index.py`；当前 `data/index/` 已生成真实 `retrieval.db`、`faiss.index`、`vector_map.json`，且关键词回查 `消防设施` 仍命中 `hebei_xiaofang_tiaoli#article-27`。
- 原主线 `Task 8` 已按 TDD 完成查询规范化与混合检索：新增 [query_normalizer.py](/Users/itboybob/Project/fire/app/services/query_normalizer.py)、[retriever.py](/Users/itboybob/Project/fire/app/services/retriever.py)、[test_query_normalizer.py](/Users/itboybob/Project/fire/tests/unit/services/test_query_normalizer.py) 与 [test_retriever.py](/Users/itboybob/Project/fire/tests/unit/services/test_retriever.py)，并在 `fire` 环境通过单测、受影响回归和真实索引检索验证。
- 原主线 `Task 9` 已按 TDD 完成答案组装与 OpenAI 兼容聊天客户端：新增 [chat.py](/Users/itboybob/Project/fire/app/schemas/chat.py)、[chat_client.py](/Users/itboybob/Project/fire/app/services/chat_client.py)、[answer_service.py](/Users/itboybob/Project/fire/app/services/answer_service.py) 与 [test_answer_service.py](/Users/itboybob/Project/fire/tests/unit/services/test_answer_service.py)，并补齐 `CHAT_*` 配置默认值与 [.env.example](/Users/itboybob/Project/fire/.env.example) 占位项。
- 已在 `fire` 环境确认 `openai 2.30.0` 已可直接导入，无需为 `Task 9` 新增依赖；当前答案层采用 `json_schema + Pydantic` 结构化输出，并在本地二次校验“引文必须来自当前证据集”，避免把格式正确但无依据的模型回答误当成可放行结果。
- 原主线 `Task 10` 已按 TDD 完成聊天 API 暴露：新增 [chat.py](/Users/itboybob/Project/fire/app/api/chat.py)、[test_chat_api.py](/Users/itboybob/Project/fire/tests/integration/api/test_chat_api.py) 与 [test_chat_dependencies.py](/Users/itboybob/Project/fire/tests/unit/api/test_chat_dependencies.py)，将 `/api/chat` 接入真实“查询规范化 -> 检索 -> 答案生成”链路，并把“尚未完成建库 / 模型调用失败 / 证据不足”拆成可区分的响应路径。
- 已修正 `Settings` 对空 `EMBEDDING_MAX_SEQ_LENGTH` 的解析，并把默认值测试改成显式隔离本机 `.env`，避免本机配置污染仓库基线测试。
- 已定位并修复当前 `fire` 环境下的一个原生稳定性问题：若先加载真实 `FAISS` 索引，再首次触发 `sentence-transformers` 编码，会在查询阶段触发段错误；当前 [chat.py](/Users/itboybob/Project/fire/app/api/chat.py) 已通过“先预热 embedder、后加载 FAISS”规避该问题，并完成真实 `data/index/` 冒烟验证。
- 已按用户确认执行一次配置安全修正：当前 [settings.py](/Users/itboybob/Project/fire/app/core/settings.py) 与 [.env.example](/Users/itboybob/Project/fire/.env.example) 已移除真实 `API Key`，仅在示例文件保留所选提供商 `iFlow` 与模型 `qwen3-32b`；真实密钥后续只应存放在本机未纳入版本控制的 `.env`。
- 已按用户要求调用 `@code-reviewer` 复核 `test_build_chunks_matches_real_structured_fixture` 的失败根因；结论是当前主问题位于“旧真实夹具/测试断言仍要求未超限枚举条文拆分”，而不是 `Task 7` 新实现或 `structured` 上游再次退化。
- 已新增 [技术债记录](/Users/itboybob/Project/fire/docs/debts/2026-03-29-chunk-builder-enum-red-test-debt.md)，并将 `tests/unit/services/test_chunk_builder.py::test_build_chunks_matches_real_structured_fixture` 显式标记为 `xfail`；当前主线放行不再被这条已知技术债阻塞，但技术债本身仍需后续单独清偿。
- 在 `fire` 环境重新执行 `conda run -n fire python -m pytest -q` 后，当前结果为 `30 passed, 1 xfailed in 0.37s`；其中唯一 `xfailed` 项即上述技术债测试。
- 原主线 `Task 7` 当前已完成真实依赖安装与环境合规验证；若继续主线，下一步应进入 `Task 8`，而不是继续停留在向量依赖准备阶段。
- 当前主线 `Task 11` 已完成，原实施计划中的 `Task 1` 到 `Task 11` 均已落地；当前无新的主线技术阻塞，剩余主要是已登记的枚举级切块技术债与后续真实聊天提供商联调风险。
- 原主线 `Task 11` 已启动 TDD 红测：当前已新增根页面渲染断言与小型离线流水线集成测试，但模板、静态资源和根路由尚未实现。
- `Task 11` 首轮红测已经暴露出一个真实计划缺口：现有 `tests/fixtures/raw/*` 更适合作为“原始文件发现夹具”，并不能稳定支撑“从原始文档一路产出 chunk 和 index”的小型离线流水线集成测试；当前已在任务 11 的集成测试中改为运行时生成最小 `.docx` 法规样本，并复跑确认失败面已收敛到根页面 `404`。
- 原主线 `Task 11` 的目标测试现已转绿：`/` 根页面会渲染模板并引用 `/static/app.css`、`/static/app.js`，小型离线流水线集成测试也已能稳定产出 `data/normalized`、`data/structured`、`data/chunks` 与 `data/index`。
- 全量测试已在 `fire` 环境重新通过，当前结果为 `49 passed, 1 xfailed in 0.53s`；唯一 `xfailed` 项仍是已登记的 `chunk_builder` 枚举级技术债，与任务 11 无直接耦合。
- 原主线 `Task 11` 已完成：当前 [README.md](/Users/itboybob/Project/fire/README.md) 已补齐安装、建库、运行、测试与已知限制说明，真实 `build_corpus.py` / `build_index.py` 与根页面 `/`、静态资源 `/static/*`、健康检查 `/health` 也已在 `fire` 环境完成合规验证。
- `Task 11` 完成后的运行就绪度复核已启动：当前 `fastapi`、`jinja2`、`openai`、`uvicorn`、`httpx`、`pytest`、`numpy`、`faiss`、`sentence-transformers` 均可在 `fire` 环境导入，`.env` 中的真实聊天配置和 `data/index/*` 索引文件也已就位；唯一缺失依赖是 `playwright`，因此“手工前端测试”已具备前提，但“浏览器自动化回归”仍未具备前提。
- 真实聊天前置检查已有结论：当前并非“依赖没装好”，而是“真实 `/api/chat` 请求能发出，但模型调用阶段返回 `502`”；因此前端网页已具备手工联调入口，但还不能宣称“真实聊天稳定可用”。

## 最新记录

### 2026-04-23 更新 NDJSON 状态流设计与文档基线

- 执行内容：按用户已确认的最终设计，新增 [NDJSON 状态流设计](/Users/itboybob/Project/fire/docs/plans/2026-04-23-fire-qa-ndjson-status-stream-design.md)，并同步更新 [2.0 PRD](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md)、[2.0 实施计划](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)、[README](/Users/itboybob/Project/fire/README.md) 与 [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md)。统一口径为“后端 NDJSON 状态流，最终可信结果由前端逐字呈现”；明确这不是模型 token 原生流，不展示未校验草稿，不做 `SSE` / `WebSocket` / 未校验 `delta`，不持久化 `partial message/delta`，不新增 `delta` 表。
- 执行环境：本轮只修改文档，未运行 Python、pytest、服务进程或浏览器自动化；未联网、未安装依赖、未执行 git 操作。
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境。Playwright 按用户补充可尝试使用，但实施前必须先在 `fire` 环境确认可用；若不可用，只记录阻塞，不私自安装。
- 验证结果：本轮未运行测试。文档层已记录后续实现验收口径：服务层事件顺序与共享链路、`TestClient.stream` NDJSON、前端 buffer 解析/typewriter/错误态/重复提交、真实 `data/index/` 加 fake chat client 验证，以及可用时通过 Playwright `page.route` mock `/api/conversations*` 的 Chromium 关键路径 E2E。
- 当前阻塞点：设计文档与计划已更新，代码尚未实现；下一步应按实施计划的“流式状态专项阶段”进入 TDD，实现 `/api/conversations/{conversation_id}/messages/stream` 与前端 NDJSON 消费。

### 2026-04-22 修复火山方舟返回 JSON 字段类型偏差导致的聊天失败

- 执行内容：针对前端报错“模型调用失败：模型返回了无法通过 schema 校验的 JSON。”进行定位。已确认本轮不是火山方舟接口不可用，也不是 API Key / 模型 ID 错误，而是模型返回的 JSON 字段类型与本地 `ModelAnswer` schema 不一致：真实返回中 `citations` 是单个字符串，`uncertainty` 是数字 `0`，而本地要求分别为字符串数组和字符串。已在 [chat_client.py](/Users/itboybob/Project/fire/app/services/chat_client.py) 增加受控归一化：单个 `citations` 字符串会转为单元素数组，`uncertainty` 的空值/`0` 会转为空字符串；若归一化后仍无法校验，会输出截断后的 warning 日志帮助定位。已在 [answer_service.py](/Users/itboybob/Project/fire/app/services/answer_service.py) 强化提示词，明确要求 `citations` 为字符串数组、`uncertainty` 为字符串。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境；未执行包安装。
- 验证结果：
  - 真实故障复现：使用真实 `data/index/` 检索结果与火山方舟 `doubao-1-5-lite-32k-250115` 调用，原始返回为合法 JSON，但 `citations` / `uncertainty` 类型不符合本地 schema，复现了截图中的校验失败。
  - 定向回归：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py -q` 结果为 `11 passed in 0.24s`。
  - 受影响回归：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py tests/unit/services/test_conversation_turn_service.py tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q` 结果为 `29 passed in 0.46s`。
  - 真实上游验证：使用真实 `data/index/` 检索结果与当前火山方舟配置再次执行答案生成，已返回 `{'conclusion': '单位的主要负责人是本单位的消防安全责任人。', 'citations': ['《中华人民共和国消防法》第十六条'], 'uncertainty': ''}`。
- 当前阻塞点：本次修复已验证通过；但用户当前 8000 端口后端进程看起来不是 `--reload` 启动，需重启后端后浏览器聊天界面才会加载修复后的代码。

### 2026-04-22 切换聊天模型提供商为火山方舟

- 执行内容：按用户要求查询火山引擎官方文档后，将本机未纳入版本控制的 `.env` 切换为火山方舟 OpenAI 兼容配置；真实 `CHAT_API_KEY` 只写入本机 `.env`，未写入仓库示例文件。已同步更新 [.env.example](/Users/itboybob/Project/fire/.env.example)，将公开示例配置改为 `CHAT_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`、`CHAT_MODEL=doubao-1-5-lite-32k-250115`，并继续保留 `CHAT_API_KEY=replace-me`。
- 官方文档依据：火山方舟 [对话(Chat) API](https://www.volcengine.com/docs/82379/1494384) 给出的 Chat Completions 请求地址为 `https://ark.cn-beijing.volces.com/api/v3/chat/completions`；火山方舟 [文本生成](https://www.volcengine.com/docs/82379/1399009) 与在线推理文档给出的 OpenAI SDK `base_url` 为 `https://ark.cn-beijing.volces.com/api/v3`；火山方舟 [模型列表](https://www.volcengine.com/docs/82379/1330310) 中当前匹配 `Doubao-1.5-lite-32k` 的模型 ID 为 `doubao-1-5-lite-32k-250115`。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境；未执行包安装。
- 验证结果：
  - `conda run -n fire python -c "from app.core.settings import Settings; ..."` 已确认 `Settings()` 可读取 `CHAT_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`、`CHAT_MODEL=doubao-1-5-lite-32k-250115`，且 `CHAT_API_KEY` 已脱离占位值。
  - `conda run -n fire python -m pytest tests/unit/core/test_settings.py -q` 结果为 `3 passed in 0.04s`。
- 当前阻塞点：本轮只完成配置加载验证，未调用火山方舟真实模型接口以避免未经确认地产生外部调用费用。若下一步做真实问答验收，需要确认该 API Key 已在火山方舟开通 `doubao-1-5-lite-32k-250115` 或对应模型单元权限；若真实调用返回模型不支持 `json_schema` 结构化输出，还需要把当前聊天客户端的火山方舟分支改为 `response_format={"type":"text"}` 并继续使用本地 JSON 校验。

### 2026-04-22 调整 `docs/status.md` 为按需更新

- 执行内容：按用户新要求调整规则文档，将“每次任务结束或每次代码执行后自动更新 `docs/status.md`”改为“按需更新”。当前口径是：`docs/status.md` 仍是唯一项目状态源，但只有重要里程碑、阻塞点变化、用户明确要求、长期任务交接、需要保存验证结果或会影响后续上下文时才更新；纯文档小改、只读分析、无状态影响的简单任务不需要自动写入。
- 执行环境：本轮仅修改规则文档；未运行 Python、pytest 或服务进程。
- 依赖情况：无需新增依赖，未执行包安装。
- 当前阻塞点：当前无新的规则级阻塞；历史计划中仍保留少量具体任务要求记录状态或验证结果的条目，这些属于里程碑/交接型记录，不再代表“每次任务结束都必须更新”。

### 2026-04-22 对齐 PRD、README 与一期 RAG 设计的权威边界

- 执行内容：在主代理已完成 2.0 PRD 第一轮修订的基础上，继续调整文档体系。已将 [README.md](/Users/itboybob/Project/fire/README.md) 明确为当前技术标准入口，并补充离线/在线分离、建库产物一致性、证据约束、错误处理、测试与真实产物验证、前端工程组织等技术稳定约束；已将 [docs/文档索引.md](/Users/itboybob/Project/fire/docs/文档索引.md) 与 [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md) 的新会话读取规则同步为“产品读 PRD、技术读 README、一期 RAG 设计仅追溯历史”；已在 [一期 RAG 设计文档](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-design.md) 开头加入历史状态说明；同时小修 [2.0 PRD](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md) 中偏接口实现的“前后端职责边界”表述，使其回到产品交互职责。
- 执行环境：本轮为文档更新；未运行 Python、pytest 或服务进程。
- 依赖情况：无需新增依赖，沿用当前仓库环境；未执行包安装。
- 验证结果：已完成文本级交叉检查，当前文档权威关系为：2.0 PRD 是唯一产品标准，README 是当前技术标准入口，一期 RAG 设计是历史资料；旧设计与 PRD 冲突时产品口径以 PRD 为准，旧设计与 README 冲突时技术口径以 README 为准。
- 当前阻塞点：文档权威边界已对齐；若下一步继续实现新版前端或会话产品能力，仍应先把 [2.0 实施计划](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 同步到当前 PRD 与 README 的最新边界，再按 TDD 执行。

### 2026-04-12 诊断“后端已启动但首页仍显示旧视觉”问题

- 执行内容：针对“访问 <http://127.0.0.1:8000/> 仍显示旧页面”的反馈，直接检查正在运行的本地服务返回内容，而不是凭截图猜测。通过 `curl http://127.0.0.1:8000/` 确认根页面 HTML 已是新版前端壳，包含 `home-view`、`thread-view`、`shell-sidebar` 等新结构；随后通过 `curl -i http://127.0.0.1:8000/static/app.css` 确认服务端返回的也是新版 CSS，内容已是深色首页 / 浅色对话页的变量体系，而不是旧版米色网格主题。
- 执行环境：本地 shell；未修改应用代码或重启服务。
- 依赖情况：无需新增依赖，沿用当前本地运行中的后端服务。
- 验证结果：
  - HTML 侧：服务端已返回新版模板，不是旧 HTML
  - CSS 侧：服务端也已返回新版 `app.css`，HTTP `200`，`content-length=16716`
  - 诊断结论：用户截图中“新 HTML 结构 + 旧米色网格背景”这一组合只能说明浏览器正在使用**旧缓存的 CSS**，而不是后端仍在提供旧页面
- 当前阻塞点：仓库内模板与静态文件已经是新版；若浏览器继续显示旧视觉，需要清理浏览器缓存或在模板中引入静态资源版本戳来强制缓存失效。

### 2026-04-12 为前端静态资源补齐规范缓存失效方案

- 执行内容：针对“新版 HTML 已返回，但浏览器仍可能混用旧 CSS/JS 缓存”的问题，没有继续依赖用户手工强刷，而是按 TDD 在 [test_chat_api.py](/Users/itboybob/Project/fire/tests/integration/api/test_chat_api.py) 先把页面契约收紧为“根页面和会话页都必须返回 `Cache-Control: no-store`，且模板中引用的 `/static/app.css`、`/static/app.js` 必须带版本参数”。随后在 [app/main.py](/Users/itboybob/Project/fire/app/main.py) 新增基于静态文件内容哈希的版本 URL 构造函数，并将 [index.html](/Users/itboybob/Project/fire/app/templates/index.html) 改为消费后端注入的 `static_css_url / static_js_url`，同时为页面响应补上 `Cache-Control: no-store`。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境与 Python 标准库 `hashlib`。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q` 初次结果为 `2 failed, 5 passed in 0.50s`，失败点集中在根页面和会话页都还没有返回 `cache-control: no-store`
  - 定向绿测：完成后端版本戳与模板接线后，`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q` 结果为 `7 passed in 0.36s`
  - 全量回归：`conda run -n fire python -m pytest -q` 结果为 `87 passed, 1 xfailed in 0.80s`
  - 真实 HTTP 验证：启动 `conda run -n fire python -m uvicorn app.main:create_app --factory --port 8013` 后，`curl -i http://127.0.0.1:8013/` 已返回 `cache-control: no-store`，且根页面实际引用 `app.css?v=7ece6e89df0e`、`app.js?v=489980400e33`
  - 工程效果：后续只要 [app/static/app.css](/Users/itboybob/Project/fire/app/static/app.css) 或 [app/static/app.js](/Users/itboybob/Project/fire/app/static/app.js) 内容发生变化，页面引用 URL 中的 `?v=` 哈希就会随之变化，浏览器不会再把新 HTML 与旧静态资源混用
- 当前阻塞点：仓库内缓存失效方案已落地并通过回归；当前无新的代码级阻塞。

### 2026-04-12 补充 README 的后端启动命令说明

- 执行内容：按用户要求检查当前机器上是否已有后端进程运行，并补充 [README.md](/Users/itboybob/Project/fire/README.md) 的后端启动说明。通过 `ps -ef | rg 'uvicorn app\.main:create_app|python -m uvicorn app\.main:create_app'` 检查后，当前未发现正在运行的 FastAPI / `uvicorn` 后端进程；随后在 README 的“运行”章节把现有启动命令显式标注为“后端启动命令”，并补充了一个带 `--port 8000` 的显式端口示例，方便直接复制执行。
- 执行环境：命令检查未依赖 Python 运行时；文档修改未运行服务或测试。
- 依赖情况：无需新增依赖，沿用当前仓库环境。
- 验证结果：
  - 进程检查：未匹配到 `python -m uvicorn app.main:create_app --factory ...` 相关进程，说明**当前后端未启动**
  - 文档结果：README 已包含清晰的后端启动命令和显式端口示例
- 当前阻塞点：无新的代码阻塞；若要实际启动后端，直接执行 README 中的 `conda run -n fire python -m uvicorn app.main:create_app --factory --reload` 即可。

### 2026-04-12 盘点 `docs/plans/` 并分析可合并文档

- 执行内容：按仓库文档顺序先读取 [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md) 与 [状态文档](/Users/itboybob/Project/fire/docs/status.md)，随后盘点并审读 [2026-03-28-fire-law-rag-design.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-design.md)、[2026-03-28-fire-law-rag-implementation.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md)、[2026-03-28-normalization-and-chunking-refactor-design.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor-design.md)、[2026-03-28-normalization-and-chunking-refactor.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md)、[2026-04-11-fire-qa-system-2.0-prd.md](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md) 与 [2026-04-11-fire-qa-system-2.0-implementation.md](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)，并调用 `doc-updater` 子代理做一轮独立静态交叉审读。当前已确认：最适合合并的是“标准化与切块重构”的设计文档与实施计划；基础 RAG 设计/实施、2.0 PRD/实施计划都不应直接合并，真正的问题是阶段标识不够强，以及 2.0 实施计划已落后于 `2026-04-12` 修订版 PRD。
- 执行环境：未运行 Python、pytest 或服务进程；本轮仅使用本地 shell 读取文档与子代理静态审读。
- 依赖情况：无需新增依赖，沿用当前仓库环境。
- 验证结果：
  - 本地盘点：已确认 `docs/plans/` 当前共有 `6` 篇主文档，总计约 `2571` 行；其中 [2026-03-28-fire-law-rag-implementation.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md) 约 `820` 行、[2026-04-11-fire-qa-system-2.0-implementation.md](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 约 `901` 行，说明当前问题不是单篇太短，而是历史主线与当前主线并列堆放。
  - 结构交叉核对：本地阅读与 `doc-updater` 子代理结论一致，均认为 [2026-03-28-normalization-and-chunking-refactor-design.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor-design.md) 与 [2026-03-28-normalization-and-chunking-refactor.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md) 的重叠最高，具备合并为单篇“专项方案”文档的条件。
  - 规范审查：已识别两类文档债务需要后续处理，一是两份 `2026-03-28` 实施类文档仍保留过时的 Git 规则；二是 [2026-04-11-fire-qa-system-2.0-implementation.md](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 仍混用英文标题与章节名，不符合仓库中文文档约束。
- 当前阻塞点：分析已完成，当前没有新的技术阻塞；下一步取决于用户是否要我继续把这份结论落成“最小文档重组方案”或直接执行合并/归档/重写。

### 2026-04-12 按新首页与对话页模板重构前端页面

- 执行内容：开始按用户新增的 [首页代码.html](/Users/itboybob/Project/fire/首页代码.html) 与 [对话页面代码.html](/Users/itboybob/Project/fire/对话页面代码.html) 重构前端页面。先按 TDD 修改 [test_chat_api.py](/Users/itboybob/Project/fire/tests/integration/api/test_chat_api.py)，把页面契约收紧为“根页面必须同时具备首页态与对话态骨架”“`/conversations/{conversation_id}` 必须可返回同一前端壳并注入初始会话 id”“首页必须存在预设问题卡片和独立首页/对话页输入表单”，以避免继续在旧单壳上打补丁。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境与现有 `pytest/FastAPI` 依赖。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q` 结果为 `2 failed, 5 passed in 0.45s`
  - 失败点 1：根页面仍是旧的单壳，没有 `home-view` / `thread-view` 双页面骨架
  - 失败点 2：`/conversations/conv-123` 当前返回 `404`，说明前端页面路由尚未支持会话详情 URL
- 二次验证结果：
  - 定向回归：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q` 结果为 `11 passed in 0.40s`
  - 当前已确认：新增首页态 / 对话态骨架与 `/conversations/{id}` 页面入口没有打断现有会话 API 契约
  - 全量回归：`conda run -n fire python -m pytest -q` 结果为 `87 passed, 1 xfailed in 0.71s`
  - 真实 HTTP smoke：使用带假检索器 / 假聊天客户端的本地 `uvicorn` smoke server，验证 `GET /` 可返回 `home-view / thread-view / home-composer-form / Starter Cards`，`GET /conversations/conv-demo` 可注入 `data-initial-conversation-id=\"conv-demo\"`，并通过真实 `POST /api/conversations` + `POST /api/conversations/{id}/messages` 验证页面所依赖的会话 API 仍能创建会话并返回结构化回答
  - Playwright MCP：已按用户要求尝试 `browser_navigate` 做前端页面点击验证，但工具初始化即失败，错误为 `ENOENT: no such file or directory, mkdir '/.playwright-mcp'`；根因是当前运行环境的根目录只读，不是项目代码错误
- 当前阻塞点：仓库内代码与 HTTP 烟雾验证已通过；唯一未闭环项是 **Playwright MCP 环境级不可用**，因此本轮无法在该工具中完成真实浏览器点击回归。

### 2026-04-12 修订 2.0 PRD 的前端页面与交互约束

- 执行内容：按仓库文档顺序读取 [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md)、[状态文档](/Users/itboybob/Project/fire/docs/status.md)、[设计文档](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-design.md)、[旧实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md)、[2.0 实施计划](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 与原 [2.0 PRD](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md)，并审查当前 [index.html](/Users/itboybob/Project/fire/app/templates/index.html)、[app.js](/Users/itboybob/Project/fire/app/static/app.js)、[app.css](/Users/itboybob/Project/fire/app/static/app.css) 的实际前端壳。确认本轮不是“单纯样式问题”，而是前端页面模型缺失：当前首页态和对话态没有被产品定义分开，`Starter Cards` 被挂在线程空态中，`buildThreadEmptyState()` 会直接吞掉首页卡片；`textarea` 没有正式键盘契约；旧等待态也没有最小反馈。随后已重写 [2.0 PRD](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md)，将“首页 `/` / 对话页 `/conversations/{id}`、Enter 发送 / `Shift+Enter` 换行、输入法组合态保护、提交后立即跳转与占位、首页深色启动台 / 对话页浅色证据台、未实现能力不得伪装入口”等前端页面与交互约束正式落盘。
- 执行环境：未运行 Python、pytest 或服务进程；本轮为文档修订与现状审查，命令仅涉及文件读取、文本检索和本地图片查看。
- 依赖情况：无需新增依赖，沿用当前仓库和本地图片参考。
- 验证结果：
  - 代码现状核对：已确认 [app/static/app.js](/Users/itboybob/Project/fire/app/static/app.js) 当前仅监听 `form submit`，没有 `keydown` 级别的 `Enter` / `Shift+Enter` 规则；同时 `buildThreadEmptyState()` 不再渲染首页 `Starter Cards`，与模板首屏意图不一致。
  - 视觉参考核对：已直接读取用户提供的“旧首页”“对话页面”图片，确认目标不是继续放大“历史会话管理页”，而是拆成“深色首页启动台”和“浅色对话证据台”两种正式页面态。
  - 官方文档核对：已通过 `Tavily` 检索 `developer.mozilla.org` 官方文档，确认 `KeyboardEvent.isComposing` 的当前语义和 `History.pushState()` / `popstate` 的当前用法，可支撑 PRD 中“输入法组合态下 Enter 不发送”和“首页/对话页 URL 同步”两条前端契约。
- 当时阻塞点：产品约束已补齐，但 [2.0 实施计划](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 尚未同步到这版前端重构边界。该文档同步已由 `2026-04-23` 的 NDJSON 状态流文档更新处理；后续应按“流式状态专项阶段”进入 TDD。

### 2026-04-11 审查并修复 2.0 计划 Task 7-10 当前实现

- 执行内容：按 `requesting-code-review` 工作流审查 [2.0 实施计划 Task 7-10](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 的当前实现，并对照 [2.0 PRD](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md) 检查“会话编排、会话 API、依赖注入、双栏前端壳、最终验证契约”是否真的落地。由于当前会话未暴露 `Task`/子代理调度工具，本轮改为按 `requesting-code-review/code-reviewer.md` 模板手工执行同等审查，结合 `git diff 0b78870..8d1441d`、当前工作树与真实运行行为一起复核。审查中确认并修复了 5 个真实缺陷：范围延伸追问现在会继承上一轮法规标题；当前历史摘要会写回 [conversation_summaries](/Users/itboybob/Project/fire/app/services/conversation_repository.py) 并从详情 API 返回；追问拒答不会再误报“本轮已根据最新检索证据修正前文”；软删除后的会话不再允许继续写 `answer_snapshots`；`turns` 也不能再引用其他会话的消息。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境、现有 FastAPI/Pydantic/pytest 依赖与仓库内真实 `data/chunks/` 产物。
- 验证结果：
  - 定向回归：`conda run --no-capture-output -n fire python -m pytest tests/unit/services/test_turn_classifier.py tests/unit/services/test_conversation_presenter.py tests/unit/services/test_conversation_repository.py tests/unit/services/test_conversation_turn_service.py tests/unit/api/test_conversation_dependencies.py tests/integration/api/test_conversations_api.py tests/integration/api/test_chat_api.py -q` 结果为 `27 passed in 0.54s`
  - 全量回归：`conda run --no-capture-output -n fire python -m pytest -q` 结果为 `86 passed, 1 xfailed in 0.71s`
  - 真实上游烟雾验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 使用真实 [data/chunks/xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl) 构造两轮会话，输出 `{'conversation_title': '消防法关于消防安全责任制怎么规定', 'history_summary': '消防法关于消防安全责任制怎么规定？ -> 《中华人民共和国消防法》第二条', 'latest_rewritten_query': '中华人民共和国消防法 河北也适用吗？ 消防法关于消防安全责任制怎么规定？ 《中华人民共和国消防法》第二条', 'latest_correction_notice': '', 'latest_knowledge_version': 'kb:real-chunk-smoke', 'latest_clause_path': '中华人民共和国消防法 > 第一章 总则 > 第二条'}`，已确认真实 chunk 产物下的摘要写回、范围延伸追问继承与详情读取都按预期工作。
- 当前阻塞点：`Task 7-10` 本轮审查发现的仓库内代码缺陷已全部修复并验证通过；当前无新的仓库内技术阻塞，剩余风险仍主要来自外部聊天提供商的可用性与限流策略。

### 2026-04-11 修复 Task 1-3 审查发现的仓库层缺陷

- 执行内容：在完成 `Task 1-3` review 并锁定根因后，按 `systematic-debugging` + `tdd-workflow` 先补红测，再修复 [conversation_repository.py](/Users/itboybob/Project/fire/app/services/conversation_repository.py) 的仓库层写路径。具体把 `append_message`、`create_turn`、`save_answer_snapshot`、`update_conversation_title` 和 `save_history_summary` 从“先检查、再写入”的非原子流程收敛为单事务条件写入，并在失败时抛出可区分异常；同时把 [test_conversation_service.py](/Users/itboybob/Project/fire/tests/unit/services/test_conversation_service.py) 中“按最近消息排序”的伪覆盖改成真实消息时间排序覆盖。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境、Python 标准库 `sqlite3` 与现有测试依赖。
- 验证结果：
  - 官方文档核对：已通过 `Tavily` 检索 `docs.python.org/3/library/sqlite3.html` 与 `sqlite.org/foreignkeys.html`，确认 Python `sqlite3` 连接上下文管理器的提交/回滚语义、DML 触发事务行为，以及 SQLite 复合/即时外键约束的当前官方说明，再据此决定用“单事务条件写入 + 仓库层验证”修复，而不是继续依赖分离的预检查。
  - 红测确认：
    - `conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q` 初次结果为 `1 passed, 2 failed in 0.05s`，失败点正好对应“软删除后仍能写 snapshot”“跨会话消息仍能建 turn”
    - `conda run -n fire python -m pytest tests/unit/services/test_conversation_service.py -q` 在调整排序测试为真实消息排序后保持通过
  - 修复后回归：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/unit/services/test_conversation_repository.py tests/unit/services/test_conversation_service.py tests/unit/services/test_conversation_summary.py tests/unit/services/test_conversation_turn_service.py tests/integration/api/test_conversations_api.py -q` 结果为 `21 passed in 0.47s`
  - 复现脚本回归：
    - `conda run --no-capture-output -n fire python - <<'PY' ... PY` 现输出 `{'saved_after_delete': False, 'blocked': True}`，确认已删除会话不再接受 `answer_snapshots` 写入
    - `conda run --no-capture-output -n fire python - <<'PY' ... PY` 现输出 `{'cross_conversation_turn_blocked': True, 'message': 'turn messages must belong to the same conversation'}`，确认 `turns` 已不能再引用其他会话消息
- 当前阻塞点：`Task 1-3` 本轮 review 发现的代码级阻塞已解除；当前无新的仓库内技术阻塞，后续可继续按同样方式审查 `Task 4+`。

### 2026-04-11 审查 2.0 计划 Task 1-3 当前实现

- 执行内容：按 `requesting-code-review` 工作流审查 [2.0 实施计划 Task 1-3](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 的当前实现，而不是只看原始提交。先按仓库规则读取 [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md)、[状态文档](/Users/itboybob/Project/fire/docs/status.md)、[2.0 PRD](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md) 与实施计划，再检查 [settings.py](/Users/itboybob/Project/fire/app/core/settings.py)、[conversation_repository.py](/Users/itboybob/Project/fire/app/services/conversation_repository.py)、[conversation_service.py](/Users/itboybob/Project/fire/app/services/conversation_service.py) 及对应测试。由于当前会话未暴露 `Task`/子代理调度工具，本轮改为按 `requesting-code-review/code-reviewer.md` 模板手工执行同等审查，并补做最小 SQLite 复现脚本确认边界行为。
- 执行环境：代码执行均使用 `fire`；源码阅读、`git diff` 与文本检索未依赖 Python 运行时。
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境与标准库 `sqlite3`。
- 验证结果：
  - `conda run -n fire python -m pytest tests/unit/core/test_settings.py -q` 结果为 `3 passed in 0.11s`
  - `conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q` 结果为 `1 passed in 0.03s`
  - `conda run -n fire python -m pytest tests/unit/services/test_conversation_service.py -q` 结果为 `3 passed in 0.03s`
  - `conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py -q` 结果为 `3 passed in 0.53s`
  - `conda run --no-capture-output -n fire python - <<'PY' ... PY` 复现“先建 turn、再软删除、最后写 snapshot”后，输出 `{'saved_after_delete': True, 'turn_id': '...'}`，已确认当前仓库仍允许在已删除会话上继续写入 `answer_snapshots`
  - `conda run --no-capture-output -n fire python - <<'PY' ... PY` 复现“用会话 A 的消息为会话 B 建 turn”后，输出 `{'detail_turns': 1, 'detail_messages': ['...']}`，已确认当前仓库允许 `turns` 引用其他会话的消息，破坏会话内数据一致性
- 当前阻塞点：`Task 1-3` 的自动化测试虽然仍全绿，但当前实现存在两个新的代码级阻塞点：`ConversationRepository.save_answer_snapshot()` 未兑现“已删除会话不可继续写入”，`ConversationRepository.create_turn()` / schema 也未保证 turn 只能引用本会话消息；在补齐约束和回归测试前，`Task 2-3` 不应被视为审查通过。

### 2026-04-11 使用新 API Key 完成 2.0 最终真实验收

- 执行内容：在用户提供新的 iFlow `CHAT_API_KEY` 后，继续按 `systematic-debugging` 排查剩余真实链路问题。先确认 `.env` 中会话所用 `CHAT_BASE_URL=https://apis.iflow.cn/v1`、`CHAT_MODEL=qwen3-32b` 与新 key 已生效；随后在真实服务进程下做多轮问答验收，先后定位并修复了 4 个真实问题：
  - iFlow 返回的 JSON 被 ```json 代码块包裹，导致 [OpenAIChatClient](/Users/itboybob/Project/fire/app/services/chat_client.py) 的严格 JSON 校验误报失败；
  - iFlow `status=449` 限流错误会直接中断会话，没有最小重试；
  - [ConversationPresenter](/Users/itboybob/Project/fire/app/services/conversation_presenter.py) 会把所有检索证据都塞进 `clause_texts`，不符合 PRD “证据区只展示法律依据对应条文原文”的要求；
  - [TurnClassifier](/Users/itboybob/Project/fire/app/services/turn_classifier.py) 只识别“它/这个/上一轮”等显式指代词，无法把“河北也适用吗？”识别为范围延伸追问，导致法律依据变化时缺少修正提示。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境和现有 iFlow / 嵌入模型配置。
- 验证结果：
  - 新 key 生效后第一次真实探针：首轮会话已不再报 token 过期，但暴露出 `模型返回了无法通过 schema 校验的 JSON。`；抓取原始返回确认 `content` 实际为合法 JSON，只是被 ```json 代码块包裹。
  - 修复后单测回归：
    - `conda run -n fire python -m pytest tests/unit/services/test_answer_service.py -q` 结果为 `10 passed in 0.33s`
    - `conda run -n fire python -m pytest tests/unit/services/test_turn_classifier.py tests/unit/services/test_conversation_presenter.py tests/unit/services/test_conversation_turn_service.py tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q` 分批结果均通过
  - 全量回归：`conda run -n fire python -m pytest -q` 结果为 `79 passed, 1 xfailed in 0.81s`
  - 真实服务验收：
    - 启动 `conda run -n fire python -m uvicorn app.main:create_app --factory --port 8014`
    - 新建会话并提问“消防法关于消防安全责任制怎么规定？”：HTTP `200`，回答引用 `《中华人民共和国消防法》第十六条`，证据区只展示第十六条原文
    - 同会话追问“它第二条怎么说？”：HTTP `200`，回答切换为 `《中华人民共和国消防法》第二条`，并正确显示修正提示 `本轮已根据最新检索证据修正前文。`
    - 重命名会话、创建并删除无用会话：均通过
    - 重启服务后重新读取 `/api/conversations` 与 `/api/conversations/{id}`：历史会话恢复成功
    - 在旧会话继续追问“河北也适用吗？”：HTTP `200`，回答切换为河北地方性依据，当前返回 `《河北省消防安全责任制规定》第二条`，并正确显示修正提示；会话详情累计消息数从 `4` 增长到 `6`
- 当前阻塞点：本轮主线已完成，当前无新的代码阻塞；若后续再次出现限流或提供商异常，应优先视为外部运行时问题，而不是 2.0 会话系统主链缺陷。

### 2026-04-11 执行 2.0 计划 Task 10

- 执行内容：按 `executing-plans` 与 `systematic-debugging` 继续执行 [2.0 实施计划 Task 10](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先针对真实验收中暴露的“会话 API 返回 `证据不足，无法可靠回答。` 且 `legal_basis=[]`”现象做根因追踪，确认问题不在检索或会话编排，而在真实 iFlow 提供商返回了无 `choices` 的错误载荷；随后补红测锁住两类行为：一是 `OpenAIChatClient` 能识别 `status/msg` 形式的提供商错误，二是 `/api/conversations/{id}/messages` 在模型失败时必须返回 `502`，不能再把上游故障吞成普通拒答。最终补最小实现，保留模型失败明细，并让会话链路与 `/api/chat` 一样显式暴露 `502`。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境、现有真实索引产物和已配置的 OpenAI 兼容聊天提供商。
- 验证结果：
  - 根因探针：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 直接调用真实聊天 SDK 后，返回对象为 `{'choices': None, 'status': '439', 'msg': '「Your API Token has expired. API Tokens have a validity period of 7 days. ...」'}`，已确认真实阻塞点是 iFlow token 过期，而不是检索缺证据。
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py tests/unit/services/test_conversation_turn_service.py tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q` 初次结果为 `5 failed, 16 passed in 0.60s`，失败点正好对应“模型失败细节未保留 / conversations API 未返回 502 / chat_client 未识别提供商错误载荷”。
  - 修复后回归：同一命令结果为 `21 passed in 0.39s`。
  - 2.0 目标测试：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/unit/services/test_conversation_repository.py tests/unit/services/test_conversation_service.py tests/unit/services/test_turn_classifier.py tests/unit/services/test_context_manager.py tests/unit/services/test_conversation_summary.py tests/unit/services/test_knowledge_version.py tests/unit/services/test_conversation_presenter.py tests/unit/services/test_query_normalizer.py tests/unit/services/test_conversation_turn_service.py tests/unit/api/test_chat_dependencies.py tests/unit/api/test_conversation_dependencies.py tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q` 结果为 `33 passed in 0.42s`。
  - 全量回归：`conda run -n fire python -m pytest -q` 结果为 `75 passed, 1 xfailed in 0.70s`。
  - 真实建库验证：
    - `conda run -n fire python scripts/build_corpus.py` 成功重建全部 `data/chunks/*.jsonl`
    - `conda run -n fire python scripts/build_index.py` 结果为 `chunks=328`，并成功输出 `data/index/retrieval.db`、`data/index/faiss.index`、`data/index/vector_map.json`
  - 真实服务验证：启动 `conda run -n fire python -m uvicorn app.main:create_app --factory --port 8012` 后，用真实 HTTP 请求完成页面和 API 检查，输出为：
    - 根页面命中 `conversation-list / conversation-thread / composer-form`
    - 创建会话 `201`
    - 首次真实发消息返回 `502`，详情为 `模型调用失败：提供商返回错误（status=439）：「Your API Token has expired...」`
    - 重命名、列表、详情仍可用，失败后会话中只保留用户消息，不再伪造一条空依据助手回复
    - 重启服务后再次读取 `/api/conversations`，历史会话仍然可见，说明本机持久化恢复正常
- 当前阻塞点：代码侧主线任务已经完成，当前剩余唯一阻塞点是 `.env` 中现用 iFlow `CHAT_API_KEY` 已过期；在用户更新有效凭证前，无法把“消防法关于消防安全责任制怎么规定？ -> 它第二条怎么说？ -> 河北也适用吗？”这一整条真实多轮回答链路标记为通过，但系统已经改为准确暴露上游失败原因，不再误报成“证据不足”。

### 2026-04-11 执行 2.0 计划 Task 9

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 9](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先把 [test_chat_api.py](/Users/itboybob/Project/fire/tests/integration/api/test_chat_api.py) 的根页面断言切到新壳标识，再整体替换 [index.html](/Users/itboybob/Project/fire/app/templates/index.html)、[app.js](/Users/itboybob/Project/fire/app/static/app.js)、[app.css](/Users/itboybob/Project/fire/app/static/app.css)，将旧的单轮验证面板改成双栏会话产品界面，并让前端主链改为加载/创建/切换/重命名/删除会话及发送 `/api/conversations/{id}/messages`。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境和现有静态资源链路。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q` 初次结果为 `1 failed, 4 passed in 0.42s`，失败原因是根页面仍是旧的单轮壳
  - Task 9 测试：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py tests/integration/api/test_conversations_api.py -q` 结果为 `7 passed in 0.33s`
  - 浏览器自动化说明：尝试用 Playwright 做真实页面点击时，工具初始化被环境级只读根目录拦住，报错 `ENOENT: no such file or directory, mkdir '/.playwright-mcp'`；该问题属于当前会话工具运行环境，不是项目代码缺陷
  - 真实壳验证：改用 `conda run -n fire python -m uvicorn app.main:create_app --factory --port 8010` 启动本地服务，再用 `curl` 命中真实页面与 API：
    - `curl -s http://127.0.0.1:8010/ | rg 'conversation-list|conversation-thread|composer-form'` 成功命中新壳标识
    - `curl -s -X POST http://127.0.0.1:8010/api/conversations -H 'Content-Type: application/json' -d '{}'` 成功返回新会话 JSON，说明前端主链依赖的新 API 已在真实服务进程下可用
- 当前阻塞点：`Task 9` 已完成，当前无新的技术阻塞；下一步进入 `Task 10`，更新 README / 文档索引 / 状态文档并做最终全量验证。

### 2026-04-11 执行 2.0 计划 Task 8

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 8](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先查阅 FastAPI 官方 `APIRouter` / `Depends` 文档并阅读现有聊天 API 测试风格，随后新增 [conversations.py](/Users/itboybob/Project/fire/app/api/conversations.py)、会话依赖测试与集成测试，在 [main.py](/Users/itboybob/Project/fire/app/main.py) 注册新 router，并把 dataclass/字典两类返回统一序列化成正式 2.0 schema。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境中的 `fastapi/httpx` 等现有测试依赖。
- 验证结果：
  - 官方文档核对：已通过 `Tavily` 检索 `fastapi.tiangolo.com` 官方文档，确认 `APIRouter`、`Depends()` 与测试覆写依赖的当前用法。
  - 红测确认：`conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py tests/unit/api/test_conversation_dependencies.py -q` 初次因路由与依赖模块尚未实现而无法通过
  - Task 8 测试：`conda run -n fire python -m pytest tests/integration/api/test_conversations_api.py tests/unit/api/test_conversation_dependencies.py -q` 结果为 `4 passed in 0.39s`
  - 真实上游验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 使用 `TestClient(create_app())` 命中真实 `/api/conversations*` 路径，并复用真实 `data/index/` 检索产物完成两轮对话，输出为 `{'create_status': 201, 'first_status': 200, 'second_status': 200, 'detail_status': 200, 'conversation_title': '消防法关于消防安全责任制怎么规定', 'message_count': 4, 'latest_basis': ['《中华人民共和国消防法》第二条'], 'latest_correction_notice': '本轮已根据最新检索证据修正前文。'}`
- 当前阻塞点：`Task 8` 已完成，当前无新的技术阻塞；下一步进入 `Task 9`，把前端网页壳切到双栏会话界面。

### 2026-04-11 执行 2.0 计划 Task 7

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 7](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先读取现有 [query_normalizer.py](/Users/itboybob/Project/fire/app/services/query_normalizer.py)、[retriever.py](/Users/itboybob/Project/fire/app/services/retriever.py)、[answer_service.py](/Users/itboybob/Project/fire/app/services/answer_service.py) 与对应单测，确认当前单轮链路接口后，再扩展 `normalize_query(..., context_hints=...)`，新增 [conversation_turn_service.py](/Users/itboybob/Project/fire/app/services/conversation_turn_service.py) 与编排层单测，把自动标题、追问判定、摘要降级、知识库版本、重写查询、重检索、回答展示和快照落库串成正式会话主链。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境、既有真实索引产物与已安装嵌入模型依赖。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_conversation_turn_service.py -q` 初次结果为 `ModuleNotFoundError: No module named 'app.services.conversation_turn_service'`
  - Task 7 单测：`conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_conversation_turn_service.py -q` 结果为 `6 passed in 0.08s`
  - 真实上游验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 使用真实 `data/index/retrieval.db`、`data/index/faiss.index`、`data/index/vector_map.json` 与真实嵌入模型执行两轮会话烟雾，输出为 `{'title': '消防法关于消防安全责任制怎么规定', 'turns': 2, 'first_basis': ['《中华人民共和国消防法》第七十四条'], 'second_basis': ['《中华人民共和国消防法》第二条'], 'rewritten_query': '中华人民共和国消防法 第二条 它第二条怎么说？', 'knowledge_version': 'kb:f1f5874d0af3f4fd'}`；这说明追问轮确实重新检索并使用了改写后的查询，而不是直接复用首轮答案。
- 当前阻塞点：`Task 7` 已完成，当前无新的技术阻塞；下一步进入 `Task 8`，暴露会话管理和消息执行 API。

### 2026-04-11 执行 2.0 计划 Task 6

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 6](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先复核现有 [chat.py](/Users/itboybob/Project/fire/app/schemas/chat.py) 的 Pydantic v2 schema 风格，并补查 Pydantic 官方文档；随后新增 [conversation.py](/Users/itboybob/Project/fire/app/schemas/conversation.py) 与 [conversation_presenter.py](/Users/itboybob/Project/fire/app/services/conversation_presenter.py)，把 2.0 的会话列表项、会话详情、用户消息输入、助手消息展示结构和发送响应结构收敛成正式 schema，并实现“同依据复用上一轮条文，依据变化时切换到本轮条文并提示修正”的展示策略。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境中的 `pydantic 2.x`。
- 验证结果：
  - 官方文档核对：已通过 `Tavily` 检索 `docs.pydantic.dev` 官方文档，确认当前仓库应继续使用 Pydantic v2 的 `BaseModel/ConfigDict/Field` 风格。
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_conversation_presenter.py -q` 初次结果为 `ModuleNotFoundError: No module named 'app.services.conversation_presenter'`
  - Task 6 单测：`conda run -n fire python -m pytest tests/unit/services/test_conversation_presenter.py -q` 结果为 `2 passed in 0.06s`
  - 真实上游验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 直接读取真实 `data/chunks/xiaofangfa_2019.jsonl` 与 `data/chunks/hebei_xiaofang_tiaoli.jsonl` 组装两种场景，输出为 `{'reused_notice': '', 'reused_clause_texts': [{'path': '旧路径', 'text': '旧条文原文'}], 'corrected_notice': '本轮已根据最新检索证据修正前文。', 'corrected_basis': ['《河北省消防条例》第二十八条']}`
- 当前阻塞点：`Task 6` 已完成，当前无新的技术阻塞；下一步进入 `Task 7`，把追问判定、上下文组装、重检索、回答生成和快照落库编排成完整会话主链。

### 2026-04-11 执行 2.0 计划 Task 5

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 5](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先查阅 Python `3.14` 官方 `hashlib` 与文件哈希相关文档，确认稳定摘要算法和文件元数据组合方式的当前语义；随后新增 [conversation_summary.py](/Users/itboybob/Project/fire/app/services/conversation_summary.py)、[knowledge_version.py](/Users/itboybob/Project/fire/app/services/knowledge_version.py) 及对应单测，实现确定性历史摘要和基于 `retrieval.db/faiss.index/vector_map.json` 文件大小与修改时间的稳定知识库版本串。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用 Python 标准库 `hashlib/pathlib` 与当前真实索引产物。
- 验证结果：
  - 官方文档核对：已通过 `Tavily` 检索 `docs.python.org/3/library/hashlib.html`，确认 `sha256` 与文件摘要能力的当前官方语义。
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_conversation_summary.py tests/unit/services/test_knowledge_version.py -q` 初次结果为 `2 errors`，失败原因是相关模块尚不存在
  - Task 5 单测：`conda run -n fire python -m pytest tests/unit/services/test_conversation_summary.py tests/unit/services/test_knowledge_version.py -q` 结果为 `2 passed in 0.02s`
  - 真实上游验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 直接基于真实 `data/chunks/xiaofangfa_2019.jsonl` 和 `data/index/` 产物生成摘要与版本，输出为 `{'summary': '消防法关于消防安全责任制怎么规定？ -> 《中华人民共和国消防法》第二条\\n已修正前文：河北也适用吗？ -> 《河北省消防条例》第二十八条', 'knowledge_version': 'kb:f1f5874d0af3f4fd'}`
- 当前阻塞点：`Task 5` 已完成，当前无新的技术阻塞；下一步进入 `Task 6`，定义 2.0 对话响应模型并实现修正提示策略。

### 2026-04-11 执行 2.0 计划 Task 4

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 4](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。新增 [turn_classifier.py](/Users/itboybob/Project/fire/app/services/turn_classifier.py)、[context_manager.py](/Users/itboybob/Project/fire/app/services/context_manager.py) 与对应单测，实现基础追问标记词识别、上一轮法规标题/条号继承，以及“最近 N 轮 + 更早历史摘要”的上下文窗口裁剪和无摘要降级。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境与现有真实 `data/chunks/` 产物。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_turn_classifier.py tests/unit/services/test_context_manager.py -q` 初次结果为 `2 errors`，失败原因是相关模块尚不存在
  - Task 4 单测：`conda run -n fire python -m pytest tests/unit/services/test_turn_classifier.py tests/unit/services/test_context_manager.py -q` 结果为 `3 passed in 0.02s`
  - 真实上游验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 直接读取真实 `data/chunks/xiaofangfa_2019.jsonl` 中 `第二条` 证据构造上一轮，输出为 `{'is_followup': True, 'canonical_title': '中华人民共和国消防法', 'article_no': '第二条', 'recent_turns': 1, 'history_summary': '更早轮次已聚焦消防法责任制。'}`，说明追问继承和上下文裁剪在真实法规标题上工作正常。
- 当前阻塞点：`Task 4` 已完成，当前无新的技术阻塞；下一步进入 `Task 5`，实现确定性历史摘要和知识库版本解析。

### 2026-04-11 执行 2.0 计划 Task 3

### 2026-04-11 审查 QA System 2.0 Task 4-6（进行中）

- 执行内容：按 `requesting-code-review` 流程读取 `docs/文档索引.md`、`docs/status.md`、[2.0 实施计划](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md) 与 [PRD](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-prd.md)，随后对 `Task 4-6` 相关实现、测试和集成接入点展开专项 review，当前已完成目标文件、`conversation_turn_service`、会话 API 与 git 范围 `0b78870..8d1441d` 的首轮核查。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境与现有测试依赖。
- 验证结果：
  - 定向回归：`conda run -n fire python -m pytest tests/unit/services/test_turn_classifier.py tests/unit/services/test_context_manager.py tests/unit/services/test_conversation_summary.py tests/unit/services/test_knowledge_version.py tests/unit/services/test_conversation_presenter.py tests/unit/services/test_conversation_turn_service.py tests/unit/api/test_conversation_dependencies.py tests/integration/api/test_conversations_api.py -q` 结果为 `18 passed in 0.52s`
  - 当前已确认：基础单测和已落地的编排/API 契约没有立即红测，说明问题更可能藏在未覆盖边界和模块接线，而不是显式主路径崩溃
  - 追问边界复现：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 直接调用 `TurnClassifier + normalize_query`，对上一轮已含 `中华人民共和国消防法 / 第二条` 的场景输入“河北也适用吗？”，输出为 `{'is_followup': True, 'context_hints': {}, 'rewritten_query': '河北也适用吗？', 'vector_query': '河北也适用吗？'}`，已确认范围延伸追问会丢失上一轮法规上下文
  - 修正提示复现：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 直接调用 `ConversationPresenter.build()`，对“上一轮有依据、本轮拒答且 `citations=[]`”的场景输出为 `{'correction_notice': '本轮已根据最新检索证据修正前文。', ...}`，已确认拒答也会被误标为“修正前文”
  - 摘要接线复现：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 构造 3 轮历史后调用 `ConversationTurnService.handle_user_message()`，输出为 `{'saved_history_summary_used': 'SUMMARY:前文问题0|前文问题1', 'retriever_vector_query': '中华人民共和国消防法 第二条 继续说明 中华人民共和国消防法', 'chat_prompt_contains_summary': False}`，已确认摘要会被保存到轮次元数据，但不会进入当前轮检索或答案生成输入
- 当前阻塞点：专项审查阶段已确认至少 3 个当前测试未覆盖的实现缺口；下一步整理正式 review 结论，并按用户要求决定是否继续进入修复。

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 3](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。基于上一任务的仓库层能力新增 [conversation_service.py](/Users/itboybob/Project/fire/app/services/conversation_service.py) 与服务层单测，把“新会话默认标题”“首条用户消息触发自动标题”“按最近消息排序”“重命名”“软删除”“删除后不可继续写入”等产品规则从存储层之上收拢到应用服务层。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境与现有 `sqlite3` 仓库实现。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_conversation_service.py -q` 初次结果为 `ModuleNotFoundError: No module named 'app.services.conversation_service'`
  - Task 3 单测：`conda run -n fire python -m pytest tests/unit/services/test_conversation_service.py -q` 结果为 `3 passed in 0.02s`
  - 真实服务验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 在 `var/task3-smoke.db` 上完成真实创建、自动标题、重命名、软删除与删除后禁写验证，输出为 `{'db': 'var/task3-smoke.db', 'renamed_title': '消防法责任制', 'remaining': 0, 'write_blocked': True}`
- 当前阻塞点：`Task 3` 已完成，当前无新的技术阻塞；下一步进入 `Task 4`，实现追问判定和上下文窗口管理。

### 2026-04-11 执行 2.0 计划 Task 2

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 2](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先查阅 Python `3.14` 官方 `sqlite3` 文档，确认 `connect()` 仍支持路径对象、`Row` 工厂、`lastrowid` 语义与参数化查询约束；随后新增 [conversation_repository.py](/Users/itboybob/Project/fire/app/services/conversation_repository.py) 和对应单测，落地 `conversations/messages/turns/answer_snapshots` 四表、父目录自动创建、会话详情读取，以及后续任务会复用的排序/重命名/软删除基础能力。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用 Python 标准库 `sqlite3` 与当前 `fire` 环境。
- 验证结果：
  - 官方文档核对：已通过 `Tavily` 检索 `docs.python.org/3/library/sqlite3.html`，确认参数化查询、`sqlite3.Row` 与 `lastrowid`/连接行为的当前官方语义。
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q` 初次结果为 `ModuleNotFoundError: No module named 'app.services.conversation_repository'`
  - Task 2 单测：`conda run -n fire python -m pytest tests/unit/services/test_conversation_repository.py -q` 结果为 `1 passed in 0.03s`
  - 真实落库验证：`conda run --no-capture-output -n fire python - <<'PY' ... PY` 在 `var/task2-smoke.db` 上完成真实 SQLite 建库、写入、重开读取，输出为 `{'db': 'var/task2-smoke.db', 'messages': 2, 'snapshots': 1, 'title': '真实验证会话'}`
- 当前阻塞点：`Task 2` 已完成，当前无新的技术阻塞；下一步进入 `Task 3`，把会话生命周期和自动标题规则上移到服务层。

### 2026-04-11 执行 2.0 计划 Task 1

- 执行内容：按 `executing-plans` 与 TDD 执行 [2.0 实施计划 Task 1](/Users/itboybob/Project/fire/docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)。先读取文档索引、状态文档、PRD 与实施计划，审查到当前工作树存在未提交文档改动且当前分支为 `main`，因此先切出本地执行分支 `qa-system-2.0-exec`；随后查阅 `pydantic-settings` 官方文档，确认 `BaseSettings + SettingsConfigDict(env_file='.env', extra='ignore')` 仍是当前兼容写法，并按红绿测试补齐会话配置默认值与 `.env.example` 占位项。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境内已安装的 `pydantic-settings 2.13.x`。
- 验证结果：
  - 官方文档核对：已通过 `Tavily` 检索 `docs.pydantic.dev` 官方文档，确认 `BaseSettings` 默认值、`.env` 支持与 `extra='ignore'` 的当前推荐写法仍有效。
  - 红测确认：`conda run -n fire python -m pytest tests/unit/core/test_settings.py -q` 初次结果为 `1 failed, 2 passed in 0.11s`，失败原因是 `Settings` 尚不存在 `conversation_db_path`
  - 绿测结果：修正实现与测试导入后，`conda run -n fire python -m pytest tests/unit/core/test_settings.py -q` 结果为 `3 passed in 0.05s`
- 当前阻塞点：`Task 1` 已完成，当前无新的技术阻塞；下一步进入 `Task 2`，建立 `SQLite` 会话仓库并补齐持久化读写测试。

### 2026-04-11 调整 Git 提交通知时机

- 执行内容：按用户最新要求再次修改 [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md)，将“代理提交前必须先向用户同步提交范围、已完成验证结果与拟使用的提交说明”调整为“代理提交后必须尽快同步本次提交范围、已完成验证结果与实际使用的提交说明”；同时保留“不得夹带无关改动”和“不得擅自执行高风险 Git 操作”的约束。
- 执行环境：本轮仅修改文档并复核文本差异；未执行 Python、pytest、脚本或服务启动命令，因此无需 `fire` 环境代码验证。
- 依赖情况：无需新增依赖，沿用现有环境。
- 验证结果：
  - [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md) 已完成同步时机调整，当前仓库级口径允许代理先提交、后同步
  - 提交范围约束与高风险 Git 操作禁令仍保留，避免规则被放宽成“任意 Git 操作均可自主执行”
  - 本轮未执行代码，因此不存在“非 `fire` 环境代码验证”的合规缺口
- 当前阻塞点：本次规则调整已完成，仓库级规则无新阻塞；但实际会话是否执行 Git 操作，仍受当次会话的更高优先级系统约束控制。

### 2026-04-11 调整仓库级 Git 提交权限

- 执行内容：按用户要求修改 [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md)，将原“代理不得擅自提交代码”的绝对禁止规则，收敛为“允许代理在当前任务范围内自主执行受控 `git add` / `git commit`”；同时补充提交前同步范围、验证结果与提交说明，以及禁止擅自 `push / merge / rebase / reset / checkout --` 和避开无关改动的约束。
- 执行环境：本轮仅修改文档并复核文本差异；未执行 Python、pytest、脚本或服务启动命令，因此无需 `fire` 环境代码验证。
- 依赖情况：无需新增依赖，沿用现有环境。
- 验证结果：
  - [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md) 已完成规则更新，当前仓库级口径不再禁止代理自主 `commit`
  - 风险控制条款已同时落盘，避免把“允许提交”扩大为“允许任意 Git 操作”
  - 本轮未执行代码，因此不存在“非 `fire` 环境代码验证”的合规缺口
- 当前阻塞点：本次文档规则调整已完成，仓库级规则无新阻塞；但实际会话是否执行 Git 操作，仍受当次会话的更高优先级系统约束控制。

### 2026-04-11 增量建库机制设计前勘察

- 执行内容：按新会话读取顺序先检查 [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md) 与 [项目状态](/Users/itboybob/Project/fire/docs/status.md)，随后复核 [设计文档](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-design.md)、[实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md)、[README.md](/Users/itboybob/Project/fire/README.md)、[corpus_ingestor.py](/Users/itboybob/Project/fire/app/services/corpus_ingestor.py)、[normalizer.py](/Users/itboybob/Project/fire/app/services/normalizer.py)、[structure_parser.py](/Users/itboybob/Project/fire/app/services/structure_parser.py)、[chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py)、[build_corpus.py](/Users/itboybob/Project/fire/scripts/build_corpus.py)、[build_index.py](/Users/itboybob/Project/fire/scripts/build_index.py)、[test_corpus_ingestor.py](/Users/itboybob/Project/fire/tests/unit/services/test_corpus_ingestor.py) 与最近提交历史，评估“新增法规后的增量处理机制”应落在哪一层。
- 执行环境：本轮以只读勘察为主；目录计数已通过 `conda run -n fire python -c ...` 在 `fire` 环境补做一次合规探针。勘察早期曾误执行过一次**未走 `fire` 环境的只读 Python 目录计数探针**，该探针不计入任何验证结论，仅作为过程失误留痕。
- 验证结果：
  - 当前离线链路的真实入口仍是“扫描 `法律文本/` 后全量执行 `normalize -> parse -> chunk`”，[build_corpus.py](/Users/itboybob/Project/fire/scripts/build_corpus.py) 不区分新增、变更、删除，也不会保存任何上次构建状态。
  - 当前索引链路的真实入口仍是“读取 `data/chunks/*.jsonl` 后全量执行关键词索引与向量索引构建”，[build_index.py](/Users/itboybob/Project/fire/scripts/build_index.py) 也没有文档级增量更新能力。
  - [设计文档](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-design.md) 和 [实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md) 都提到 `data/manifests/`，但当前仓库实际不存在该目录；合规探针确认当前 `data/normalized=6`、`data/structured=6`、`data/chunks=6`、`data/index=3`、`data/manifests=0`。
  - 当前 [CorpusIngestor](/Users/itboybob/Project/fire/app/services/corpus_ingestor.py) 只负责生成稳定 `document_id` 与输入清单，不负责内容摘要、源文件指纹、构建批次号或依赖关系记录；这意味着系统目前没有足够状态去判断“哪些法规需要重建、哪些索引可以复用”。
- 当前阻塞点：在给增量机制出正式设计前，需要先澄清未来语料变更模型究竟是“只会新增新法规”，还是还会出现“同名法规替换修订版 / 原文件覆盖更新 / 删除旧法规”等场景；这会直接决定清单模型、失效传播和索引更新策略。

### 2026-03-29 Task 11 完成后的依赖与真实聊天前置条件复核

- 执行内容：根据用户要求，在 `Task 11` 完成后继续检查“项目所有依赖是否安装完成，以及是否可以触发真实聊天并在前端网页测试”。先启动 `@code-reviewer` 做只读复核；同时由主代理在 `fire` 环境分步检查运行时依赖导入情况、`.env` 中聊天与嵌入配置是否已脱离占位值，以及 `data/index/` 下三类索引文件是否存在。
- 执行环境：`fire`
- 依赖情况：本轮为复核与验证；未新增依赖安装。
- 验证结果：
  - 依赖探针最终结果：`fastapi 0.135.2`、`jinja2 3.1.6`、`openai 2.30.0`、`uvicorn 0.42.0`、`httpx 0.28.1`、`pytest 9.0.2`、`numpy 2.4.3`、`faiss 1.13.2`、`sentence-transformers 5.3.0` 均可导入
  - 自动化测试相关依赖现状：`playwright` 当前仍未安装，探针结果为 `ModuleNotFoundError: No module named 'playwright'`
  - 聊天配置就绪度：`CHAT_API_KEY`、`CHAT_BASE_URL`、`CHAT_MODEL` 当前均已脱离仓库占位值，`EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  - 索引就绪度：`data/index/retrieval.db`、`data/index/faiss.index`、`data/index/vector_map.json` 当前均存在
  - 过程说明：本轮中有三次依赖探针命令因为 shell 引号转义写错而失败，但失败点都在验证命令本身，不在运行环境；最终已用可审计输出重新确认结果
- 当前阻塞点：当前不存在阻止“手工真实聊天测试”的缺失依赖；唯一缺口是 `playwright` 未安装，因此如果要做浏览器自动化点击测试，仍需先向用户报备并获批安装相关依赖。
- 补充验证：在 `fire` 环境通过 `TestClient(create_app())` 对真实 `/api/chat` 发起一次请求（问题：`消防法关于消防安全责任制怎么规定？`，`top_k=3`），结果为 HTTP `502`，响应体 `{'detail': '模型调用失败，当前无法基于证据生成稳定结论。'}`；这说明真实聊天链路已能触发到模型调用阶段，但当前还未达到“前端网页可稳定演示真实回答”的状态
- 根因补查：在 `fire` 环境直接调用 [OpenAIChatClient.complete()](/Users/itboybob/Project/fire/app/services/chat_client.py) 后，当前真实提供商返回的是 `ChatCompletionError: 模型返回了无法通过 schema 校验的 JSON。`；因此当前主问题不是缺依赖、缺索引或前端请求路径错误，而是现用提供商 / 模型对 `json_schema + strict` 的响应与本地 `ModelAnswer` 校验口径不兼容
- 官方文档对照补查：通过 MCP 抓取 iFlow 官方 [API 手册](https://platform.iflow.cn/docs/api-reference) 后，已确认官方 `POST https://apis.iflow.cn/v1/chat/completions` 示例里使用的是 `response_format: {\"type\": \"text\"}`，而不是当前代码采用的 `json_schema + strict`
- 官方文档驱动实验：在 `fire` 环境使用真实 `qwen3-32b` 和 iFlow 官方文档示例参数 `response_format={\"type\":\"text\"}` 直接请求后，模型成功返回可被 `json.loads()` 解析的合法 JSON，字段完整为 `conclusion/citations/scope/uncertainty`；这进一步说明真实接入问题的根因位于 iFlow 兼容层参数选择，而不是模型本身、索引本身或前端请求链路
- 修复进展：当前已按官方文档口径收窄 [OpenAIChatClient](/Users/itboybob/Project/fire/app/services/chat_client.py) 的 iFlow 分支：`iflow.cn` 走 `response_format={\"type\":\"text\"}`，其他提供商仍保留 `json_schema + strict`；同时已补单测锁住这条兼容逻辑
- 修复后回归：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py tests/integration/api/test_chat_api.py -q` 结果为 `11 passed in 0.34s`
- 修复后真实链路复验：再次通过 `TestClient(create_app())` 请求真实 `/api/chat` 后，结果仍为 HTTP `502`，响应体 `{'detail': '模型调用失败，当前无法基于证据生成稳定结论。'}`；这说明“改成官方 `response_format=text`”只能证明 iFlow 基础 JSON 输出可行，但在当前完整 RAG prompt 下，模型返回内容仍未稳定满足本地 `ModelAnswer` 校验
- 稳定性补样：继续在 `fire` 环境对真实 `/api/chat` 连续发起 `3` 次同问题请求后，结果为 `2` 次 HTTP `200`、`1` 次 HTTP `502`；成功样本的结论均为“根据《中华人民共和国消防法》第十六条，单位的主要负责人是本单位的消防安全责任人”，失败样本仍是 `模型调用失败，当前无法基于证据生成稳定结论。`。这说明官方文档驱动修复已把接入状态从“固定失败”提升到“可用但不稳定”
- 全量回归补记：在完成 iFlow 兼容层修复后重新执行 `conda run -n fire python -m pytest -q`，结果为 `50 passed, 1 xfailed in 0.55s`；唯一 `xfailed` 仍是已登记的 `chunk_builder` 枚举级技术债，与本轮 iFlow 调试无直接耦合

### 2026-03-29 完成知识图谱增强兼容性调研

- 执行内容：按仓库文档读取规则先核对 [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md)、[项目状态](/Users/itboybob/Project/fire/docs/status.md) 与 [设计文档](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-design.md)，确认当前基线已明确将“Neo4j、知识图谱、三元组联动”排除在本阶段范围外；随后使用 `Tavily MCP` 广泛检索 Microsoft GraphRAG、Neo4j GraphRAG 与知识图谱增强 RAG 的最新公开资料，评估现有离线建库 / 在线检索分层是否支持后续扩展。
- 执行环境：本轮为架构调研与资料检索；未执行新的 Python、pytest、建库脚本或服务启动命令。
- 验证结果：
  - 当前仓库设计虽然**不把知识图谱纳入现阶段范围**，但离线链路与在线链路边界清晰，且 [Retriever](/Users/itboybob/Project/fire/app/services/retriever.py) 与设计文档中的 `EvidenceAssembler` / `AnswerService` 职责已分离，因此从架构上看**可以兼容后续知识图谱增强**，但属于新增能力，不是零改动直接开启
  - 外部资料一致表明，知识图谱增强通常应优先插入“离线建库 + 在线检索”两层：离线侧先抽取实体/关系并构建图索引，在线侧再在初始检索命中后做实体扩展、邻居遍历或图约束召回，而不是只在最终答案生成阶段临时拼接
  - 对本项目而言，最稳妥的接入点是：在现有“结构解析/切块”之后新增一段图构建流程，并在现有混合检索之后新增图扩展检索；`AnswerService` 仍只消费统一证据，不应承担图构建主职责
- 当前阻塞点：若未来真的进入知识图谱增强实现，首先要做的是**重新批准设计边界**，因为当前正式设计基线仍将 Neo4j / 知识图谱排除在范围外；其次要决定是先做轻量本地图结构（法规-章节-条文-引用关系），还是直接引入 Neo4j 这类更重的外部存储。

### 2026-03-29 真实问句诊断：`消防安全责任制` 回答偏窄

- 执行内容：基于用户真实问句“消防法关于消防安全责任制是怎么规定的”，先核对现行《中华人民共和国消防法》官方公开文本，再在 `fire` 环境下读取 [query_normalizer.py](/Users/itboybob/Project/fire/app/services/query_normalizer.py)、[keyword_index.py](/Users/itboybob/Project/fire/app/services/keyword_index.py)、[retriever.py](/Users/itboybob/Project/fire/app/services/retriever.py) 与 [answer_service.py](/Users/itboybob/Project/fire/app/services/answer_service.py)，并对真实索引执行 `normalize_query()`、`search_keyword_index()` 与 `Retriever.search()` 探针，定位“回答为什么显得怪”。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境内已有的 `sqlite3`、`sentence-transformers`、`faiss-cpu` 与现有真实索引产物；法条核对额外参考四川省消防救援总队公开的现行《中华人民共和国消防法》全文页面（反映 `2021-04-29` 修正后的文本）。
- 验证结果：
  - `normalize_query("消防法关于消防安全责任制是怎么规定的")` 当前产出 `keyword_terms=['消防法关于消防安全责任制是怎么规定的', '中华人民共和国消防法']`，没有把“消防安全责任制”单独沉淀成关键词；对应实现位于 [query_normalizer.py](/Users/itboybob/Project/fire/app/services/query_normalizer.py#L49)。
  - 对真实索引执行 `search_keyword_index("中华人民共和国消防法", data/index/retrieval.db)` 后，前 `8` 条结果依次出现 [第七十四条](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl)、[第十六条末句](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl)、第七十二条、第四十八条等；其中首项竟是“本法自 `2009年5月1日` 起施行”，说明当前 FTS 排序会把“仅命中法规标题”的块错误抬高。相关实现位于 [keyword_index.py](/Users/itboybob/Project/fire/app/services/keyword_index.py#L51)。
  - 对真实索引执行 `Retriever.search(..., top_k=8)` 后，前 `3` 条结果为 `article-74`、`article-16-part-2`、`article-72`，而真正更贴近问题的《消防法》第二条未进入前列；这说明当前“标题词 + 宽泛责任类问句”的检索质量不足，生成模型即使不胡编，也很容易被错误证据带偏。
  - 官方公开文本显示：现行《消防法》第二条先从总则层面规定“实行消防安全责任制”；第十六条再具体列举单位应履行的消防安全职责，并在条末规定“单位的主要负责人是本单位的消防安全责任人”。因此，真实聊天返回“根据《中华人民共和国消防法》第十六条，单位的主要负责人是本单位的消防安全责任人”虽然不算纯错答，但明显属于**抓到一条局部规定后把它误当成整体结论**。
  - 当前 [answer_service.py](/Users/itboybob/Project/fire/app/services/answer_service.py#L77) 的提示词只要求“依据证据输出结论”，并未强制模型区分“总则层面的总体规定”和“具体条款中的责任人/职责细项”，这会进一步放大检索偏差带来的结论收缩问题。
- 当前阻塞点：主线暂无新增技术阻塞；当前新增的是一个非阻塞质量风险，即“标题别名进入关键词检索后会把无关条文抬高，答案提示词又缺少‘先总后分’约束”，因此像“怎么规定”“如何规定”这类概括型问句仍可能继续出现“法律上局部正确、语义上答非所问”的回答。

### 2026-03-29 原主线 Task 11 首轮红测成立并暴露原始夹具缺口

- 执行内容：按 `executing-plans` 与 TDD 开始执行 [原主线 Task 11](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L715)。先读取文档索引、状态、实施计划、设计文档，并补查 FastAPI 官方文档中 `Jinja2Templates` 与 `StaticFiles` 的当前推荐接法，以及 MDN 对浏览器 `fetch()` 错误处理的建议；随后在 [test_chat_api.py](/Users/itboybob/Project/fire/tests/integration/api/test_chat_api.py) 中新增根页面渲染断言，并新建 [test_build_pipeline.py](/Users/itboybob/Project/fire/tests/integration/pipeline/test_build_pipeline.py) 作为任务 11 的小型离线流水线集成测试。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境内已有的 `fastapi`、`jinja2`、`pytest`、`httpx`、`numpy` 与 `faiss-cpu`；本轮红测未引入 `playwright` 等新依赖。
- 验证结果：
  - 红测命令：`conda run -n fire python -m pytest tests/integration/pipeline/test_build_pipeline.py tests/integration/api/test_chat_api.py -q`
  - 结果为 `2 failed, 4 passed in 0.38s`
  - 失败 1：`GET /` 当前返回 `404`，说明任务 11 所需的根页面路由、模板渲染与静态资源挂载尚未实现
  - 失败 2：小型流水线测试中，`scripts/build_corpus.py` 虽成功写出 `data/structured/*.json` 与 `data/chunks/*.jsonl` 路径，但 `build_index.py` 随后报 `.../data/chunks 下没有可建索引的 chunk`；这表明现有 `tests/fixtures/raw/*` 不能稳定产出可建索引的 chunk，更像“文件发现夹具”，不适合作为任务 11 的端到端离线夹具
- 当前阻塞点：页面实现本身没有新的设计阻塞，但离线集成测试夹具需要先调整为“能真实产出条文 chunk 的最小原始文档样本”；否则会把夹具能力不足误判成流水线实现缺陷。
- 补充验证：在同一条红测命令下将离线夹具改为运行时生成的最小 `.docx` 法规样本后，`tests/integration/pipeline/test_build_pipeline.py` 已通过，整体结果收敛为 `1 failed, 5 passed in 0.46s`；当前唯一失败只剩 `GET /` 返回 `404`，说明任务 11 现在可以进入页面实现阶段。
- 绿测确认：在补齐 [main.py](/Users/itboybob/Project/fire/app/main.py)、[index.html](/Users/itboybob/Project/fire/app/templates/index.html)、[app.css](/Users/itboybob/Project/fire/app/static/app.css) 与 [app.js](/Users/itboybob/Project/fire/app/static/app.js) 后，再次执行 `conda run -n fire python -m pytest tests/integration/pipeline/test_build_pipeline.py tests/integration/api/test_chat_api.py -q`，结果为 `6 passed in 0.47s`
- 全量回归：`conda run -n fire python -m pytest -q` 结果为 `49 passed, 1 xfailed in 0.53s`；唯一 `xfailed` 项仍为 [test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py) 中已登记的历史技术债测试，不属于任务 11 回归
- 真实验证补记：曾尝试用一条 `conda run -n fire python - <<'PY' ...` 命令合并执行“真实建库 + 页面冒烟”，该命令退出码为 `0`，但当前终端包装层未回传脚本 stdout；为避免把不可审计结果误记为已验证，后续改为分步重跑真实验证命令并分别落盘
- 真实语料建库入口复验：`conda run -n fire python scripts/build_corpus.py` 已再次成功执行，当前 `6` 份真实法规均完成 `structured -> chunks` 重建，说明任务 11 的页面接入未破坏离线入口脚本
- 真实索引入口复验：`conda run -n fire python scripts/build_index.py` 已再次成功执行，当前真实索引摘要为 `chunks=328`、`keyword_db=data/index/retrieval.db`、`vector_index=data/index/faiss.index`、`vector_map=data/index/vector_map.json`；执行中仅出现 Hugging Face Hub 未鉴权提示和 `BertModel` 的 `position_ids` `UNEXPECTED` 加载说明，均未阻断索引构建
- 页面冒烟补记：曾尝试用一条内联 `python -c` 命令验证 `/`、`/health` 与 `/static/*`，但该命令因 shell 对中文字符串和引号的转义失败而报 `SyntaxError: '(' was never closed`；该失败属于验证命令书写错误，不代表应用本身存在回归，因此已计划立即改用更稳妥的写法重跑
- 页面冒烟复验：改用 ASCII 转义后的 `python -c` 命令重新验证真实应用工厂，结果为 `root 200`、`health 200`、`css 200`、`js 200`、`title True`、`form True`，说明根页面、静态资源与健康检查均已在真实应用实例下可用
- 运行就绪度混合检查补记：曾尝试在同一条 `python -c` 命令里同时做“依赖导入检查 + 根页面检查 + 真实 `/api/chat` 请求”；该命令本身存在两个缺陷：一是版本打印代码误写成 `getattr(module, __version__, n/a)`，导致依赖检查日志失真；二是它在真实聊天前显式预导入了 `faiss` / `sentence_transformers`，随后又在同一进程触发 `/api/chat`，结果复现出已知的 `Segmentation fault: 11`。由于这条命令破坏了正常应用路径中的初始化顺序，因此不能直接据此判定“前端真实聊天一定不可用”，后续需拆成独立命令重跑
- 依赖元数据复验：改用 `importlib.metadata.version()` 只读核对 `fire` 环境已安装版本，当前 `fastapi 0.135.2`、`jinja2 3.1.6`、`openai 2.30.0`、`uvicorn 0.42.0`、`httpx 0.28.1`、`pytest 9.0.2`、`numpy 2.4.3`、`faiss-cpu 1.13.2`、`sentence-transformers 5.3.0` 均已安装，未发现缺包
- 真实聊天复验：在不额外预导入 `faiss`/`sentence_transformers` 的情况下，直接通过 `TestClient(create_app())` 发送一次真实 `/api/chat` 请求，结果为 `status 200`、`content_type application/json`，返回字段完整包含 `citations / conclusion / evidence / scope / uncertainty`；本次真实回答摘要为“根据《中华人民共和国消防法》第十六条，单位的主要负责人是本单位的消防安全责任人”，`citation_count=1`、`evidence_count=3`。这说明当前真实聊天链路在正常应用初始化顺序下可以成功触发
- 前端手工测试前置条件复验：在不触发真实聊天的轻量检查中，`Settings()` 显示 `chat_api_key_set=True`、`chat_base_url_set=True`、`chat_model_set=True`、`embedding_model_name=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，同时渲染后的根页面满足 `root_has_endpoint=True`，说明浏览器端已经拿到 `/api/chat` 请求入口，当前具备打开网页做手工真实聊天测试的前提
- 当前阻塞点：主线 `Task 11` 已完成，当前无新的主线技术阻塞。剩余非阻塞风险是：网页界面仍只是验证面板，真实聊天联调仍取决于本机 `.env` 中的外部模型配置和可接受的调用成本。

### 2026-03-29 完成原主线 Task 10 聊天 API 暴露

- 执行内容：按 `executing-plans` 与 TDD 执行 [原主线 Task 10](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L658)。先读取文档索引、状态、实施计划与设计文档，再核对 FastAPI 官方文档中 `APIRouter`、`response_model`、依赖覆盖测试和 `HTTPException` 的当前推荐用法；随后新增 [chat.py](/Users/itboybob/Project/fire/app/api/chat.py) 与 [test_chat_api.py](/Users/itboybob/Project/fire/tests/integration/api/test_chat_api.py)，把 `/api/chat` 接入真实“查询规范化 -> 混合检索 -> 答案生成”链路，并通过依赖注入把“索引未就绪 / 模型调用失败 / 证据不足”拆成不同返回路径。执行中顺手修复了两个真实运行问题：一是 [settings.py](/Users/itboybob/Project/fire/app/core/settings.py) 对空 `EMBEDDING_MAX_SEQ_LENGTH` 的解析缺陷；二是当前 `fire` 环境下“先加载 FAISS、后首次触发 `sentence-transformers` 编码”会导致原生段错误，因此在 [chat.py](/Users/itboybob/Project/fire/app/api/chat.py#L100) 前置加入 embedder 预热，并补上 [test_chat_dependencies.py](/Users/itboybob/Project/fire/tests/unit/api/test_chat_dependencies.py) 锁住初始化顺序。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境内已安装的 `fastapi`、`openai`、`numpy`、`faiss-cpu`、`sentence-transformers` 与现有真实索引产物。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q` 初次结果为 `1 error`，失败原因是 `app.api.chat` 尚不存在
  - Task 10 集成测试：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q` 最终结果为 `4 passed in 0.33s`
  - 受影响回归：`conda run -n fire python -m pytest tests/unit/api/test_chat_dependencies.py tests/unit/services/test_vector_index.py tests/unit/core/test_settings.py tests/unit/services/test_answer_service.py tests/integration/api/test_health_api.py tests/integration/api/test_chat_api.py -q` 结果为 `18 passed in 0.36s`
  - 真实上游验证：使用真实 [retrieval.db](/Users/itboybob/Project/fire/data/index/retrieval.db)、[faiss.index](/Users/itboybob/Project/fire/data/index/faiss.index) 与 [vector_map.json](/Users/itboybob/Project/fire/data/index/vector_map.json)，通过 `TestClient(create_app())` 调用 `/api/chat`，仅将聊天客户端替换为测试桩以避免外部模型额度消耗；最终返回：
    - HTTP `200`
    - `conclusion = 已命中真实索引并返回证据。`
    - `citations = ['《中华人民共和国消防法》第二条']`
    - `evidence_count = 1`
    - `first_chunk = xiaofangfa_2019#article-2`
  - 真实故障复现与修复验证：在 `fire` 环境中已独立复现“`FaissVectorStore.load('data/index/faiss.index')` 先执行，再首次 `embedder.encode_queries(...)` 会触发 `Segmentation fault: 11`”；加入预热后，再执行“预热 embedder -> 加载 FAISS -> 再次编码 -> 检索”链路可稳定返回 `searched 3 55`
- 当前阻塞点：`Task 10` 已完成，当前无新的技术阻塞；若继续主线，应进入 `Task 11` 的极薄网页聊天界面与端到端文档。当前非阻塞风险是：这次真实 API 冒烟为了避免隐式外部花费，只验证了真实检索链路与 API 结构，没有直接消耗真实聊天提供商额度；若后续要做最终联调，仍建议用户在确认可接受外部调用成本后再执行一次真实 `/api/chat` 全链路请求。

### 2026-03-29 创建本机 `.env` 并补齐当前运行依赖配置

- 执行内容：根据用户授权，新建未纳入版本控制的 `.env`，将当前选定的聊天提供商 `iFlow`、模型 `qwen3-32b`、聊天超时/温度参数，以及离线索引已验证通过的本地嵌入模型 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 一并写入本机配置，避免后续在线链路联调时只完成聊天配置而遗漏嵌入配置。
- 执行环境：本次将使用 `fire` 环境做最小加载验证。
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境内已安装的 `openai`、`sentence-transformers` 等既有依赖。
- 验证结果：
  - [`.env`](/Users/itboybob/Project/fire/.env) 已创建，且仍被 [`.gitignore`](/Users/itboybob/Project/fire/.gitignore#L7) 忽略
  - `fire` 环境最小加载验证已通过：`Settings()` 可正常读取 `CHAT_BASE_URL=https://apis.iflow.cn/v1`、`CHAT_MODEL=qwen3-32b`、真实 `CHAT_API_KEY` 与 `EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 当前阻塞点：功能层无新增阻塞；若继续推进 Task 10，当前本机配置已具备接入真实聊天客户端的基础条件。非阻塞风险仍然是：此前暴露过的真实 `API Key` 最好尽快轮换。

### 2026-03-29 移除受版本管理文件中的真实聊天密钥

- 执行内容：根据用户确认，对 [settings.py](/Users/itboybob/Project/fire/app/core/settings.py) 与 [.env.example](/Users/itboybob/Project/fire/.env.example) 做配置安全修正，移除真实聊天密钥，恢复源码默认占位值，并在示例文件中仅保留当前项目选定的提供商 `iFlow` 与模型 `qwen3-32b` 作为非敏感配置说明。
- 执行环境：本次包含文档与配置文件修改；后续验证在 `fire` 环境执行。
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境。
- 验证结果：
  - [settings.py](/Users/itboybob/Project/fire/app/core/settings.py#L12) 当前不再硬编码真实 `API Key`
  - [.env.example](/Users/itboybob/Project/fire/.env.example#L1) 当前仅保留占位 `CHAT_API_KEY=replace-me`，并显式注明真实密钥只应写入本机 `.env`
  - 最小回归：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/unit/services/test_answer_service.py -q` 结果为 `6 passed in 0.52s`
- 当前阻塞点：功能层无新增阻塞；后续一旦进入真实模型联调，仍需要用户在本机 `.env` 中提供真实 `CHAT_API_KEY`。由于真实密钥已经在此前对话和本地受版本管理文件中出现过，安全上更稳妥的做法是尽快在提供商后台执行一次密钥轮换。

### 2026-03-29 完成原主线 Task 9 答案组装与 OpenAI 兼容聊天客户端

- 执行内容：按 `executing-plans` 与 TDD 执行 [原主线 Task 9](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L590)。先读取文档索引、状态、实施计划与设计文档，再核对 OpenAI 官方文档中“Structured Outputs 优先于旧 JSON mode”的当前建议，以及 Chat Completions 在 OpenAI 兼容场景下通过 `base_url` 复用 SDK 的接法；随后在本地分支 `task9-answer-chat` 上补齐 [app/schemas/](/Users/itboybob/Project/fire/app/schemas)、[chat_client.py](/Users/itboybob/Project/fire/app/services/chat_client.py)、[answer_service.py](/Users/itboybob/Project/fire/app/services/answer_service.py) 与 [test_answer_service.py](/Users/itboybob/Project/fire/tests/unit/services/test_answer_service.py)，实现结构化输出包装、答案 prompt 组装、引文候选集约束、无证据拒答与引文落地校验。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境内已安装的 `openai 2.30.0`；本任务只新增配置项 `CHAT_TIMEOUT_SECONDS` 与 `CHAT_TEMPERATURE`，未触发新的安装需求。
- 验证结果：
  - 依赖确认：`conda run -n fire python -c "import openai; print(openai.__version__)"` 结果为 `2.30.0`
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py -q` 初次结果为 `1 error`，失败原因是 `app.services.answer_service` 尚不存在
  - Task 9 单测：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py -q` 最终结果为 `5 passed in 0.22s`
  - 受影响回归：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/unit/services/test_answer_service.py -q` 结果为 `6 passed in 0.22s`
  - 真实上游验证：直接读取真实 [xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl) 中 `xiaofangfa_2019#article-2` 作为证据，使用测试桩客户端调用 `build_answer()`：
    - 有证据场景稳定返回引文 `《中华人民共和国消防法》第二条`
    - 空证据场景稳定返回 `证据不足，无法可靠回答。`
    - 说明答案层在真实 chunk 产物上已能同时守住“引文必须来自证据集”和“无证据直接拒答”两条门禁
  - 环境合规说明：本次实现与验收结论均来自 `fire` 环境；执行前审查阶段曾误用一次非 `fire` 的只读 Python 探针检查目录存在性，该探针不计入任何验证结论
- 当前阻塞点：`Task 9` 已完成，当前无新的技术阻塞；若继续主线，应进入 `Task 10` 的聊天 API 暴露。当前非阻塞风险是：部分第三方“OpenAI 兼容”后端可能只支持旧 `json_object` 而不支持 `json_schema`，若后续联调遇到兼容性问题，应在客户端增加受控回退策略，而不是放松引文校验。

### 2026-03-29 完成原主线 Task 8 查询规范化与混合检索

- 执行内容：按 `executing-plans` 与 TDD 执行 [原主线 Task 8](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L527)。先读取文档索引、状态、实施计划与设计文档，再核对最新官方文档中 `SQLite FTS5 bm25` 的排序语义、`SentenceTransformer.encode_query()/encode_document()` 的检索建议以及 `FAISS` 对内积检索/归一化向量的要求；随后新增 [query_normalizer.py](/Users/itboybob/Project/fire/app/services/query_normalizer.py) 与 [retriever.py](/Users/itboybob/Project/fire/app/services/retriever.py)，补齐 [test_query_normalizer.py](/Users/itboybob/Project/fire/tests/unit/services/test_query_normalizer.py) 与 [test_retriever.py](/Users/itboybob/Project/fire/tests/unit/services/test_retriever.py)，实现别名规范化、地域/条号/日期线索提取、canonical title 收敛、关键词/向量结果融合去重与来源保留。
- 执行环境：`fire`
- 依赖情况：无需新增依赖，沿用当前 `fire` 环境内已安装的 `numpy`、`faiss-cpu`、`sentence-transformers` 与现有真实索引产物。
- 验证结果：
  - 红测确认：`conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_retriever.py -q` 初次结果为 `2 errors`，失败原因是 `app.services.query_normalizer` 尚不存在。
  - Task 8 单测：`conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_retriever.py -q` 最终结果为 `5 passed in 0.01s`
  - 受影响回归：`conda run -n fire python -m pytest tests/unit/services/test_keyword_index.py tests/unit/services/test_vector_index.py tests/unit/services/test_query_normalizer.py tests/unit/services/test_retriever.py -q` 结果为 `11 passed in 0.08s`
  - 真实上游检索验证：在真实 [data/index/retrieval.db](/Users/itboybob/Project/fire/data/index/retrieval.db)、[data/index/faiss.index](/Users/itboybob/Project/fire/data/index/faiss.index) 与 [data/index/vector_map.json](/Users/itboybob/Project/fire/data/index/vector_map.json) 上，以真实嵌入模型 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 构造 `Retriever.from_disk()` 执行检索冒烟：
    - `消防法第二条责任制` 命中 `xiaofangfa_2019#article-2`，路径为 `中华人民共和国消防法 > 第一章 总则 > 第二条`
    - `河北消防条例第28条自2010年7月1日起施行吗` 命中 `hebei_xiaofang_tiaoli#article-28`，路径为 `河北省消防条例 > 第三章 消防设施 > 第二十八条`
    - `谁对本单位消防安全全面负责` 返回 `vector` 来源结果，证明自然问句场景下向量支路已实际参与检索
  - 稳定性复核：显式设置 `OMP_NUM_THREADS=1` 与 `TOKENIZERS_PARALLELISM=false` 后，在同一进程连续执行两条真实查询，均稳定返回结果，未复现早期一次性的 `Segmentation fault 11`
  - 环境合规说明：本次实现与验收所引用的测试/检索结果均来自 `fire` 环境；执行早期曾误用一次非 `fire` 的只读 Python 探针查看数据字段，该探针不计入任何验证结论
- 当前阻塞点：`Task 8` 已完成，当前无新的技术阻塞；若继续主线，应进入 `Task 9` 的答案组装与 OpenAI 兼容聊天客户端实现。当前非阻塞风险是：自然语言问句的融合排序仍偏保守，后续可能需要结合答案层和更多真实问句继续调权。

### 2026-03-29 完成 Task 7 真实依赖安装与环境合规验证

- 执行内容：在获得用户明确许可后，于 `fire` 环境安装 `numpy`、`faiss-cpu`、`sentence-transformers`，并补齐其传递依赖；随后验证导入版本、复跑 `Task 7` 相关单测与受影响回归，再使用真实嵌入模型 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` 执行 [build_index.py](/Users/itboybob/Project/fire/scripts/build_index.py) 完成真实索引构建；最后在真实生成的 [data/index/retrieval.db](/Users/itboybob/Project/fire/data/index/retrieval.db) 上补做一次关键词回查。
- 执行环境：`fire`
- 验证结果：
  - 安装命令：`conda run -n fire python -m pip install numpy faiss-cpu sentence-transformers`
  - 依赖版本验证：`numpy=2.4.3`、`faiss=1.13.2`、`sentence_transformers=5.3.0`、`torch=2.11.0`
  - `Task 7` 单测：`conda run -n fire python -m pytest tests/unit/services/test_vector_index.py -q` 结果为 `4 passed in 0.08s`
  - 受影响回归：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/unit/services/test_keyword_index.py tests/unit/services/test_vector_index.py -q` 结果为 `7 passed in 0.09s`
  - 全量回归：`conda run -n fire python -m pytest -q` 结果为 `30 passed, 1 xfailed in 0.37s`
  - 真实入口验证：`EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 conda run --no-capture-output -n fire python scripts/build_index.py` 成功输出：
    - `chunks=328`
    - `keyword_db=data/index/retrieval.db`
    - `vector_index=data/index/faiss.index`
    - `vector_map=data/index/vector_map.json`
  - 文件落盘验证：`data/index/` 当前包含真实 `retrieval.db`、`faiss.index`、`vector_map.json`
  - 回查验证：在真实 `data/index/retrieval.db` 上查询 `消防设施`，前 `3` 个命中中首项为 `hebei_xiaofang_tiaoli#article-27`
  - [pyproject.toml](/Users/itboybob/Project/fire/pyproject.toml) 已补入 `numpy`、`faiss-cpu`、`sentence-transformers` 运行时依赖，避免环境只在本机偶然可复现
- 当前阻塞点：原主线 `Task 7` 已完成。当前已知技术债不再阻塞主线放行；若继续推进，应进入 `Task 8` 的查询规范化与混合检索。

### 2026-03-29 为枚举级切块旧红测建立技术债记录并解除主线放行阻塞

- 执行内容：按用户要求新增 [技术债记录](/Users/itboybob/Project/fire/docs/debts/2026-03-29-chunk-builder-enum-red-test-debt.md)，系统化记录 `tests/unit/services/test_chunk_builder.py::test_build_chunks_matches_real_structured_fixture` 对应的历史债务、影响范围、解除条件与临时放行策略；随后更新 [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md)，并在 [test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py#L115) 中为该测试补上显式 `xfail` 标记，避免后续 `pytest -q` 把这条已知技术债继续误判为当前主线新回归。
- 执行环境：`fire`
- 验证结果：
  - 技术债文档已落盘，路径为 [docs/debts/2026-03-29-chunk-builder-enum-red-test-debt.md](/Users/itboybob/Project/fire/docs/debts/2026-03-29-chunk-builder-enum-red-test-debt.md)
  - [文档索引](/Users/itboybob/Project/fire/docs/文档索引.md#L19) 已新增“技术债记录”层，明确其用途与读取时机
  - [test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py#L115) 已将该测试标记为 `xfail`，原因中回链技术债文档
  - `conda run -n fire python -m pytest -q` 结果为 `30 passed, 1 xfailed in 0.33s`；说明当前主线的全量回归已经不再被这条已知技术债直接阻塞
  - 结合 [Task 7 完成度复核](#2026-03-29-原主线-task-7-完成度复核) 中的代码、测试和真实上游验证结果，可判定 `Task 7` 在“不安装新依赖”的边界内已经完成；剩余仅是等待用户确认依赖安装后的真实后端环境验证
- 当前阻塞点：当前主线放行已不再被该技术债卡住；若继续推进主线，下一真实阻塞只剩 `Task 7` 的向量依赖安装确认。技术债本身仍保留，未来若要解除，必须按其记录中的两条合法路径之一处理。

### 2026-03-29 原主线 Task 7 完成度复核

- 执行内容：按用户要求忽略 [test_build_chunks_matches_real_structured_fixture](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py#L113) 这条旧红测，仅以 [原主线实施计划 Task 7](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L457) 为准重新逐项核对当前实现，并在 `fire` 环境复跑 Task 7 相关单测、受影响回归、真实上游建索引验证和依赖探测。
- 执行环境：`fire`
- 验证结果：
  - 计划文件列出的 `5` 个目标文件均已落地：
    - [embedder.py](/Users/itboybob/Project/fire/app/services/embedder.py)
    - [vector_store.py](/Users/itboybob/Project/fire/app/services/vector_store.py)
    - [vector_index.py](/Users/itboybob/Project/fire/app/services/vector_index.py)
    - [test_vector_index.py](/Users/itboybob/Project/fire/tests/unit/services/test_vector_index.py)
    - [build_index.py](/Users/itboybob/Project/fire/scripts/build_index.py)
  - 计划步骤对照：
    - `FakeEmbedder` 场景已覆盖：`build_vector_index()` 与 `build_indexes()` 均可在无真实向量依赖的前提下通过测试桩完成验证
    - 窄接口 `VectorStore` 已定义于 [vector_store.py](/Users/itboybob/Project/fire/app/services/vector_store.py#L12)
    - 默认 FAISS 实现 `FaissVectorStore` 已存在，并在缺依赖时抛出明确错误，而不是静默退化
    - `faiss.index` 与 `vector_map.json` 的持久化逻辑已存在于 [vector_index.py](/Users/itboybob/Project/fire/app/services/vector_index.py#L45)
    - [build_index.py](/Users/itboybob/Project/fire/scripts/build_index.py#L27) 已可在一次调用中同时构建关键词索引与向量索引
  - Task 7 单测：`conda run -n fire python -m pytest tests/unit/services/test_vector_index.py -q` 结果为 `4 passed in 0.10s`
  - 受影响回归：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/unit/services/test_keyword_index.py tests/unit/services/test_vector_index.py -q` 结果为 `7 passed in 0.08s`
  - 真实上游验证：基于仓库现有 `data/chunks/*.jsonl` 共 `328` 条 chunk，通过假嵌入器与临时向量存储执行 `build_indexes()`，成功产出 `faiss.index`、`retrieval.db`、`vector_map.json`，并确认查询 `消防设施` 的首个关键词命中为 `hebei_xiaofang_tiaoli#article-27`
  - 依赖探测：`numpy=False`、`faiss=False`、`sentence_transformers=False`
  - 复核结论：当前未发现任何“不依赖 `numpy/faiss-cpu/sentence-transformers` 仍可继续补完”的 Task 7 缺口
- 当前阻塞点：若要把 Task 7 从“代码与假后端验证完成”提升到“真实 FAISS + 真实本地嵌入模型已完成环境合规验证”，仍必须先获批安装 `numpy`、`faiss-cpu`、`sentence-transformers`；在此之前，Task 7 只能视为“非依赖部分已完成，真实依赖验证待解锁”。

### 2026-03-29 复核 `test_build_chunks_matches_real_structured_fixture` 失败根因

- 执行内容：按用户要求调用 `@code-reviewer` 做只读审查，同时在 `fire` 环境本地复核 [test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py)、[chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py)、真实夹具 [xiaofangfa_article_62_structured.json](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_structured.json)、期望夹具 [xiaofangfa_article_62_expected.jsonl](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl)，并重跑目标失败测试确认现状。
- 执行环境：`fire`
- 验证结果：
  - `conda run -n fire python -m pytest tests/unit/services/test_chunk_builder.py::test_build_chunks_matches_real_structured_fixture -q -vv` 结果仍为稳定失败；失败差异集中在：当前实现输出单个 article-level chunk，而期望夹具要求 `5` 个枚举级 chunk
  - 真实结构化夹具中，第六十二条当前总长度为 `165`，分段长度为 `[33, 44, 32, 9, 18, 24]`，不满足“某段仍超过 `300` 且带枚举标记才触发二级切块”的已接受规则
  - [chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py#L82) 当前只在条文整体超限时才继续做按段切块，并未实现“未超限也按枚举拆分”；这与当前重构 ADR 中的收紧口径一致，不属于 `Task 7` 引入的新回归
  - `@code-reviewer` 与主代理结论一致：根因层级是“旧红测/旧期望夹具仍在”，背后是已记录的计划矛盾和历史债务；该问题不会阻塞当前 `Task 7`、`build_index`、`Task 8`、`Task 9` 的功能推进，但会持续污染“全量测试是否全绿”的门禁判断
- 当前阻塞点：如果继续沿当前主线推进，功能上可以前进，但全量测试门禁会一直被这条旧红测拦住；若要彻底消除该失败，只能二选一：要么恢复并完成那条重构线，要么重新发起设计变更，正式接受“未超限枚举条文也拆分”的新规则。

### 2026-03-29 完成原主线 Task 7 接口落地与假后端验证

- 执行内容：按 `executing-plans` 与 TDD 执行 [原主线 Task 7](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L457)。先读取项目索引、状态和实施计划，再核对设计文档中对 `Embedder` / `RetrieverStore` 的稳定接口约束；随后查询最新官方文档，确认 `SentenceTransformer.encode_document()` / `encode_query()` 的调用方式，以及 FAISS `IndexFlat` / `write_index()` / `read_index()` 的持久化能力后，新增 [embedder.py](/Users/itboybob/Project/fire/app/services/embedder.py)、[vector_store.py](/Users/itboybob/Project/fire/app/services/vector_store.py)、[vector_index.py](/Users/itboybob/Project/fire/app/services/vector_index.py)、[build_index.py](/Users/itboybob/Project/fire/scripts/build_index.py) 与 [test_vector_index.py](/Users/itboybob/Project/fire/tests/unit/services/test_vector_index.py)，并同步扩展 [settings.py](/Users/itboybob/Project/fire/app/core/settings.py) 与 [.env.example](/Users/itboybob/Project/fire/.env.example) 的索引/嵌入配置。
- 执行环境：`fire`
- 验证结果：
  - 官方文档核对完成：`SentenceTransformer` 当前官方文档明确提供 `encode_document()` / `encode_query()`，并说明在 `normalize_embeddings=True` 时可改用点积；FAISS 官方教程与 Wiki 明确展示了 `index.add()`、`index.search()`、`write_index()`、`read_index()` 的用法
  - 环境探测结果：在 `fire` 环境执行模块探测后，`numpy=False`、`faiss=False`、`sentence_transformers=False`；因此本次没有擅自安装依赖，而是把真实后端实现收敛为显式可选依赖边界
  - `Task 7` 单测：`conda run -n fire python -m pytest tests/unit/services/test_vector_index.py -q` 结果为 `4 passed in 0.06s`
  - 受影响回归：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/unit/services/test_keyword_index.py tests/unit/services/test_vector_index.py -q` 结果为 `7 passed in 0.06s`
  - 真实上游产物验证：在 `fire` 环境读取仓库真实 `data/chunks/*.jsonl` 共 `328` 条 chunk，注入 `FakeEmbedder` 与临时 `TempVectorStore` 执行一次 `build_indexes()`，成功产出 `faiss.index`、`retrieval.db`、`vector_map.json` 三个文件；随后用生成的关键词库查询 `消防设施`，首个命中为 `hebei_xiaofang_tiaoli#article-27`
  - 全量测试探测：`conda run -n fire python -m pytest -q` 当前结果为 `1 failed, 30 passed in 0.24s`；唯一失败为 [test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py) 中的 `test_build_chunks_matches_real_structured_fixture`，失败点仍是 `第六十二条` 枚举级 chunk 夹具与当前旧切块实现不一致，这与本次 `Task 7` 改动无直接耦合
- 当前阻塞点：若要继续把 `Task 7` 从“接口实现 + 假后端验证”推进到“真实 FAISS / sentence-transformers 环境合规验证”，必须先向用户显式报备并获批安装 `numpy`、`faiss-cpu`、`sentence-transformers`；此外，仓库当前仍存在一个与 `Task 7` 无关的既有全量测试失败，不能把现在误记为全仓全绿。

### 2026-03-29 收紧“自动安装依赖”规则并新增计划撰写约束

- 执行内容：按用户要求调用 `@doc-updater` 收紧仓库级依赖安装规则，并补充一条新的计划撰写规则；随后由主代理复核并按用户最终口径调整 [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md) 与 [原主线实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md)。
- 执行环境：本次为文档更新与主代理复核；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：
  - [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md#L18) 中的依赖安装规则已改为：若实施计划或实际执行表明当前任务依赖尚未安装，必须先显式向用户请求并报备待安装依赖清单；仅在用户确认后，才可在 `fire` 环境自动安装
  - [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md#L22) 已新增 `计划撰写规则`：撰写任何类型的执行计划时，都必须显式说明本 Phase / Task 是否需要安装依赖；若需要，还必须写明依赖清单与安装环境
  - [原主线实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L19) 已同步改为“先向用户报备依赖清单，再安装”的表述，并新增“未单独写执行前依赖提示时，默认表示无需新增依赖，沿用当前 `fire` 环境”的解释
- 当前阻塞点：无新的技术阻塞；后续若进入需要新增依赖的任务，必须先向用户显式报备待安装依赖清单，再执行安装。

### 2026-03-29 补齐原主线实施计划中的依赖安装说明

- 执行内容：按用户要求审查 [原主线实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md) 中从 `Task 6` 往后的依赖安装说明，并核对当前 [pyproject.toml](/Users/itboybob/Project/fire/pyproject.toml) 与 `fire` 环境现状；随后补充 [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md) 与实施计划，明确“执行过程中自动安装依赖”的仓库级规则，以及 `Task 7/9/11` 的依赖边界。
- 执行环境：`fire`
- 验证结果：
  - 当前 [pyproject.toml](/Users/itboybob/Project/fire/pyproject.toml) 已声明 `fastapi`、`jinja2`、`openai`、`pydantic-settings`、`uvicorn`、`pytest`、`httpx`，但未显式覆盖 `Task 7` 需要的向量检索依赖
  - 在 `fire` 环境中执行模块探测后，`faiss`、`numpy`、`playwright`、`sentence_transformers` 当前均未安装
  - [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md#L18) 已新增仓库级规则：若实施计划或实际执行表明当前任务依赖尚未安装，代理应在继续前主动将其安装到 `fire` 环境，并在 `docs/status.md` 记录安装内容、安装时机与验证结果
  - [原主线实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L19) 已新增总则：执行中若发现缺少依赖，应先安装到 `fire` 环境再继续
  - [Task 7](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L465) 已补充执行前依赖提示：接入真实向量检索前至少需要 `numpy`、`faiss-cpu`，若采用 `sentence-transformers` 方案还需安装 `sentence-transformers`
  - [Task 9](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L591) 已补充 `openai` 兼容客户端的依赖说明
  - [Task 11](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L716) 已补充“默认不新增依赖；若升级为真实浏览器自动化，再安装 `playwright` 等依赖”的说明
- 当前阻塞点：当前没有新的技术阻塞；后续进入 `Task 7` 时，应按新规则先自动安装缺失依赖，再继续实现。

### 2026-03-29 将“真实上游产物验证”上升为仓库级测试规则

- 执行内容：按用户要求调用 `@Curie` 更新 [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md)，在仓库级 `执行说明` 中补充一条新的测试验证规则，要求以后新增或修改测试时，除运行对应的单元/预编写测试外，还必须基于真实上游产物再做一轮真实验证。
- 执行环境：本次为文档更新与主代理复核；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：
  - [AGENTS.md](/Users/itboybob/Project/fire/AGENTS.md#L19) 已新增规则：`凡是新增或修改测试，必须先运行对应的单元/预编写测试，再基于真实上游产物（如 data/normalized、data/structured、data/chunks 或真实源文档）补做一轮真实验证。`
  - 主代理已复核 `git diff`，确认本次只修改 `AGENTS.md`，没有扩写其他制度或改动代码
- 当前阻塞点：无新的技术阻塞；该规则会在后续任务中生效，当前主线仍可继续推进到 `Task 7`。

### 2026-03-29 恢复并完成原主线 Task 6

- 执行内容：根据用户“暂时搁置重构计划，重新回到原执行计划”的决定，先复核当前 `data/` 三层产物是否足以支撑恢复原主线 [Task 6](/Users/itboybob/Project/fire/docs/plans/2026-03-28-fire-law-rag-implementation.md#L395)；确认 `data/normalized`、`data/structured`、`data/chunks` 已无超链接污染后，按 `executing-plans` 执行 `Task 6` 的 TDD：新增 [test_keyword_index.py](/Users/itboybob/Project/fire/tests/unit/services/test_keyword_index.py)，先跑红测，再实现 [keyword_index.py](/Users/itboybob/Project/fire/app/services/keyword_index.py) 与 [build_corpus.py](/Users/itboybob/Project/fire/scripts/build_corpus.py)，随后在 `fire` 环境完成单测、真实语料索引烟雾验证与脚本入口验证。
- 执行环境：`fire`
- 验证结果：
  - 准入判断：当前 `data/normalized`、`data/structured`、`data/chunks` 已显式确认无 `HYPERLINK/http(s):///\l "#"`；`data/chunks/*.jsonl` 当前无空 `path`、空 `text`、重复 `chunk_id`，且 `6` 份 chunk 文件都不再存在长度超过 `300` 的块
  - 红测成立：`conda run -n fire python -m pytest tests/unit/services/test_keyword_index.py -q` 初次结果为 `ModuleNotFoundError: No module named 'app.services.keyword_index'`
  - `Task 6` 绿测：补齐最小实现后，`conda run -n fire python -m pytest tests/unit/services/test_keyword_index.py -q` 结果为 `2 passed in 0.03s`
  - 真实索引烟雾验证：基于当前 `data/chunks/*.jsonl` 共 `328` 条 chunk 构建 [retrieval.db](/Users/itboybob/Project/fire/data/retrieval.db)，库中 `SELECT count(*) FROM chunks` 返回 `328`；查询 `消防设施` 的前 `3` 个命中为：
    - `hebei_xiaofang_tiaoli#article-27`
    - `hebei_xiaofang_tiaoli#article-29`
    - `hebei_xiaofang_tiaoli#article-28`
  - 脚本入口验证：`conda run -n fire python scripts/build_corpus.py` 可直接执行，成功重写 `6` 份 `data/structured/*.json` 与 `data/chunks/*.jsonl`
- 当前阻塞点：原主线 `Task 6` 已完成，当前无新的 Task 6 级阻塞；若继续主线，应进入 `Task 7`。仍保留的已知债务是枚举条文引用粒度偏粗，但该风险不再阻塞当前关键词索引构建。

### 2026-03-29 复核并重建 `xiaofangfa_2019` chunk 产物以清除残留超链接污染

- 执行内容：按用户要求先在 `fire` conda 环境执行 `rg -n 'HYPERLINK|https?://|\\l "#"' data/chunks -S`，确认 `data/chunks/` 下的超链接污染是否只存在于 [xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl)；结论成立后，再基于新的 [xiaofangfa_2019.json](/Users/itboybob/Project/fire/data/structured/xiaofangfa_2019.json) 使用现有 [chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py) 的旧分块逻辑重建 `data/chunks/xiaofangfa_2019.jsonl`。
- 执行环境：`fire`
- 验证结果：
  - 污染范围查证成立：重建前 `rg -n 'HYPERLINK|https?://|\\l "#"' data/chunks -S` 仅命中 [xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl) 第 `66`、`70` 行，对应 `第六十二条` 与 `第六十五条`
  - 重建命令成功输出 `data/chunks/xiaofangfa_2019.jsonl`
  - 重建后再次执行 `rg -n 'HYPERLINK|https?://|\\l "#"' data/chunks -S` 无命中，说明 `data/chunks/` 目录当前已无超链接字段码残留
  - 抽样复核显示：
    - [xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl) 中 `第六十二条` 已变为单块 `xiaofangfa_2019#article-62`，文本长度 `165`，且不再包含超链接污染
    - `第六十五条` 仍按旧逻辑分为 `2` 块，但 `part-1` 文本已更新为 `依照《中华人民共和国产品质量法》的规定从重处罚`
- 当前阻塞点：`data/chunks/` 的已知超链接污染已清除，但“段内二级切块”重构本身仍处于搁置状态；是否恢复原主线 `Task 6`，仍需基于当前数据质量与门禁口径另行判断。

### 2026-03-29 复核原实施计划后确认不能直接执行 Task 5

- 执行内容：按用户要求重新检查 [重构实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md)、[项目状态](/Users/itboybob/Project/fire/docs/status.md) 与 [重构 ADR](/Users/itboybob/Project/fire/docs/adr/2026-03-28-normalization-and-chunking-refactor.md)，判断在当前状态下是否可以跳过 `Task 4` 的实际完成，直接执行原计划中的 `Task 5`。
- 执行环境：本次为文档复核；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：
  - [实施计划 Task 5](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md#L202) 的步骤 1 预期“目标测试全部通过，哨兵样本稳定，且变化能够归因到预期阶段”，这隐含前提是 [Task 4](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md#L154) 已经完成并把 `chunk_builder` 回归拉绿
  - [实施计划 Task 4](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md#L190) 明确要求先跑 `tests/unit/services/test_chunk_builder.py -q` 并重建 chunk 哨兵样本；但当前 `Task 4` 的真实样本阻塞仍未解除
  - [ADR](/Users/itboybob/Project/fire/docs/adr/2026-03-28-normalization-and-chunking-refactor.md#L20) 也明确规定本次重构采用顺序执行：先修 `normalizer`，再验证 `structured`，再处理 `chunk_builder`，最后才做分阶段和全量重建
- 当前阻塞点：若现在直接执行原 `Task 5`，会把“尚未完成的 `Task 4`”伪装成“已完成并可归因验证”，导致测试口径和状态记录同时失真。因此当前不能直接执行原计划的 `Task 5`。

### 2026-03-29 按用户要求补充 Task 4 执行识别提示

- 执行内容：根据用户最新要求，停止继续完善文档系统，也不修改 `Task 4` 触发规则或继续寻找新样本；改为由 `@Curie` 只在 [重构设计文档](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor-design.md) 与 [重构实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md) 的 `chunk_builder / 段内二级切块` 相关位置补充执行识别提示，并在主代理侧复核 diff。
- 执行环境：本次为文档修改与只读复核；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：
  - [重构设计文档](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor-design.md#L62) 已新增提示：若某个单段长度超过 `300` 且包含枚举标记，应优先视为需要进入该路径验证的候选样本
  - [重构实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md#L182) 已新增提示：若真实样本先出现“单行长度超过 `300` 且带枚举标记”的情况，应优先检查其在结构化后是否满足触发条件
  - 复核 `git diff` 后确认：本次仅补充执行识别提示，没有改写原有触发条件，也没有继续扩展文档系统
- 当前阻塞点：该提示只提升后续识别效率，不会自动制造新的真实样本。因此 `Task 4` 的核心阻塞仍然存在，当前尚不能据此直接继续实现二级切块逻辑。

### 2026-03-29 Task 4 真实样本复核失败并完成文档系统根因分析

- 执行内容：继续推进 `Task 4` 前，先复核 [重构实施计划](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md)、[重构 ADR](/Users/itboybob/Project/fire/docs/adr/2026-03-28-normalization-and-chunking-refactor.md)、[chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py) 与 [test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py)；随后在 `fire` conda 环境分别扫描 `data/structured/*.json`、`data/normalized/*.txt` 与 `法律文本/*`，查找是否存在“单行/单段超过 `300` 且包含 `（一）（二）` 枚举标记”的真实样本；同时调用 `@architect` 分析“为什么找不到用户明确批准该触发规则的记录”，并审视当前文档系统应如何避免再次出现同类问题。
- 执行环境：`fire`
- 验证结果：
  - `data/structured/*.json` 扫描结果为空：当前 6 份结构化语料中，不存在任何“单段超过 `300` 且包含枚举标记”的条文段落
  - `data/normalized/*.txt` 扫描结果为空：当前 6 份标准化语料中，也不存在任何“单行超过 `300` 且包含枚举标记”的文本行
  - `法律文本/*` 经 `textutil` 转换后的原始文本抽查结果同样为空：当前项目语料源中未发现符合该触发条件的真实段落
  - `@architect` 的结论是：仓库当前更擅长记录“执行到了哪一步”，但没有定义“规则级批准应该落在哪个文档、以什么格式固化、如何跨设计/计划/状态复用”，因此会出现“能找到整篇设计已批准，却找不到具体细则逐条批准证据”的问题
  - `@architect` 建议后续补上：规则状态三分法、`Decision ID`、独立决策台账、`检查点` 与 `批准点` 分离，以及在文档索引中显式加入“去哪里查批准”
- 当前阻塞点：用户此前改选的“方向一：修正真实哨兵样本，保持原触发规则不变”已被当前真实语料再次证伪。若不扩大语料范围或修改任务边界，`Task 4` 无法在现有 6 份法规内继续诚实执行。

### 2026-03-29 检索状态文档并记录 Task 4 决策改选

- 执行内容：检索 [status.md](/Users/itboybob/Project/fire/docs/status.md) 全文，回溯是否存在用户明确批准“只有按段切块后某段仍超过 `300` 且包含枚举标记才触发二级切块”的状态记录；随后根据用户于 `2026-03-29` 的最新决策，更新 [标准化与切块重构 ADR](/Users/itboybob/Project/fire/docs/adr/2026-03-28-normalization-and-chunking-refactor.md)，明确放弃“枚举条文即使未超限也拆分”，改选“修正真实哨兵样本，保持原触发规则不变”。
- 执行环境：本次为文档检索与文档更新；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：
  - `status.md` 中未找到用户对该具体触发条件的明确批准记录
  - 能回溯到的最接近记录是 `2026-03-28 Task 5 段内二级切块需求审计`，其结论是“若引入段内二级切块，应作为通用规则落入 `chunk_builder.py`”，但并未把“仅当超限才触发”写成用户批准语句
  - ADR 已新增 `2026-03-29 决策补充`，正式记录这次改选及其负面影响：一部分未超限但带枚举结构的法条仍不会被拆分，因此后续检索/引用粒度可能仍然偏粗
- 当前阻塞点：需要先修正任务 4 的真实哨兵样本，使其与现有触发规则一致；在此之前，不应继续修改 `chunk_builder.py`。

### 2026-03-29 标准化与切块重构 Task 4 启动审计发现计划矛盾

- 执行内容：准备进入 `Task 4` 前，在 `fire` conda 环境复核 [chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py)、[test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py) 与真实夹具；并通过临时检查确认 [xiaofangfa_article_62_structured.json](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_structured.json) 的第六十二条清洗后正文长度与分段长度。
- 执行环境：`fire`
- 验证结果：发现阻塞性矛盾，而不是代码缺陷：
  - 真实夹具第六十二条当前总长度只有 `165`
  - 分段长度为 `[33, 44, 32, 9, 18, 24]`
  - 因此它既没有整体超过 `300`，也不存在任何单段超过 `300`
  - 这与任务 4 设计中的触发条件“仅当按段切块后某段仍超过 `max_chunk_chars` 且包含枚举标记时，才触发二级切块”直接冲突
  - 但现有 [xiaofangfa_article_62_expected.jsonl](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl) 却要求无条件拆成 `5` 个枚举块
- 当前阻塞点：`Task 4` 目前不能被诚实执行。若继续硬改，只能把实现改成“未超限也按枚举拆”，这会破坏设计中“触发条件保守”的约束。需要先在两条路里选一条：
  - 修正任务 4 的真实哨兵样本，改用清洗后仍真实超限的枚举条文
  - 或者正式修改设计与实施计划，接受“枚举条文即使未超限也拆分”的新规则

### 2026-03-28 标准化与切块重构 Task 3 完成并进入用户检查点

- 执行内容：按实施计划继续执行 `Task 3`。先审计 [structure_parser.py](/Users/itboybob/Project/fire/app/services/structure_parser.py) 与 [test_structure_parser.py](/Users/itboybob/Project/fire/tests/unit/services/test_structure_parser.py) 的现有覆盖，判断“任务 2 清理后的真实消防法片段”尚未被直接固定，因此新增 [xiaofangfa_article_62_clean.txt](/Users/itboybob/Project/fire/tests/fixtures/structured/xiaofangfa_article_62_clean.txt) 与新的 `structure_parser` 哨兵测试；随后在 `fire` conda 环境执行 `conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py -q`；再按计划重建 `data/structured/xiaofangfa_2019.json`，并将重建后的结构化摘要与重建前基线逐项对比。
- 执行环境：`fire`
- 验证结果：通过，结果分为四段：
  - 哨兵回归：新增测试后，`conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py -q` 结果为 `5 passed in 0.02s`
  - 结构化哨兵重建：`conda run -n fire python -c "... parse_legal_document(...); write_structured_document(...)"` 成功输出 `data/structured/xiaofangfa_2019.json`
  - 摘要对比：重建前后 `title=中华人民共和国消防法`、`first_article_no=第一条`、`last_article_no=第七十四条`、`promulgated_on=null`、`effective_on=2009年5月1日`、`article_count=74` 均保持一致
  - 显式污染检查：`rg -n 'HYPERLINK|https?://|\\l "#"' data/structured/xiaofangfa_2019.json -S` 无命中；关键抽样显示 `第六十二条` 与 `第六十五条` 中原先的超链接污染已被清除，但法规可见文本仍完整保留
- 当前阻塞点：无新的技术阻塞；已满足任务 3 的用户自管检查点条件，等待用户先检查结构化哨兵结果，再进入任务 4 的切块逻辑修改。

### 2026-03-28 标准化与切块重构 Task 2 完成并进入用户检查点

- 执行内容：按实施计划继续执行 `Task 2`。先在 `fire` conda 环境执行 `conda run -n fire python -m pytest tests/unit/services/test_normalizer.py::test_clean_text_strips_inline_hyperlink_field_code_from_real_fixture -q` 保持红测；随后修改 [normalizer.py](/Users/itboybob/Project/fire/app/services/normalizer.py)，新增 `INLINE_HYPERLINK_PATTERN` 与 `_strip_inline_hyperlink_fields()`，并在 `clean_text()` 的空白归一化前接入；再执行 `conda run -n fire python -m pytest tests/unit/services/test_normalizer.py -q`；最后按计划重建 `xiaofangfa_2019` 标准化哨兵样本，并用 `rg` 显式检查超链接残留。
- 执行环境：`fire`
- 验证结果：通过，结果分为四段：
  - 红测：`1 failed in 0.02s`，失败点仅为 `test_clean_text_strips_inline_hyperlink_field_code_from_real_fixture`
  - `normalizer` 绿测：`9 passed in 0.03s`
  - 哨兵重建：`conda run -n fire python -c "... normalize_document(...)"` 成功输出 `data/normalized/xiaofangfa_2019.txt`
  - 显式残留检查：
    - `rg -n 'HYPERLINK|https?://|\\l "#"' data/normalized/xiaofangfa_2019.txt -S` 无命中
    - `rg -n 'HYPERLINK|https?://|\\l "#"' data/normalized -S` 无命中
    - 关键正文抽样显示 `第六十二条` 现为 `依照《中华人民共和国治安管理处罚法》的规定处罚`，`第六十五条` 现为 `依照《中华人民共和国产品质量法》的规定从重处罚`
- 当前阻塞点：无新的技术阻塞；已满足任务 2 的用户自管检查点条件，等待用户先检查标准化哨兵结果，再继续任务 3。

### 2026-03-28 标准化与切块重构 Task 1 复跑确认并进入用户检查点

- 执行内容：在 `fire` conda 环境按实施计划第 4 步再次执行 `conda run -n fire python -m pytest tests/unit/services/test_normalizer.py tests/unit/services/test_chunk_builder.py -q`，确认补齐真实夹具后，失败是否仍只落在目标新增行为上。
- 执行环境：`fire`
- 验证结果：按预期失败，结果为 `2 failed, 12 passed in 0.02s`。失败集合与首次红测完全一致，仍仅包括：
  - `test_clean_text_strips_inline_hyperlink_field_code_from_real_fixture`
  - `test_build_chunks_matches_real_structured_fixture`
  说明当前不存在“夹具缺失、测试语法错误、非目标断言连带失败”等额外漂移。
- 当前阻塞点：无新的技术阻塞；已满足任务 1 的用户自管检查点条件，等待用户审阅真实夹具后，再进入 `Task 2` 和 `Task 4` 的代码修改。

### 2026-03-28 标准化与切块重构 Task 1 首次红测成立

- 执行内容：新增真实回归夹具 [inline_hyperlink_raw.txt](/Users/itboybob/Project/fire/tests/fixtures/normalized/inline_hyperlink_raw.txt)、[inline_hyperlink_expected.txt](/Users/itboybob/Project/fire/tests/fixtures/normalized/inline_hyperlink_expected.txt)、[xiaofangfa_article_62_structured.json](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_structured.json)、[xiaofangfa_article_62_expected.jsonl](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl)，并修改 [test_normalizer.py](/Users/itboybob/Project/fire/tests/unit/services/test_normalizer.py) 与 [test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py) 接入真实失败测试；随后在 `fire` conda 环境执行 `conda run -n fire python -m pytest tests/unit/services/test_normalizer.py tests/unit/services/test_chunk_builder.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，结果为 `2 failed, 12 passed in 0.04s`。失败点仅集中在两条新增断言：
  - `test_clean_text_strips_inline_hyperlink_field_code_from_real_fixture`：当前 `clean_text()` 仍保留真实行内 `HYPERLINK ... \l "#"` 字段码。
  - `test_build_chunks_matches_real_structured_fixture`：当前 `build_chunks()` 仍把第六十二条输出为单个粗粒度 chunk，尚未细化为枚举级 chunk。
- 当前阻塞点：需要按实施计划第 4 步复跑一次同一组测试，确认失败不会漂移到“夹具缺失 / 测试语法 / 非目标断言”之外；完成后进入任务 1 的用户检查点。

### 2026-03-28 重构 ADR 中文化完成

- 执行内容：将 [标准化与切块重构 ADR](./adr/2026-03-28-normalization-and-chunking-refactor.md) 全量改写为中文版本，并同步修正文档状态摘要中对该批重构文档语言状态的描述。
- 执行环境：本次为文档改写；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：重构设计文档、实施计划与 ADR 现已全部统一为中文表述，文档系统不再保留这批重构决策的英文正文。
- 当前阻塞点：等待按中文化后的重构计划开始执行真实夹具、上游修复、分阶段重建与全量重建；在此之前，`Task 6` 继续保持暂停。

### 2026-03-28 重构文档中文化完成

- 执行内容：将 [标准化与切块重构设计](./plans/2026-03-28-normalization-and-chunking-refactor-design.md) 与 [标准化与切块重构实施计划](./plans/2026-03-28-normalization-and-chunking-refactor.md) 统一改写为中文版本，保留原有门禁、任务拆分与验证要求。
- 执行环境：本次为文档改写；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：两份新文档已不再中英混杂，后续可直接用于中文语境下的设计审阅和执行交接。
- 当前阻塞点：等待按新的中文实施计划开始执行重构；在该计划完成前，`Task 6` 仍保持暂停。

### 2026-03-28 重构门禁设计与计划落盘

- 执行内容：完成 `Task 6` 前置重构的文档设计落盘，新增 [标准化与切块重构设计](./plans/2026-03-28-normalization-and-chunking-refactor-design.md)、[标准化与切块重构实施计划](./plans/2026-03-28-normalization-and-chunking-refactor.md) 与对应 [ADR](./adr/2026-03-28-normalization-and-chunking-refactor.md)，并同步更新 [文档索引](./文档索引.md)、主线 [实施计划](./plans/2026-03-28-fire-law-rag-implementation.md) 及基线 [设计文档](./plans/2026-03-28-fire-law-rag-design.md)。
- 执行环境：本次为文档设计与整理；未执行新的 Python、pytest 或服务启动命令。
- 验证结果：文档系统已正式引入 ADR 层；`Task 6` 现已被新重构计划门禁拦截。后续执行必须先完成真实夹具、`normalizer` 修复、`chunk_builder` 二级切块、分阶段重建和全量重建。
- 当前阻塞点：等待按新实施计划开始执行重构；在该计划完成前，原主线 `Task 6` 保持暂停。

### 2026-03-28 Task 5 段内二级切块需求审计

- 执行内容：在 `fire` conda 环境扫描全部 `data/chunks/*.jsonl`，核对是否存在超过 `DEFAULT_MAX_CHUNK_CHARS=300` 的已生成 chunk；同时扫描 `data/structured/*.json` 中带 `（一）（二）` 等枚举标记的真实条文，评估“段内二级切块”是否只影响个别法规。
- 执行环境：`fire`
- 验证结果：当前已生成 chunk 中，仅 [xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl) 仍存在 `2` 个超限块：
  - `xiaofangfa_2019#article-62-part-1`，长度 `334`
  - `xiaofangfa_2019#article-65-part-1`，长度 `379`
- 其余 5 份法规的已生成 chunk 未发现超限。但真实 `structured` 输入中，多份法规都存在带 `（一）（二）` 的枚举条文，例如 [xiaofangfa_2019.json](/Users/itboybob/Project/fire/data/structured/xiaofangfa_2019.json)、[hebei_xiaofang_anquan_zerenzhi_guiding.txt](/Users/itboybob/Project/fire/data/normalized/hebei_xiaofang_anquan_zerenzhi_guiding.txt)、[xiaofang_anquan_zerenzhi_shishi_banfa.txt](/Users/itboybob/Project/fire/data/normalized/xiaofang_anquan_zerenzhi_shishi_banfa.txt) 等。因此若引入“段内二级切块”，应作为通用规则落入 `chunk_builder.py`，并全量重建 `data/chunks/*.jsonl`，而不是只对 `xiaofangfa_2019` 做特判。
- 当前阻塞点：当前无新的技术阻塞；后续若正式调整切块规则，需要同步更新真实夹具回归，并在 `Task 6` 建索引前重建下游产物。

### 2026-03-28 分块超链接残留根因定位

- 执行内容：在 `fire` conda 环境执行 `conda run -n fire /usr/bin/textutil -convert txt -stdout -encoding UTF-8 '法律文本/消防法--2019年4月23日.doc'` 抽样复核原始转换输出，并结合 `rg` 全量搜索 `data/normalized/`、`data/structured/`、`data/chunks/` 中的 `HYPERLINK` 残留；同时对 `app/services/normalizer.py`、`app/services/structure_parser.py`、`app/services/chunk_builder.py` 与 `tests/unit/services/test_normalizer.py` 做全链路只读审查。
- 执行环境：`fire`
- 验证结果：已确认 `HYPERLINK` 在 `.doc -> textutil` 输出阶段就以内联字段码形式进入正文，当前仅发现于 `xiaofangfa_2019` 的第六十二条和第六十五条。`clean_text()` 只在整行以 `HYPERLINK` 开头时丢弃该行，因此会漏掉 `《 HYPERLINK "..." \l "#" 法律名》` 这种条文内嵌样式；`structure_parser` 与 `chunk_builder` 均未做二次清洗，只会把污染继续传递到 `data/structured/*.json` 和 `data/chunks/*.jsonl`。现有测试也只覆盖了独立成行的 `HYPERLINK foo`，没有覆盖真实 `.doc` 的内联字段码样式。
- 当前阻塞点：需要先在 `normalizer` 中实现“删除字段码、保留显示文本”的内联超链接清洗，再补真实样式回归测试，并从 `data/normalized/` 起重生成受影响产物。

### 2026-03-28 Task 5 审查通过

- 执行内容：由 `code-reviewer` 对 `app/services/chunk_builder.py` 与 `tests/unit/services/test_chunk_builder.py` 做只读审查，重点检查切块路径保留、长条文按段拆分、JSONL 落盘，以及与现有 `data/structured/*.json` 的匹配风险。
- 执行环境：审查基于当前工作树与已通过的 `fire` 环境验证结果完成。
- 验证结果：未发现新的实质性问题。剩余风险主要是三类：
  - 若单个段落本身极长，当前实现不会继续向句子级拆分，因此单块长度仍可能超过 `DEFAULT_MAX_CHUNK_CHARS`
  - `Task 5` 测试目前仍以合成结构 payload 为主，尚未固化真实 `data/structured/*.json -> data/chunks/*.jsonl` 的夹具回归
  - 空条文 / 空 `chunks` 输出的边界行为尚未单独写测试
- 当前阻塞点：当前无新的技术阻塞；这些风险可在后续 `Task 6` 前按需要补成回归测试。

### 2026-03-28 Task 5 真实语料切块执行完成

- 执行内容：在 `fire` conda 环境调用当前 `chunk_builder` 实现，从 `data/structured/*.json` 生成全部 `data/chunks/*.jsonl`，并抽样核对切块数量、路径和多段条文拆分结果。
- 执行环境：`fire`
- 验证结果：通过，已生成 `6` 份 chunk 产物。统计结果为：
  - `hebei_xiaofang_anquan_zerenzhi_guiding`：`55` 块，其中多段拆分块 `32`
  - `hebei_xiaofang_anquan_zerenzhi_shishi_banfa`：`30` 块，其中多段拆分块 `10`
  - `hebei_xiaofang_tiaoli`：`63` 块，其中多段拆分块 `0`
  - `jiguan_tuanti_qiye_shiye_danwei_xiaofang_anquan_guanli_guiding`：`53` 块，其中多段拆分块 `10`
  - `xiaofang_anquan_zerenzhi_shishi_banfa`：`47` 块，其中多段拆分块 `24`
  - `xiaofangfa_2019`：`81` 块，其中多段拆分块 `14`
  抽样复核 `xiaofangfa_2019#article-16-part-1` 显示切块仍保持路径 `中华人民共和国消防法 > 第二章 火灾预防 > 第十六条`，且是按段保留条文内容，没有退化成任意句子碎片。
- 当前阻塞点：当前无新的技术阻塞；若继续执行计划，可进入 `Task 6`。

### 2026-03-28 Task 5 服务层回归重新通过

- 执行内容：在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q`，重新回归验证 `Task 2` 到 `Task 5` 的离线链路。
- 执行环境：`fire`
- 验证结果：通过，结果为 `20 passed in 0.04s`。说明当前语料发现、标准化、结构解析和切块逻辑之间没有出现新的回归冲突。
- 当前阻塞点：仍需在真实 `data/structured/*.json` 上生成首批 `data/chunks/*.jsonl`，并检查切块数、路径和样本内容是否符合“按条优先”的设计约束。

### 2026-03-28 Task 5 重新绿测通过

- 执行内容：在 `app/services/chunk_builder.py` 中补回按条优先切块实现后，于 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_chunk_builder.py -q`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `4 passed in 0.01s`。说明当前最小切块能力已成立：条文路径保留、长条按段拆分、无章节标题路径不漂移，以及 `data/chunks/<document_id>.jsonl` 落盘。
- 当前阻塞点：仍需把 `Task 5` 与 `Task 2-4` 一起跑服务层回归，并在真实 `data/structured/*.json` 上生成 `data/chunks/*.jsonl` 后做抽样审查。

### 2026-03-28 Task 5 服务层回归通过

- 执行内容：在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q`，回归验证 `Task 2` 到 `Task 5` 的离线链路。
- 执行环境：`fire`
- 验证结果：通过，结果为 `19 passed in 0.06s`。说明当前语料发现、标准化、结构解析和切块逻辑之间没有出现回归冲突。
- 当前阻塞点：仍需在真实 `data/structured/*.json` 上生成首批 `data/chunks/*.jsonl`，并检查切块数、路径和样本内容是否符合“按条优先”的设计约束。

### 2026-03-28 Task 5 绿测通过

- 执行内容：新增 `app/services/chunk_builder.py`，实现 `Chunk` 数据模型、按条优先切块、超长条文按段拆分，以及 `write_chunk_file()` 的 JSONL 落盘；随后在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_chunk_builder.py -q`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `3 passed in 0.02s`。说明 `Task 5` 的最小能力已成立：条文路径保留、分段后路径不漂移、以及 `data/chunks/<document_id>.jsonl` 输出稳定。
- 当前阻塞点：仍需扩大到服务层回归，并在真实 `data/structured/*.json` 上生成首批 `data/chunks/*.jsonl` 后做抽样审查。

### 2026-03-28 Task 5 红测成立

- 执行内容：新增 `tests/unit/services/test_chunk_builder.py`，覆盖条文路径保留、超长条文按段切块和 JSONL 落盘后，在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_chunk_builder.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，结果为 `3 failed in 0.03s`，全部失败均为 `ModuleNotFoundError: No module named 'app.services.chunk_builder'`。说明 `Task 5` 当前仍处于纯测试阶段，TDD 红测成立。
- 当前阻塞点：需要新增 `app/services/chunk_builder.py`，补上切块数据模型、按条优先切块逻辑和 JSONL 落盘实现。

### 2026-03-28 Task 4 终审通过

- 执行内容：在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py -q`，并重新对 6 份 `data/normalized/*.txt` 与 `data/structured/*.json` 做逐份终审，重点核对历史修改前言是否污染 `title`、`promulgated_on/effective_on`、首条条号、`chapter_title/heading_path` 和首条正文。
- 执行环境：`fire`
- 验证结果：通过，测试结果为 `16 passed in 0.04s`。终审脚本显示：
  - `hebei_xiaofang_anquan_zerenzhi_shishi_banfa` 的前言伪条号仍存在于标准化文本前言区，但结构化输出已正确选取真实标题、真实 `第一条`、`promulgated_on=2009年10月29日`，且前言文本未漏入首条正文。
  - `jiguan_tuanti_qiye_shiye_danwei_xiaofang_anquan_guanli_guiding` 已正确提取 `promulgated_on=2001年11月14日`、`effective_on=2002年5月1日`。
  - 其余 4 份文档未发现标题、首条、正文或元数据被历史前言污染的残留问题。
- 当前阻塞点：当前无新的技术阻塞；若继续执行计划，可进入 `Task 5`。

### 2026-03-28 Task 4 最新前后对照审计

- 执行内容：在 `fire` conda 环境重新对 `data/normalized/*.txt` 与 `data/structured/*.json` 做逐份对照审计，重点检查历史修改前言是否污染 `title`、`promulgated_on/effective_on`、首条条号、`chapter_title/heading_path` 和首条正文。
- 执行环境：`fire`
- 验证结果：重点风险已明显收敛。`hebei_xiaofang_anquan_zerenzhi_shishi_banfa` 现已正确解析为标题 `河北省消防安全责任制实施办法`、首条 `第一条`、`promulgated_on=2009年10月29日`，且前言中的伪条号 `第五条/第六条` 未漏进 article text。其余文档也未发现“前言污染标题/首条/正文”的残留问题。当前剩余问题集中在 `jiguan_tuanti_qiye_shiye_danwei_xiaofang_anquan_guanli_guiding`：标准化文本第 2 行含 `2001 年 11 月 14 日` / `2002 年 5 月 1 日`，但结构化 JSON 仍为 `promulgated_on=null`、`effective_on=null`。
- 当前阻塞点：若要批准当前 `Task 4` 输出，仍需修正日期提取正则，使其兼容带空格的中文日期写法。

### 2026-03-28 Task 4 历史修改前言污染边界修正

- 执行内容：在真实结构化结果中发现 `hebei_xiaofang_anquan_zerenzhi_shishi_banfa` 的 `promulgated_on` 被“修改决定前言”污染后，补充更贴近真实样本的测试，修正 `structure_parser` 的标题搜索边界与公布日期提取优先级，再次在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py -q`，并重生成全部 `data/structured/*.json`。
- 执行环境：`fire`
- 验证结果：通过。服务层回归结果仍为 `15 passed in 0.03s`；真实语料重生成结果显示：
  - `hebei_xiaofang_anquan_zerenzhi_shishi_banfa` -> `title=河北省消防安全责任制实施办法`，`promulgated_on=2009年10月29日`，`effective_on=2009年12月1日`，条文范围 `第一条` 到 `第二十四条`
  - 其余 5 份结构化结果的标题与首末条范围保持稳定，无新增退化
- 当前阻塞点：本地修复与复核已完成，等待 `@Poincare` 对“历史修改说明是否仍扰乱结构解析结果”做最终审查。

### 2026-03-28 Task 4 真实语料结构化执行完成

- 执行内容：在新增 `app/services/structure_parser.py`、`tests/unit/services/test_structure_parser.py` 和结构片段夹具后，于 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py -q`，随后将 `data/normalized/*.txt` 全量解析并落盘到 `data/structured/*.json`。
- 执行环境：`fire`
- 验证结果：通过。服务层回归结果为 `15 passed in 0.04s`；真实语料结构化结果为 `documents=6`，6 份法规全部生成 JSON。关键样本已本地复核：
  - `xiaofangfa_2019` -> 标题 `中华人民共和国消防法`，条文范围 `第一条` 到 `第七十四条`
  - `hebei_xiaofang_anquan_zerenzhi_shishi_banfa` -> 标题 `河北省消防安全责任制实施办法`，条文范围 `第一条` 到 `第二十四条`
  - `hebei_xiaofang_tiaoli` -> 标题 `河北省消防条例`，条文范围 `第一条` 到 `第六十三条`
- 当前阻塞点：实现与本地复核已完成，等待 `@Poincare` 对 `normalized -> structured` 前后结果做最终对比审查。

### 2026-03-28 Task 4 红测成立

- 执行内容：先修正实施计划中 `Task 4` 关于 `title/document_id` 语义和真实前言结构覆盖不足的问题，然后在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_structure_parser.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，报 `ModuleNotFoundError: No module named 'app.services.structure_parser'`。说明当前已进入 `Task 4` 的纯测试阶段，TDD 红测成立。
- 当前阻塞点：需要新增 `app/services/structure_parser.py`，实现 `ParsedDocument` / `ParsedArticle`、标题与元数据提取、条文结构解析，以及 `data/structured/<document_id>.json` 落盘。

### 2026-03-28 Task 3 Unicode 行终止符真实语料复核通过

- 执行内容：在 `fire` conda 环境调用当前 `CorpusIngestor + Normalizer` 实现，重新生成全部 `data/normalized/*.txt` 产物，并按文件类型统计 `.doc/.docx` 成功数，同时检查标准化文本中是否仍含 `U+2028/U+2029/\r`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `documents=6 file_types={'docx': 3, 'doc': 3}`、`successes=6 failures=0 success_by_type={'docx': 3, 'doc': 3}`、`anomalies=[]`。说明当前 `.doc` 与 `.docx` 两类真实输入都能成功标准化，且产物已无异常行终止符残留。
- 当前阻塞点：代码实现与真实语料复核已完成，等待 `code-reviewer` 给出最终审查意见。

### 2026-03-28 Task 3 Unicode 行终止符绿测通过

- 执行内容：在 `app/services/normalizer.py` 中补充 `U+2028/U+2029` 到普通换行的归一化，并将分行逻辑收紧为 `splitlines()` 后，于 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `12 passed in 0.02s`。说明 `.doc/.docx` 的现有加载路径与新增 Unicode 行终止符修复可同时成立。
- 当前阻塞点：仍需重生成真实语料产物，并确认 `data/normalized/` 中不再残留异常行终止符。

### 2026-03-28 Task 3 Unicode 行终止符红测成立

- 执行内容：在 `tests/unit/services/test_normalizer.py` 新增 `U+2028/U+2029` Unicode 行终止符用例后，于 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，结果为 `1 failed, 7 passed in 0.04s`。失败断言表明 `clean_text()` 仍保留了 `U+2028/U+2029`，没有把它们标准化成普通换行。
- 当前阻塞点：需要在 `app/services/normalizer.py` 中补充 `U+2028/U+2029` 的换行归一化逻辑，然后重跑测试并重生成 `data/normalized/`。

### 2026-03-28 Task 3 真实语料标准化执行完成

- 执行内容：在 `fire` conda 环境调用当前 `CorpusIngestor + Normalizer` 实现，对 `法律文本/` 下 6 份 `.doc/.docx` 法规执行标准化，输出到 `data/normalized/`，并对 `xiaofangfa_2019` 自动对比 `textutil` 原始提取文本和标准化文本。
- 执行环境：`fire`
- 验证结果：通过，`6` 份文档全部生成标准化文本，无失败报告。对比结果显示 `xiaofangfa_2019` 从 `198` 行标准化为 `197` 行，共有 `86` 处行级变化，主要是三类清洗：章节标题空白压缩（如 `第一章　总  则` -> `第一章 总则`）、条号与正文之间的空白统一（如 `第一条　...` -> `第一条 ...`），以及多余空行折叠。
- 当前阻塞点：当前无新的技术阻塞；下一步可进入 `Task 4`，开始解析章节与条文结构。

### 2026-03-28 Task 3 绿测通过

- 执行内容：修正 `clean_text()` 的空白折叠逻辑与标准化期望夹具读取方式后，在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `11 passed in 0.02s`。说明 `Task 2 + Task 3` 的服务层能力已形成回归闭环。
- 当前阻塞点：仍需用真实语料执行一次标准化，确认 `data/normalized/` 产物与清洗结果符合预期。

### 2026-03-28 Task 3 首次绿测失败

- 执行内容：新增 `app/services/normalizer.py` 并在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_normalizer.py -q`，验证文档清洗、`textutil` 转换与标准化落盘。
- 执行环境：`fire`
- 验证结果：失败，结果为 `3 failed, 4 passed in 0.03s`。失败集中在两类问题：`clean_text()` 仍保留了多余空行，以及 `expected_fire_law.txt` 带有尾随换行，导致与标准化输出不一致。
- 当前阻塞点：需要修正空白折叠逻辑与标准化期望夹具，然后重新执行 `Task 3` 单测。

### 2026-03-28 Task 3 红测成立

- 执行内容：新增 `tests/unit/services/test_normalizer.py` 与 `tests/fixtures/normalized/expected_fire_law.txt`，覆盖清洗规则、`textutil` 调用边界、标准化落盘与失败报告后，在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，报 `ModuleNotFoundError: No module named 'app.services.normalizer'`。说明 `Task 3` 仍处于纯测试阶段，TDD 红测成立。
- 当前阻塞点：需要新增 `app/services/normalizer.py`，实现 `clean_text()`、Office 文档加载、标准化文件输出，以及空结果失败报告。

### 2026-03-28 已将隔离 worktree 折回 main

- 执行内容：将 `../fire-task2-manifest` 中已验证的 Python 3.14 基线调整、`Task 2` 代码与测试、README 和状态文档同步回当前 `main` 工作树，在主工作树重新执行回归测试，并移除额外 worktree 目录。
- 执行环境：`fire`
- 验证结果：`python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py tests/unit/services/test_corpus_ingestor.py -q` 通过，结果为 `6 passed in 0.23s`。说明 worktree 回收后，`main` 的代码与测试状态一致。
- 当前阻塞点：当前无新的技术阻塞；若要让分支恢复为“非脏”状态，需要由用户自行选择提交、暂存或丢弃本地修改。

### 2026-03-28 Task 1 + Task 2 回归通过

- 执行内容：在 `fire` conda 环境执行 `python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py tests/unit/services/test_corpus_ingestor.py -q`，回归验证 Python 3.14 基线、`Task 1` 最小应用和 `Task 2` 语料发现逻辑。
- 执行环境：`fire`
- 验证结果：通过，结果为 `6 passed in 0.22s`。当前批次“Task 1 合规验证 + Task 2 TDD 实现”已完成闭环。
- 当前阻塞点：无代码级阻塞；等待用户审查本批次结果并决定是否继续。

### 2026-03-28 Task 2 绿测通过

- 执行内容：新增 `app/services/__init__.py` 与 `app/services/corpus_ingestor.py`，实现 `CorpusDocument`、已知法规别名映射、ASCII slug 回退、中文文件名哈希回退，以及按 `document_id` 排序的 `discover_documents()`。
- 执行环境：`fire`
- 验证结果：`python -m pytest tests/unit/services/test_corpus_ingestor.py -q` 通过，结果为 `4 passed in 0.02s`。
- 当前阻塞点：仍需执行 `Task 1 + Task 2` 回归测试，确认本批次闭环。

### 2026-03-28 Task 2 红测成立

- 执行内容：新增 `tests/unit/services/test_corpus_ingestor.py` 和 `tests/fixtures/raw/` 原始夹具后，在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，报 `ModuleNotFoundError: No module named 'app.services'`。说明 `Task 2` 测试先于实现落地，TDD 红测阶段成立。
- 当前阻塞点：需要新增 `app/services/__init__.py` 与 `app/services/corpus_ingestor.py`，实现 `CorpusDocument` 和 `discover_documents()`。

### 2026-03-28 Task 1 fire 环境合规验证通过

- 执行内容：在 `fire` conda 环境执行 `python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py -q`，验证 `Settings` 默认路径和 `/health` 接口。
- 执行环境：`fire`
- 验证结果：通过，结果为 `2 passed in 1.25s`。`Task 1` 已完成环境合规验证，不再仅依赖 `base` 环境结果。
- 当前阻塞点：下一步进入 `Task 2`，需要先写失败测试并确认红测成立。

### 2026-03-28 fire 环境依赖安装成功

- 执行内容：在为 setuptools 显式限制 `app*` 包发现范围后，于 `fire` conda 环境重新执行 `python -m pip install -e ".[dev]"`。
- 执行环境：`fire`
- 验证结果：成功。editable install 已完成，已安装 `fastapi 0.135.2`、`pydantic-settings 2.13.1`、`httpx 0.28.1`、`openai 2.30.0`、`pytest 9.0.2`、`jinja2 3.1.6`、`uvicorn 0.42.0`，项目 `fire-law-rag 0.1.0` 已可在 `fire` 环境导入。
- 当前阻塞点：尚未执行 `Task 1` 在 `fire` 环境下的最小测试闭环。

### 2026-03-28 fire 环境依赖安装失败

- 执行内容：在 `fire` conda 环境执行 `python -m pip install -e ".[dev]"`，尝试完成 `Task 1` 的环境合规安装。
- 执行环境：`fire`
- 验证结果：失败。`setuptools` 在 editable build 阶段报 `Multiple top-level packages discovered in a flat-layout: ['app', '苏子瀚', '法律文本']`，说明当前 `pyproject.toml` 没有把包发现范围限制在应用源码目录。
- 当前阻塞点：需要先按官方文档为 setuptools 显式配置 package discovery，只包含 `app*`，然后重试安装。

### 2026-03-28 Python 3.14 基线对齐与隔离 worktree 启动

- 执行内容：创建隔离 worktree `../fire-task2-manifest` 与分支 `task2-manifest-py314`，并将 `pyproject.toml`、`README.md`、实施计划、`AGENTS.md`、`docs/文档索引.md` 对齐到 Python 3.14 执行基线与当前文档规则。
- 执行环境：未运行 Python、pytest、服务启动或安装命令；本次仅进行仓库文件编辑与 git worktree 隔离。
- 验证结果：worktree 已创建成功；仓库元数据已从 `<3.14` 调整为 `>=3.14,<3.15`，README 已改为指向 `docs/文档索引.md`，实施计划技术栈已同步到 Python 3.14。
- 当前阻塞点：尚未在 `fire` 环境执行依赖安装与 `Task 1` 合规测试。

### 2026-03-28 新会话文档读取顺序规范化

- 执行内容：基于 Harness Engineering / Context Engineering 原则，修改 `AGENTS.md` 与 `docs/文档索引.md`，明确新开聊天窗口时 Codex 的文档读取顺序、触发条件，以及“自动读取项目规则”和“按需读取业务文档”的边界。
- 执行环境：`fire`
- 验证结果：已确认仓库级规则入口收敛到 `AGENTS.md`；新会话标准顺序已固定为“先读文档索引，再读项目状态，再按任务需要读取设计文档或实施计划”；`docs/文档索引.md` 也已同步解释这套规则的目的和适用范围。
- 当前阻塞点：当前无新的文档系统阻塞；项目主阻塞仍是 `Task 1` 尚未在 `fire` 环境完成依赖安装与合规验证。

### 2026-03-28 Codex 文档读取规则审查

- 执行内容：在 `fire` conda 环境中检查 `AGENTS.md`、`docs/文档索引.md` 与 `docs/` 文件结构，并检索 OpenAI 官方 Codex 文档，确认新开聊天窗口时 Codex 对项目文档的自动发现顺序与限制。
- 执行环境：`fire`
- 验证结果：已确认当前仓库只规范了文档分层用途，尚未在 `AGENTS.md` 中显式规定新聊天窗口的读取顺序；同时根据 OpenAI 官方文档，Codex 会自动发现 `AGENTS.override.md`、`AGENTS.md` 及配置声明的 fallback 文件名，不会自动读取 `docs/` 下的业务文档，除非 `AGENTS.md` 明确指引。
- 当前阻塞点：若要让新聊天窗口中的 Codex 按固定顺序读取项目文档，仍需把“读取顺序 + 触发条件”正式写入 `AGENTS.md`。

### 2026-03-28 文档系统重构

- 执行内容：按 Harness Engineering / Context Engineering 的分层原则重构文档系统，新增 `docs/文档索引.md` 与本状态文档，并清理设计文档、实施计划、README 中的重复状态信息。
- 执行环境：未运行 Python、pytest、服务启动或安装命令；本次仅进行仓库文档整理与只读检查。
- 验证结果：已将滚动执行状态收敛到本文件；设计文档回归为稳定上下文，实施计划回归为任务与验收，README 仅保留高层状态并链接本文件。
- 当前阻塞点：`Task 1` 仍未在 `fire` 环境完成依赖安装与合规验证。

### 2026-03-28 Task 1 最近一次代码执行结果

- 执行内容：初始化项目骨架，补充 `pyproject.toml`、`.gitignore`、`.env.example`、`README.md`、FastAPI 最小应用与测试文件。
- 执行环境：`base`
- 验证结果：`python3 -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py -q` 通过，结果为 `2 passed, 1 warning`。
- 合规状态：未完成环境合规验证，因为验证不是在 `fire` 环境完成的。
- 当前阻塞点：`fire` 环境缺少依赖，无法按仓库规则重跑测试。

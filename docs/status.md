# 项目状态

本文档是本仓库唯一的执行状态文档。所有任务进展、运行环境、验证结果和当前阻塞点都只在这里更新。

## 当前摘要

- 设计基线和实施计划已经落盘，可作为后续实现依据。
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
- 当前主要阻塞点已转为原主线后续任务，而不是 `Task 6`：若继续推进，应进入 `Task 7`；仍保留的已知债务是“枚举条文的引用粒度可能偏粗”，但这不再阻塞当前关键词索引构建。

## 最新记录

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

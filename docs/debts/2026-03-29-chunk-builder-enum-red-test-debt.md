# 技术债记录：`test_build_chunks_matches_real_structured_fixture` 红测

## 债务标题

`chunk_builder` 的枚举级切块真实夹具仍要求旧规则，导致当前主线存在一条已知红测。

## 问题描述

当前失败测试 [tests/unit/services/test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py) 中的 `test_build_chunks_matches_real_structured_fixture`，要求 [tests/fixtures/chunks/xiaofangfa_article_62_structured.json](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_structured.json) 对应的 `第六十二条` 被拆成 `5` 个枚举级 chunk，并在输出中携带：

- `subitem_no`
- 细化后的 `path`，例如 `... > （一）`
- `part-n` 形式的 `chunk_id`

但当前主线实现 [app/services/chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py) 仍遵循“按条优先，只有超限时才进一步切块”的旧规则，因此会把该条文保留为单个 article-level chunk。

## 证据

### 失败测试与期望夹具

- 失败测试：`tests/unit/services/test_chunk_builder.py::test_build_chunks_matches_real_structured_fixture`
- 期望夹具： [tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl)

### 当前真实夹具不满足已接受的触发条件

- 当前真实结构化夹具中，`第六十二条` 正文总长度为 `165`
- 分段长度为 `[33, 44, 32, 9, 18, 24]`
- 不存在“某段仍超过 `300` 且包含 `（一）（二）` 枚举标记”的情况

### 设计与 ADR 已收紧规则

当前重构设计、实施计划与 ADR 的一致口径是：

- 只有在某段按现有规则切块后仍超过 `300`
- 且该段包含可识别的枚举标记

才触发“段内二级切块”。

这意味着：当前夹具对应的条文，按已接受规则并不应该被拆成 `5` 个枚举级 chunk。

## 为什么现在不修

当前主线已经回到原实施计划，正在推进 `Task 7 -> Task 8 -> Task 9`。如果现在为了让这条测试变绿而直接修改 `chunk_builder.py`，本质上是在偷偷把规则改成“未超限也按枚举拆分”，会带来两个问题：

1. 它会违反当前已接受的设计边界和 ADR 结论。
2. 它会把“搁置中的重构线”重新混入当前主线，破坏现有任务归因。

因此，这条失败应被视为**已记录但暂缓处理的技术债**，而不是当前主线必须立即修复的回归。

## 对当前主线 / Task 7-9 的影响

### 对 Task 7

- 不阻塞。
- `Task 7` 的索引构建依赖的是现有 `chunk_id`、`path`、`text` 契约，而不是枚举级 `subitem_no`。
- 当前 `build_index` 流程可以基于现有 article-level chunk 正常工作。

### 对 Task 8

- 不阻塞实现。
- 查询规范化和混合检索仍可继续推进。
- 风险是：命中的引用粒度可能偏粗，个别答案只能引用到整条法条，而不是精确到 `（一）` / `（二）`。

### 对 Task 9

- 不阻塞实现。
- 回答组装和引文约束仍可继续推进。
- 风险同样是引用粒度偏粗，而不是链路不可用。

### 对主线放行

- 会阻塞“全量 `pytest -q` 必须全绿”这一种单一放行方式。
- 不应继续让这条已知技术债红测污染当前主线的回归判断。

## 解除条件

该技术债只有两种合法解除方式，必须二选一：

1. 恢复并继续执行标准化与切块重构线，完成“段内二级切块”对应的设计、实现、夹具重建和全量验证。
2. 重新发起新的设计文档、实施计划和 ADR，正式接受“未超限的枚举条文也拆分”的新规则，再修改测试和实现。

在上述任一条件成立之前，不应直接修改当前主线 `chunk_builder.py` 来迎合这条旧红测。

## 临时放行策略

在该技术债解除前，当前主线的放行策略调整为：

1. 继续运行与当前任务直接相关的测试集，而不是把这条已知红测当作当前主线唯一门禁。
2. 对新增或修改的测试，仍必须补做真实上游产物验证。
3. 保留这条技术债记录和 `docs/status.md` 中的状态说明，避免后续会话误判为“未知新回归”。
4. 若需要执行全量测试，应明确把这条红测视为“已知技术债失败”，单独说明，不得混同为当前任务回归失败。

当前主线已采取的落地措施是：为 `tests/unit/services/test_chunk_builder.py::test_build_chunks_matches_real_structured_fixture` 添加显式 `xfail(strict=True)` 标记，并在原因中回链本记录。这样做的目的不是“假装问题不存在”，而是防止 `pytest -q` 继续把一条已知技术债误判成当前主线的新回归；同时若未来它意外转绿，`XPASS` 会重新把套件打红，提醒回收这笔债务。

## 关联文件

- [app/services/chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py)
- [tests/unit/services/test_chunk_builder.py](/Users/itboybob/Project/fire/tests/unit/services/test_chunk_builder.py)
- [tests/fixtures/chunks/xiaofangfa_article_62_structured.json](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_structured.json)
- [tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl](/Users/itboybob/Project/fire/tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl)
- [docs/plans/2026-03-28-normalization-and-chunking-refactor-design.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor-design.md)
- [docs/plans/2026-03-28-normalization-and-chunking-refactor.md](/Users/itboybob/Project/fire/docs/plans/2026-03-28-normalization-and-chunking-refactor.md)
- [docs/adr/2026-03-28-normalization-and-chunking-refactor.md](/Users/itboybob/Project/fire/docs/adr/2026-03-28-normalization-and-chunking-refactor.md)
- [docs/status.md](/Users/itboybob/Project/fire/docs/status.md)

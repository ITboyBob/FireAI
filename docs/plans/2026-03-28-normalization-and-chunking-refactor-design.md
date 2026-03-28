# 标准化与切块重构设计

**目标：** 修复消防法规离线语料链路中的两类上游质量问题：`.doc -> textutil` 导出的内联 `HYPERLINK` 字段码污染，以及枚举条文在切块阶段粒度过粗、局部 chunk 超限的问题。

**文档状态：** 已批准。该设计一旦执行，将作为 `Task 6` 之前的硬前置门禁。

**执行状态入口：** 运行时进展、验证结果和阻塞点统一记录在 [项目状态](../status.md)。

## 一、背景

当前离线链路已经完成 `normalized -> structured -> chunks` 的首轮落地，但在真实语料抽查中暴露出两类不能带入索引构建的问题：

1. `.doc` 经 macOS `textutil` 导出后，Word 内联超链接字段码会以正文内容形式残留到 [xiaofangfa_2019.txt](/Users/itboybob/Project/fire/data/normalized/xiaofangfa_2019.txt)、[xiaofangfa_2019.json](/Users/itboybob/Project/fire/data/structured/xiaofangfa_2019.json) 与 [xiaofangfa_2019.jsonl](/Users/itboybob/Project/fire/data/chunks/xiaofangfa_2019.jsonl) 中。
2. 多份法规存在 `（一）（二）` 形式的条文内枚举结构，当前 [chunk_builder.py](/Users/itboybob/Project/fire/app/services/chunk_builder.py) 只按换行段落切分，导致个别长段在切块后仍然超过目标长度，且引用粒度偏粗。

这两类问题都属于离线链路的上游质量缺陷。如果在当前状态下继续执行 `Task 6` 建索引，后续检索、引用和人工核验都会基于不一致、带污染的语料产物展开，风险不可接受。

## 二、范围

### 纳入范围

- 为 `normalizer` 增加真实内联 `HYPERLINK` 样式的回归夹具
- 在 `normalizer` 中实现“删除字段码、保留显示文本”的清洗规则
- 在 `chunk_builder` 中增加“段内二级切块”能力
- 为 `structured -> chunks` 增加真实回归夹具，而不是只依赖合成 payload
- 按“局部归因验证 -> 全量一致性重建”的顺序重建 `normalized/structured/chunks`
- 更新文档系统，使 `Task 6` 的门禁状态可追踪

### 不纳入范围

- 关键词索引、向量索引、检索排序逻辑本身的实现
- UI、FastAPI API、问答链路
- OCR、PDF、新语料来源
- 对法规正文做语义改写或摘要

## 三、核心设计

### 3.1 设计原则

- 先锁真实回归，再改代码
- 先做局部重建归因，再做全量重建确认一致性
- 不允许把旧 `normalized/structured/chunks` 与新规则产物混用
- 不按句号随意切碎法条；优先依赖法律原文自带结构

### 3.2 `normalizer` 设计

`normalizer` 的职责从“删除整行噪声”提升为“清理真实 Office 字段码污染”。这次不改变 `.doc/.docx` 加载入口，只增加对内联 `HYPERLINK` 字段码的清洗能力。

目标行为是：

- 删除类似 `HYPERLINK "..." \l "#"` 的字段码片段
- 保留用户真正能看到的显示文本，例如 `《中华人民共和国治安管理处罚法》`
- 不影响标题、条号、日期、章节边界和正文汉字内容

### 3.3 `chunk_builder` 设计

“段内二级切块”会作为 `chunk_builder` 的通用能力，而不是 `xiaofangfa_2019` 的特判。但触发条件必须保守：

- 仅当某个段落在现有按段切块后仍超过 `DEFAULT_MAX_CHUNK_CHARS`
- 且该段落中存在可识别的 `（一）（二）...` 枚举标记

触发后：

- 按枚举标记切分子项
- 将引导句复制到每个子项 chunk，避免脱离适用条件
- 增加 `subitem_no` 元数据，如 `（一）`
- 路径细化为 `法规 > 章节 > 条号 > （一）`

这样既能降低 chunk 长度，也能提高检索和引用精度，同时避免句子级切分造成法条条件断裂。

## 四、执行门禁

`Task 6` 在本次重构完成前不得启动。门禁解除条件必须同时满足：

1. 真实 `normalizer` 回归夹具通过
2. 真实 `structured -> chunks` 回归夹具通过
3. 局部哨兵样本重建结果稳定
4. 全量 `normalized -> structured -> chunks` 重建完成
5. 全量重建后的关键摘要已复核并记录到 [项目状态](../status.md)

## 五、验证策略

验证分两层：

### 5.1 局部归因验证

针对受影响最明显的样本先做定点重建，判断问题出现在哪一层：

- `normalized` 出现误删或残留：归因 `normalizer`
- `normalized` 正常但 `structured` 漂移：归因 `normalizer` 清洗过度或 `structure_parser` 被连带影响
- `structured` 正常但 `chunks` 异常：归因 `chunk_builder`

### 5.2 全量一致性验证

局部验证通过后，再全量重建 6 份法规，保证所有 `normalized/structured/chunks` 都来自同一代规则。只有这一轮通过，才允许继续 `Task 6`。

## 六、风险与控制

### 6.1 主要风险

- 内联字段码清洗过度，误删真实法规文本
- 段内二级切块引入不稳定 `chunk_id` 或路径漂移
- 局部样本通过，但全量语料暴露新边界
- 新旧产物混用导致后续索引和引用不可追踪

### 6.2 控制手段

- 先补真实夹具，避免只靠玩具样本
- 先局部重建、再全量重建，降低排查成本
- 在重建前记录基线摘要，重建后逐项对比
- 把这次门禁和方案写入 ADR 与实施计划，避免后续绕过

## 七、成功标准

- `data/normalized/` 中不再出现真实内联 `HYPERLINK` 字段码残留
- `data/chunks/` 中不再保留当前已知的超限长单段
- `Task 4` 已稳定的标题、前言、日期提取能力不退化
- `Task 6` 建索引前，上游三层产物全部来自同一代重建结果

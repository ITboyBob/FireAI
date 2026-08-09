# Evaluation / Optimization 模板组件摘录

> **文档角色**：上游模板参考资料
>
> **权威边界**：仅用于追溯模板的组件范围，不属于[新评测系统设计卷册](../../新评测和优化方案.md)，不得覆盖总卷或任何分卷的字段、指标、阈值、Gate、SDK 或报告契约。

## Evaluation 模板组件

| 组件           | 模板文件/对象                                      | 职责                                                         |
| -------------- | -------------------------------------------------- | ------------------------------------------------------------ |
| 被测 Agent     | `agent/agent.py`、`root_agent`                     | 天气 Agent，绑定模型、指令及四个天气工具。                   |
| 运行配置       | `agent/config.py`、`.env`                          | 从环境变量加载模型凭据、端点和模型名。                       |
| 评测集         | `weather_agent.evalset.json`                       | 声明一个用例：用户问题、预期最终回复、预期工具调用、会话初始状态。 |
| 指标与阈值     | `agent/test_config.json`                           | 工具轨迹平均分 ≥ 0.8；最终回复包含预期文本的平均分 ≥ 0.6。   |
| 评测编排       | `test_quickstart.py` → `AgentEvaluator.evaluate()` | 加载 Agent、同目录配置和评测集，逐用例运行并评分。           |
| 质量门禁与结果 | `AgentEvaluator` / pytest                          | 任一用例未达阈值即抛失败；当前 quickstart 打印明细，不指定结果落盘目录。 |

## Optimization 模板组件

| 组件                | 模板文件/对象                                            | 职责                                                         |
| ------------------- | -------------------------------------------------------- | ------------------------------------------------------------ |
| 可执行 Agent 适配器 | `agent/agent.py`、`call_agent()`                         | 每次调用重新读取 Prompt，并创建独立 `Runner + InMemorySessionService`，避免 case 间状态污染。 |
| 优化对象注册表      | `TargetPrompt`                                           | 将 `system.md` 与 `skill.md` 注册为可读写字段；本例每轮只改一个字段。 |
| 初始 Prompt         | `agent/prompts/system.md`、`skill.md`                    | 被优化的 baseline；示例故意让“只给答案”与“展示推理”相冲突。  |
| 数据分层            | `train.evalset.json`、`val.evalset.json`                 | train 的 5 个用例供反思抽样；val 的 3 个用例负责候选评分、接受和停止。 |
| 评分协议            | `optimizer.json` 的 `evaluate`                           | 精确/包含式答案指标，以及含数值正确、推理清晰、单位正确的 LLM rubric。 |
| 反思与候选生成      | GEPA `reflection_lm`                                     | 从 train minibatch 的失败表现生成新的 Prompt 候选。          |
| 候选选择            | Pareto 前沿、全量 val 评测                               | 候选通过验证后，与历史 Pareto 前沿比较并接受或拒绝。         |
| 停止与资源控制      | `max_metric_calls`、无提升轮数、required metrics、并发度 | 限制成本、控制早停；本例最多 60 次 metric 调用。             |
| 审计、回滚与推广    | `runs/<timestamp>/`                                      | 落 `result.json`、`summary.txt`、`rounds/`、baseline/best Prompt 快照；默认 `update_source=False`，不会覆盖源 Prompt。 |

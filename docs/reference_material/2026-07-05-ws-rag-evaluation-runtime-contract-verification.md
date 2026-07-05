# Word/W 单文件 RAG 问答评测运行时契约核验记录

## Pydantic v2 契约核验

- **核验日期**：2026-07-05
- **fire 环境 Pydantic 版本**：2.12.5
- **官方文档**：https://docs.pydantic.dev/latest/concepts/models/
- **结论**：
  - `BaseModel` 仍是 Pydantic v2 主要 schema 定义方式，字段以 Annotated 属性声明。
  - `model_validate(data)` 用于从字典验证并构造模型实例；`model_validate_json(text)` 用于 JSON 字符串。
  - `model_config = ConfigDict(...)` 用于配置严格模式、额外字段策略、str_max_length 等。
  - `ConfigDict(extra="forbid")` 可拒绝未知字段；`strict=True` 关闭自动类型强制转换。
  - 字段校验器使用 `@field_validator` 和 `@model_validator`；v2 已移除 v1 的 `@validator` 和 `root_validator`。
  - `model_dump(mode="json")` 将模型序列化为可 JSON 化的字典。
- **与计划差异**：无差异；本 Task 仅使用基础 BaseModel、ConfigDict、field_validator 和 model_validate。

## OpenAI Python SDK 契约核验

- **核验日期**：2026-07-05
- **fire 环境 SDK 版本**：2.30.0
- **官方文档**：https://platform.openai.com/docs/guides/structured-outputs
- **结论**：
  - SDK 支持 `response_format={"type": "json_schema", "json_schema": {...}}`。
  - 结构化输出需要 `strict=True` 和符合 JSON Schema 的 schema 定义。
  - 响应通过 `chat.completions.create()` 返回，内容从 `choices[0].message.content` 提取。
  - 官方文档确认 `json_schema` 模式下模型输出会遵守提供的 JSON Schema，且 `additionalProperties: false` 与 `required` 字段均受支持；这满足 Judge 对 `ContextJudgment`、`FaithfulnessJudgment`、`RelevanceJudgment` 三个固定 schema 的解析需求。
  - 文档同时指出首次请求 schema 会有额外延迟，后续同 schema 请求复用；评测链路中三个 schema 固定，可接受该一次性开销。
- **与计划差异**：无差异；Judge 使用 `json_schema` + `strict=True`，不依赖 `chat.completions.parse()` 或 Pydantic 对象直接传入的 helper，保持与在线 `ModelAnswer` 解耦。

## Python 3.14 文件系统契约核验

- **核验日期**：2026-07-05
- **fire 环境 Python 版本**：3.14.2
- **macOS 版本**：待 Task 9 执行时补充
- **官方文档**：https://docs.python.org/3.14/library/os.html
- **结论**：待 Task 9 执行时补充 `os.rename()`、`os.fsync()` 和目录重命名原子性结论。
- **与计划差异**：暂无。

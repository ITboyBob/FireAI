# 消防法律 RAG

基于 `法律文本/` 的本机纯 RAG 项目。

## 第一阶段目标

- 建立离线语料流水线：标准化、结构解析、切块、建索引
- 提供最小可用的 FastAPI API 与薄网页聊天界面
- 确保回答基于检索到的法律条文并带来源约束

## 当前状态

项目已完成 `Task 1`、`Task 2` 和 `Task 3`，并已在真实语料上生成首批标准化文本。详细执行状态见 [docs/status.md](docs/status.md)。

## 环境规则

- 所有包安装必须在 conda 环境 `fire` 中执行
- 所有代码执行必须在 conda 环境 `fire` 中执行
- 每次执行完代码后，都必须同步更新 [docs/status.md](docs/status.md)

## 规划结构

- `法律文本/`：原始语料
- `app/`：FastAPI 应用代码
- `scripts/`：离线流水线脚本入口
- `data/`：可重建生成物
- `tests/`：单元测试与集成测试
- `docs/plans/`：设计文档与实施计划

## 标准化约定

- 原始 `.doc` / `.docx` 文档通过 macOS 自带 `textutil` 转成 UTF-8 纯文本
- 标准化后的文本写入 `data/normalized/<document_id>.txt`
- 若转换成功但清洗后为空，则写入 `data/normalized/<document_id>.error.txt`

## 相关文档

- [文档索引](docs/文档索引.md)
- [项目状态](docs/status.md)
- [设计文档](docs/plans/2026-03-28-fire-law-rag-design.md)
- [实施计划](docs/plans/2026-03-28-fire-law-rag-implementation.md)

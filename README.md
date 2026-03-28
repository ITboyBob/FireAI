# 消防法律 RAG

基于 `法律文本/` 的本机纯 RAG 项目。

## 第一阶段目标

- 建立离线语料流水线：标准化、结构解析、切块、建索引
- 提供最小可用的 FastAPI API 与薄网页聊天界面
- 确保回答基于检索到的法律条文并带来源约束

## 当前状态

- `Task 1` 已完成项目骨架、基础配置和 `/health` 健康接口。
- `Task 1` 的测试曾在 `base` 环境通过。
- 经复核，`fire` conda 环境目前缺少 `fastapi`、`pydantic_settings`、`httpx`、`jinja2`、`openai`、`pytest`。
- 因此，当前代码状态为：**功能骨架已落地，但尚未在要求的 `fire` 环境中完成合规验证。**

## 环境规则

- 所有包安装必须在 conda 环境 `fire` 中执行
- 所有代码执行必须在 conda 环境 `fire` 中执行
- 每次执行完代码后，都必须同步更新文档状态

## 规划结构

- `法律文本/`：原始语料
- `app/`：FastAPI 应用代码
- `scripts/`：离线流水线脚本入口
- `data/`：可重建生成物
- `tests/`：单元测试与集成测试
- `docs/plans/`：设计文档与实施计划

## 相关文档

- [设计文档](docs/plans/2026-03-28-fire-law-rag-design.md)
- [实施计划](docs/plans/2026-03-28-fire-law-rag-implementation.md)

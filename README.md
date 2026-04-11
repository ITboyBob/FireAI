# 消防法律 RAG

基于 `法律文本/` 的本机纯 RAG 项目。当前实现包含离线语料处理、混合检索、OpenAI 兼容聊天后端，以及由 FastAPI 直接提供的极薄网页聊天界面。

详细执行状态只在 [docs/status.md](docs/status.md) 维护。

## 当前能力

- 离线链路：原始 `.doc/.docx` 法规标准化、结构解析、按条优先切块、关键词索引与向量索引构建
- 在线链路：`/api/chat` 返回固定结构响应，区分“证据不足”“建库未完成”“模型调用失败”
- 网页入口：`/` 提供极薄聊天壳，浏览器端直接向 `/api/chat` 发请求并展示引文与证据

## 环境规则

- 所有包安装必须在 conda 环境 `fire` 中执行
- 所有代码执行必须在 conda 环境 `fire` 中执行
- 每次执行完代码后，都必须同步更新 [docs/status.md](docs/status.md)

## 安装

1. 激活或显式使用 `fire` 环境。
2. 在 `fire` 环境安装项目：

```bash
conda run -n fire python -m pip install -e ".[dev]"
```

3. 参考 [.env.example](.env.example) 在本机创建未纳入版本控制的 `.env`，至少补齐：

- `CHAT_API_KEY`
- `CHAT_BASE_URL`
- `CHAT_MODEL`
- `EMBEDDING_MODEL_NAME`

## 建库

先跑离线语料流水线：

```bash
conda run -n fire python scripts/build_corpus.py
```

该步骤会重建：

- `data/normalized/`
- `data/structured/`
- `data/chunks/`

再构建检索索引：

```bash
conda run -n fire python scripts/build_index.py
```

该步骤会重建：

- `data/index/retrieval.db`
- `data/index/faiss.index`
- `data/index/vector_map.json`

## 运行

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload
```

启动后可访问：

- `/`：极薄网页聊天界面
- `/health`：健康检查
- `/docs`：FastAPI 文档页

## 测试

任务 11 相关回归：

```bash
conda run -n fire python -m pytest tests/integration/pipeline/test_build_pipeline.py tests/integration/api/test_chat_api.py -q
```

完整回归：

```bash
conda run -n fire python -m pytest -q
```

## 已知限制

- 当前网页界面只是验证面板，不包含登录、历史会话、持久化草稿或多轮上下文管理。
- 若未先完成建库，网页会直接收到 `/api/chat` 的错误提示，而不是自动帮你补建索引。
- 回答层仍依赖外部 OpenAI 兼容聊天服务；若未配置真实 `CHAT_*`，只能完成本地结构与检索验证。
- 现有切块体系仍保留一条已登记的历史技术债：枚举条文在未超长时不会进一步细拆，引用粒度可能偏粗。

## 仓库结构

- `法律文本/`：原始法规输入
- `app/`：FastAPI 应用、模板和静态资源
- `scripts/`：离线流水线脚本入口
- `data/`：可重建生成物
- `tests/`：单元测试与集成测试
- `docs/plans/`：设计文档与实施计划

## 相关文档

- [文档索引](docs/文档索引.md)
- [项目状态](docs/status.md)
- [设计文档](docs/plans/2026-03-28-fire-law-rag-design.md)
- [实施计划](docs/plans/2026-03-28-fire-law-rag-implementation.md)

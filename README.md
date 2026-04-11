# 消防问答系统 2.0

基于 `法律文本/` 的本机消防法规问答系统。当前实现包含离线语料处理、混合检索、OpenAI 兼容聊天后端、本机 `SQLite` 会话持久化，以及由 FastAPI 直接提供的双栏网页会话界面。

详细执行状态只在 [docs/status.md](docs/status.md) 维护。

## 当前能力

- 离线链路：原始 `.doc/.docx` 法规标准化、结构解析、按条优先切块、关键词索引与向量索引构建
- 在线链路：
  - `/api/conversations/*` 提供会话创建、列表、详情、重命名、删除和多轮消息执行
  - `/api/chat` 保留为兼容回归入口，模型调用失败时返回明确错误
- 会话能力：本机持久化历史会话、首条消息自动标题、基础追问判定、上下文窗口裁剪、修正提示和回答快照落库
- 网页入口：`/` 提供“会话列表 + 当前线程 + 输入区”的双栏界面，前端主链默认使用 `/api/conversations/*`

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

- `/`：双栏网页会话界面
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

- 当前系统定位仍是“本机单用户会话问答系统”，不包含多用户、权限、会话搜索或跨设备同步。
- 若未先完成建库，网页会直接收到建库未完成提示，而不是自动帮你补建索引。
- 回答层仍依赖外部 OpenAI 兼容聊天服务；若未配置真实 `CHAT_*` 或提供商凭证已失效，只能完成结构、检索、持久化和前端壳验证，无法完成真实多轮回答验收。
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
- [产品需求文档（消防问答系统 2.0）](docs/plans/2026-04-11-fire-qa-system-2.0-prd.md)
- [实施计划（消防问答系统 2.0）](docs/plans/2026-04-11-fire-qa-system-2.0-implementation.md)
- [设计文档](docs/plans/2026-03-28-fire-law-rag-design.md)
- [实施计划](docs/plans/2026-03-28-fire-law-rag-implementation.md)

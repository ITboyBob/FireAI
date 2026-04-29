# 消防问答系统 2.0

## 项目简介

消防问答系统 2.0 是一个基于本机消防法规文本的问答系统。项目以 `法律文本/` 中的法规文件为语料来源，先离线生成结构化语料、切块和检索索引，再由后端完成会话管理、检索、回答生成和网页展示。

系统面向本机单用户使用，重点是让回答能够绑定到可追溯的消防法规条文，而不是让大语言模型脱离证据自由回答。

## 技术栈

- 后端框架：`FastAPI`
- 模板与静态资源：`Jinja2`、原生 `HTML/CSS/JavaScript`
- 配置管理：`pydantic-settings`
- 会话存储：本机 `SQLite`
- 关键词检索：本机 `SQLite` 索引
- 向量检索：`sentence-transformers`、`faiss-cpu`、`numpy`
- 大语言模型：使用 OpenAI 兼容接口的大语言模型 API

## 系统架构

```text
法律文本/
  -> scripts/build_corpus.py
  -> data/normalized/
  -> data/structured/
  -> data/chunks/
  -> scripts/build_index.py
  -> data/index/
  -> FastAPI 后端
  -> 会话、检索、回答生成、证据整理
  -> 网页界面
```

离线链路负责语料标准化、结构解析、切块、关键词索引和向量索引构建。

在线链路负责会话管理、查询规范化、法规证据检索、结构化回答生成、证据展示和历史记录持久化。

## 仓库结构

- `法律文本/`：原始法规输入文件。
- `app/`：FastAPI 应用、API 路由、服务层、模板和静态资源。
- `scripts/`：离线语料处理和索引构建脚本。
- `data/`：可重建的标准化文本、结构化 JSON、切块 JSONL 和检索索引。
- `var/`：本机运行时数据和临时产物。

## 环境配置

建议使用 conda 进行依赖管理。

Python 版本要求：

- `Python >=3.14,<3.15`

创建 `fire` 环境：

```bash
conda create -n fire python=3.14 -y
```

安装项目依赖：

```bash
conda run -n fire python -m pip install -e ".[dev]"
```

该命令会在 `fire` 环境中读取 `pyproject.toml` 的 `[project.dependencies]` 和 `[project.optional-dependencies].dev`，安装运行依赖与开发依赖。

下面的依赖列表用于说明项目会安装哪些核心包，不替代上面的安装命令。

核心运行依赖：

- `fastapi`
- `uvicorn`
- `jinja2`
- `pydantic-settings`
- `openai`
- `sentence-transformers`
- `faiss-cpu`
- `numpy`

参考 [.env.example](.env.example) 在本机创建未纳入版本控制的 `.env`，至少补齐：

- `CHAT_API_KEY`
- `CHAT_BASE_URL`
- `CHAT_MODEL`
- `EMBEDDING_MODEL_NAME`

## 运行和使用

1. 准备本机 `.env` 配置。

2. 构建语料。

```bash
conda run -n fire python scripts/build_corpus.py
```

   该步骤会重建：

   - `data/normalized/`
   - `data/structured/`
   - `data/chunks/`

3. 构建检索索引。

```bash
conda run -n fire python scripts/build_index.py
```

   该步骤会重建：

   - `data/index/retrieval.db`
   - `data/index/faiss.index`
   - `data/index/vector_map.json`

4. 启动后端服务。

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload
```

   若需要显式指定端口，可使用：

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload --port 8000
```

5. 访问页面。

   - 网站首页：<http://127.0.0.1:8000/>
   - 网站首页（等价地址）：<http://localhost:8000/>
   - `/`：网页会话界面
   - `/health`：健康检查
   - `/docs`：FastAPI 文档页

6. 在网页首页输入消防法规相关问题，查看回答、法律依据和条文原文。

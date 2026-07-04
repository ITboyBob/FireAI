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
  -> scripts/import_new_corpus.py
  -> data/manifests/
  -> FastAPI 后端
  -> 会话、检索、回答生成、证据整理
  -> 网页界面
```

离线链路负责语料标准化、结构解析、切块、关键词索引和向量索引构建。

增量导入链路只用于用户显式指定的单个全新法规文件。它先在 `data/.staging/` 中生成临时语料和索引，完整校验后再提交到正式 `data/`，并在 `data/manifests/incremental_imports.json` 记录成功导入状态。

在线链路负责会话管理、查询规范化、法规证据检索、结构化回答生成、证据展示和历史记录持久化。

## 仓库结构

- `法律文本/`：原始法规输入文件。
- `app/`：FastAPI 应用、API 路由、服务层、模板和静态资源。
- `scripts/`：离线语料处理和索引构建脚本。
- `data/`：可重建的标准化文本、结构化 JSON、切块 JSONL 和检索索引。
- `data/manifests/`：增量导入的 build-state 记录。
- `data/.staging/`：增量导入过程中不可见的临时产物目录。
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

2. 如需追加一个或多个全新法规，使用显式增量导入。

```bash
# 单文件（兼容旧写法，也支持 --source）
conda run -n fire python scripts/import_new_corpus.py /absolute/path/to/new-law.docx

# 显式批次：默认处理清单中 expected_extraction_class=W 且 expected_content_class=S1 的条目
conda run -n fire python scripts/import_new_corpus.py --batch-manifest /absolute/path/to/manifest.json

# 显式批次：只处理 W-S2（复合颁布文本）条目，先校验源文件
conda run -n fire python scripts/import_new_corpus.py \
  --batch-manifest /absolute/path/to/manifest.json \
  --extraction-class W \
  --content-class S2 \
  --verify-source-only

# 显式批次：只处理 W-S2 条目，执行真实导入
conda run -n fire python scripts/import_new_corpus.py \
  --batch-manifest /absolute/path/to/manifest.json \
  --extraction-class W \
  --content-class S2
```

对于本项目当前 fixture，可使用：

```bash
# W-S2（复合颁布文本）
conda run -n fire python scripts/import_new_corpus.py \
  --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json \
  --source-root 法律文本/todo \
  --extraction-class W \
  --content-class S2

# W-S3（Word 直接提取 + 尾部排除：附件、文书模板、页码域等）
# 先 dry-run 验证 v3 质量门禁和干净 chunk 数，不写入正式语料
conda run -n fire python scripts/import_new_corpus.py \
  --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json \
  --source-root 法律文本/todo \
  --extraction-class W \
  --content-class S3 \
  --dry-run

# W-S3 真实导入：dry-run 验证通过后执行，会写入正式语料、索引和 manifest
conda run -n fire python scripts/import_new_corpus.py \
  --batch-manifest tests/fixtures/legal_ingestion/todo_baseline.json \
  --source-root 法律文本/todo \
  --extraction-class W \
  --content-class S3
```

> 本项目已完成 W-S3 真实导入：批次 `run_id=c132d0f3-aa52-40cc-a1c8-7e26cb0209e1`，`selected=1`、`committed=1`、`failed=0`，`河北省消防救援机构执法过错责任追究规定.doc` 成功提交。14 文件总进度为 11/14，剩余 3 份 PDF 待 PT/PS 能力覆盖。详情见 [法规摄取能力路线图](docs/project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md)。

   单文件参数与 `--batch-manifest` 互斥；命令只接受显式指定的单个 `.doc/.docx` 文件，或一份显式批次清单。不支持目录扫描、PDF/TXT/网页导入、旧法规修订替换或条文级 diff。若发现同 `document_id`、正式输出文件已存在、manifest 已记录、关键词索引已有记录或向量映射已有记录，会直接失败，不跳过、不覆盖。

   命令成功后会输出 `run_id`、导入法规、chunk 数量、manifest 路径，并提示：语义重复法规无法只靠文件名或 hash 完整识别，第一版只做机械冲突检测。

3. 启动后端服务。

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload
```

   若需要显式指定端口，可使用：

```bash
conda run -n fire python -m uvicorn app.main:create_app --factory --reload --port 8000
```

4. 访问页面。

   - 网站首页：<http://127.0.0.1:8000/>
   - 网站首页（等价地址）：<http://localhost:8000/>
   - `/`：网页会话界面
   - `/health`：健康检查
   - `/docs`：FastAPI 文档页

5. 在网页首页输入消防法规相关问题，查看回答、法律依据和条文原文。

## 文档系统

本仓库使用分层文档系统，避免新会话一次性加载全部历史资料：

- [文档索引](docs/system_meta/文档索引.md)：登记全部文档的角色、读取时机和权威级别。
- [文档读取规则](docs/system_meta/文档读取规则.md)：定义默认最小读取集合、任务映射和冲突优先级。
- [消防问答系统 2.0 PRD](docs/architecture_or_strategy/2026-04-11-fire-qa-system-2.0-prd.md)：当前唯一产品标准。
- [工程技术标准](docs/architecture_or_strategy/工程技术标准.md)：当前技术架构和工程约束。
- [法规摄取总体架构入口](docs/architecture_or_strategy/2026-06-29-legal-ingestion-overall-architecture.md)：法规摄取三层文档结构、统一入口、策略路由和提交边界。
- [法规摄取能力路线图](docs/project_or_workflow/2026-06-29-legal-ingestion-capability-roadmap.md)：当前能力、依赖、里程碑顺序和状态的总体规划入口。
- [统一法规摄取入口 ADR](docs/architecture_or_strategy/2026-06-29-unified-legal-ingestion-entry-adr.md)：记录唯一薄 CLI 与独立策略路由的决策原因。
- [多格式法律语料摄取组件设计](docs/architecture_or_strategy/2026-06-28-multi-format-legal-corpus-ingestion-design.md)：多格式数据流、组件职责和集成边界专项。
- [S3 正文后排除边界专项设计](docs/architecture_or_strategy/2026-07-04-s3-trailing-exclusion-boundary-design.md)：S3 尾部附件、评分表、模板和印发材料的边界信号、排除契约与质量门禁。
- [S3 边界能力与 W-S3 组合验收计划](docs/project_or_workflow/2026-07-04-s3-boundary-and-w-s3-acceptance-implementation.md)：S3 独立策略、v3 门禁、W-S3 真实预演、正式导入和状态收口步骤。
- [W-S1 端到端摄取实施计划](docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation.md)：W-S1 里程碑的任务分卷、质量资格和真实验收入口。
- [S2 边界能力与 W-S2 组合验收计划](docs/project_or_workflow/2026-06-30-s2-boundary-and-w-s2-acceptance-implementation.md)：S2 边界、元数据证据、W-S2 真实验收和正式导入步骤；当前已随两份 W-S2 文件正式提交完成。

`README.md` 只承担项目介绍、安装、运行和文档入口职责，不覆盖 PRD 或工程技术标准。

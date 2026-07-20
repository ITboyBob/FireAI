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

## 评测系统

项目提供离线 RAG 评测能力，用于在真实模型上验证已导入法规的问答效果。评测代码位于 `scripts/eval_ws_rag/`，不改动在线服务。

### 已有文件和 document-id 列表

`document-id` 是每份法规导入成功后生成的唯一标识，可在以下两处找到：

- `data/manifests/incremental_imports.json` 的 `document_id` 字段；
- `data/chunks/` 目录下对应的 `<document_id>.jsonl` 文件。

当前已导入的法规与 `document-id` 对照如下：

| document-id | 法规名称 |
| --- | --- |
| doc_e656eadc89d0 | 河北省火灾高危单位消防安全管理规定 |
| doc_69c2e31cbdd7 | 高层民用建筑消防消防安全管理规定 |
| doc_2373a58c077e | 公共娱乐场所管理规定 |
| doc_d42834f991f1 | 中华人民共和国消防救援衔条例 |
| doc_7217aa1967d5 | 安全生产行政执法与刑事司法衔接工作办法 |
| doc_4cefe1e66632 | 河北省消防安全领域信用管理暂行细则 |
| doc_0d9a0b22e189 | 河北省消防技术服务监督管理规定 |
| doc_405dcbcae152 | 河北省消防行政执法裁量实施办法 |
| doc_17f21c6a42ec | 河北省火灾事故调查处理规定 |
| doc_8984bc91baeb | 消防产品监督管理规定 |
| doc_d97773f1500c | 消防监督检查规定 |
| doc_0e84d13a099b | 河北省消防设施管理规定 |
| doc_aa2b9b6c20ab | 社会消防安全教育培训规定 |
| doc_1e3762c74ebf | 河北省消防救援机构执法过错责任追究规定 |

### 生成/更新评测 dataset

dataset 是不可变问题集。`--dataset-id` 由你自行命名（如 `ws_rag_baseline_001`），不能与已有 dataset 重名。

环境变量要求（参考 `.env.example`）：

- `WS_RAG_QUESTION_GENERATOR_API_KEY`
- `WS_RAG_QUESTION_GENERATOR_BASE_URL`
- `WS_RAG_QUESTION_GENERATOR_MODEL`

命令示例：

```bash
conda run -n fire python scripts/generate_ws_rag_dataset.py \
  --document-id doc_d97773f1500c \
  --document-id doc_0e84d13a099b \
  --dataset-id ws_rag_baseline_001 \
  --seed 42
```

产物落在 `data/eval/ws_rag_datasets/<dataset_id>/dataset.json`。目录已存在时命令会失败，禁止覆盖。

### 开启新一轮评测 run

run 依赖已落盘的 dataset。`--run-id` 由你自行命名（如 `ws_rag_baseline_001_run_001`），不能与已有 run 重名。

环境变量要求：

- `CHAT_API_KEY`、`CHAT_BASE_URL`、`CHAT_MODEL`（答案生成）
- `WS_RAG_JUDGE_API_KEY`、`WS_RAG_JUDGE_BASE_URL`、`WS_RAG_JUDGE_MODEL`（Judge）

命令示例：

```bash
conda run -n fire python scripts/evaluate_ws_rag.py \
  --dataset data/eval/ws_rag_datasets/ws_rag_baseline_001/dataset.json \
  --run-id ws_rag_baseline_001_run_001
```

产物落在 `reports/ws_rag_eval/<run_id>/report.json` 和 `errors.json`。`run_id` 已存在会失败；致命错误时调试信息写入 `var/ws_rag_eval/<run_id>/debug.json`。

核验命令：

```bash
conda run -n fire python scripts/verify_ws_rag_evaluation_run.py \
  --dataset data/eval/ws_rag_datasets/ws_rag_baseline_001/dataset.json \
  --run reports/ws_rag_eval/ws_rag_baseline_001_run_001 \
  --data-dir data
```

### 启动 Dashboard

Dashboard 是独立本机 Streamlit 工具，只读已发布的 Run。

```bash
conda run -n fire python -m streamlit run scripts/eval_ws_rag/dashboard.py \
  --server.address 127.0.0.1 \
  --server.headless true
```

访问 <http://127.0.0.1:8501>。`--server.headless true` 用于跳过 Streamlit 首次运行的交互式邮箱向导（`conda run` 的非交互 stdin 会让该向导直接失败），启动后不再自动打开浏览器，需手动访问上述地址。首轮仅展示单个 mock Run，真实 Run 接入和双 Run 比较能力待后续验收。

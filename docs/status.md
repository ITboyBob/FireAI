# 项目状态

本文档是本仓库唯一的执行状态文档。所有任务进展、运行环境、验证结果和当前阻塞点都只在这里更新。

## 当前摘要

- 设计基线和实施计划已经落盘，可作为后续实现依据。
- 新开聊天窗口时的文档读取顺序已在 `AGENTS.md` 中固化，`docs/文档索引.md` 用于解释这套顺序。
- `Task 1` 的代码骨架已经落地，包括基础配置、`/health` 接口和最小测试。
- 仓库元数据和实施计划已对齐到 Python `3.14` 基线，`fire` 环境已完成 editable install。
- `Task 1` 已在要求的 `fire` conda 环境完成合规验证。
- `Task 2` 已按 TDD 落地语料发现与输入清单，并通过回归测试。
- 已将 `task2-manifest-py314` worktree 中的已验证改动折回当前 `main` 工作树。
- 当前主要阻塞点是：当前批次实现与验证已闭环，等待用户审查并决定是否继续后续任务。

## 最新记录

### 2026-03-28 已将隔离 worktree 折回 main

- 执行内容：将 `../fire-task2-manifest` 中已验证的 Python 3.14 基线调整、`Task 2` 代码与测试、README 和状态文档同步回当前 `main` 工作树，在主工作树重新执行回归测试，并移除额外 worktree 目录。
- 执行环境：`fire`
- 验证结果：`python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py tests/unit/services/test_corpus_ingestor.py -q` 通过，结果为 `6 passed in 0.23s`。说明 worktree 回收后，`main` 的代码与测试状态一致。
- 当前阻塞点：当前无新的技术阻塞；若要让分支恢复为“非脏”状态，需要由用户自行选择提交、暂存或丢弃本地修改。

### 2026-03-28 Task 1 + Task 2 回归通过

- 执行内容：在 `fire` conda 环境执行 `python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py tests/unit/services/test_corpus_ingestor.py -q`，回归验证 Python 3.14 基线、`Task 1` 最小应用和 `Task 2` 语料发现逻辑。
- 执行环境：`fire`
- 验证结果：通过，结果为 `6 passed in 0.22s`。当前批次“Task 1 合规验证 + Task 2 TDD 实现”已完成闭环。
- 当前阻塞点：无代码级阻塞；等待用户审查本批次结果并决定是否继续。

### 2026-03-28 Task 2 绿测通过

- 执行内容：新增 `app/services/__init__.py` 与 `app/services/corpus_ingestor.py`，实现 `CorpusDocument`、已知法规别名映射、ASCII slug 回退、中文文件名哈希回退，以及按 `document_id` 排序的 `discover_documents()`。
- 执行环境：`fire`
- 验证结果：`python -m pytest tests/unit/services/test_corpus_ingestor.py -q` 通过，结果为 `4 passed in 0.02s`。
- 当前阻塞点：仍需执行 `Task 1 + Task 2` 回归测试，确认本批次闭环。

### 2026-03-28 Task 2 红测成立

- 执行内容：新增 `tests/unit/services/test_corpus_ingestor.py` 和 `tests/fixtures/raw/` 原始夹具后，在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，报 `ModuleNotFoundError: No module named 'app.services'`。说明 `Task 2` 测试先于实现落地，TDD 红测阶段成立。
- 当前阻塞点：需要新增 `app/services/__init__.py` 与 `app/services/corpus_ingestor.py`，实现 `CorpusDocument` 和 `discover_documents()`。

### 2026-03-28 Task 1 fire 环境合规验证通过

- 执行内容：在 `fire` conda 环境执行 `python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py -q`，验证 `Settings` 默认路径和 `/health` 接口。
- 执行环境：`fire`
- 验证结果：通过，结果为 `2 passed in 1.25s`。`Task 1` 已完成环境合规验证，不再仅依赖 `base` 环境结果。
- 当前阻塞点：下一步进入 `Task 2`，需要先写失败测试并确认红测成立。

### 2026-03-28 fire 环境依赖安装成功

- 执行内容：在为 setuptools 显式限制 `app*` 包发现范围后，于 `fire` conda 环境重新执行 `python -m pip install -e ".[dev]"`。
- 执行环境：`fire`
- 验证结果：成功。editable install 已完成，已安装 `fastapi 0.135.2`、`pydantic-settings 2.13.1`、`httpx 0.28.1`、`openai 2.30.0`、`pytest 9.0.2`、`jinja2 3.1.6`、`uvicorn 0.42.0`，项目 `fire-law-rag 0.1.0` 已可在 `fire` 环境导入。
- 当前阻塞点：尚未执行 `Task 1` 在 `fire` 环境下的最小测试闭环。

### 2026-03-28 fire 环境依赖安装失败

- 执行内容：在 `fire` conda 环境执行 `python -m pip install -e ".[dev]"`，尝试完成 `Task 1` 的环境合规安装。
- 执行环境：`fire`
- 验证结果：失败。`setuptools` 在 editable build 阶段报 `Multiple top-level packages discovered in a flat-layout: ['app', '苏子瀚', '法律文本']`，说明当前 `pyproject.toml` 没有把包发现范围限制在应用源码目录。
- 当前阻塞点：需要先按官方文档为 setuptools 显式配置 package discovery，只包含 `app*`，然后重试安装。

### 2026-03-28 Python 3.14 基线对齐与隔离 worktree 启动

- 执行内容：创建隔离 worktree `../fire-task2-manifest` 与分支 `task2-manifest-py314`，并将 `pyproject.toml`、`README.md`、实施计划、`AGENTS.md`、`docs/文档索引.md` 对齐到 Python 3.14 执行基线与当前文档规则。
- 执行环境：未运行 Python、pytest、服务启动或安装命令；本次仅进行仓库文件编辑与 git worktree 隔离。
- 验证结果：worktree 已创建成功；仓库元数据已从 `<3.14` 调整为 `>=3.14,<3.15`，README 已改为指向 `docs/文档索引.md`，实施计划技术栈已同步到 Python 3.14。
- 当前阻塞点：尚未在 `fire` 环境执行依赖安装与 `Task 1` 合规测试。

### 2026-03-28 新会话文档读取顺序规范化

- 执行内容：基于 Harness Engineering / Context Engineering 原则，修改 `AGENTS.md` 与 `docs/文档索引.md`，明确新开聊天窗口时 Codex 的文档读取顺序、触发条件，以及“自动读取项目规则”和“按需读取业务文档”的边界。
- 执行环境：`fire`
- 验证结果：已确认仓库级规则入口收敛到 `AGENTS.md`；新会话标准顺序已固定为“先读文档索引，再读项目状态，再按任务需要读取设计文档或实施计划”；`docs/文档索引.md` 也已同步解释这套规则的目的和适用范围。
- 当前阻塞点：当前无新的文档系统阻塞；项目主阻塞仍是 `Task 1` 尚未在 `fire` 环境完成依赖安装与合规验证。

### 2026-03-28 Codex 文档读取规则审查

- 执行内容：在 `fire` conda 环境中检查 `AGENTS.md`、`docs/文档索引.md` 与 `docs/` 文件结构，并检索 OpenAI 官方 Codex 文档，确认新开聊天窗口时 Codex 对项目文档的自动发现顺序与限制。
- 执行环境：`fire`
- 验证结果：已确认当前仓库只规范了文档分层用途，尚未在 `AGENTS.md` 中显式规定新聊天窗口的读取顺序；同时根据 OpenAI 官方文档，Codex 会自动发现 `AGENTS.override.md`、`AGENTS.md` 及配置声明的 fallback 文件名，不会自动读取 `docs/` 下的业务文档，除非 `AGENTS.md` 明确指引。
- 当前阻塞点：若要让新聊天窗口中的 Codex 按固定顺序读取项目文档，仍需把“读取顺序 + 触发条件”正式写入 `AGENTS.md`。

### 2026-03-28 文档系统重构

- 执行内容：按 Harness Engineering / Context Engineering 的分层原则重构文档系统，新增 `docs/文档索引.md` 与本状态文档，并清理设计文档、实施计划、README 中的重复状态信息。
- 执行环境：未运行 Python、pytest、服务启动或安装命令；本次仅进行仓库文档整理与只读检查。
- 验证结果：已将滚动执行状态收敛到本文件；设计文档回归为稳定上下文，实施计划回归为任务与验收，README 仅保留高层状态并链接本文件。
- 当前阻塞点：`Task 1` 仍未在 `fire` 环境完成依赖安装与合规验证。

### 2026-03-28 Task 1 最近一次代码执行结果

- 执行内容：初始化项目骨架，补充 `pyproject.toml`、`.gitignore`、`.env.example`、`README.md`、FastAPI 最小应用与测试文件。
- 执行环境：`base`
- 验证结果：`python3 -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py -q` 通过，结果为 `2 passed, 1 warning`。
- 合规状态：未完成环境合规验证，因为验证不是在 `fire` 环境完成的。
- 当前阻塞点：`fire` 环境缺少依赖，无法按仓库规则重跑测试。

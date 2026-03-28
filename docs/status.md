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
- `Task 3` 已按 TDD 完成文档标准化实现，并在 `fire` 环境通过服务层回归测试。
- 已基于 `法律文本/` 真实语料生成 `data/normalized/*.txt`，当前 6 份原始法规均标准化成功。
- `Task 3` 的 Unicode 行终止符缺陷已修复，全部标准化产物已重新生成。
- 当前 3 份 `.doc` 与 3 份 `.docx` 输入均已再次验证通过，产物中确认不存在 `U+2028/U+2029/\r` 残留。
- 当前主要阻塞点是：当前无新的技术阻塞；等待 `code-reviewer` 审查结论，若无新问题可进入 `Task 4`。

## 最新记录

### 2026-03-28 Task 3 Unicode 行终止符真实语料复核通过

- 执行内容：在 `fire` conda 环境调用当前 `CorpusIngestor + Normalizer` 实现，重新生成全部 `data/normalized/*.txt` 产物，并按文件类型统计 `.doc/.docx` 成功数，同时检查标准化文本中是否仍含 `U+2028/U+2029/\r`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `documents=6 file_types={'docx': 3, 'doc': 3}`、`successes=6 failures=0 success_by_type={'docx': 3, 'doc': 3}`、`anomalies=[]`。说明当前 `.doc` 与 `.docx` 两类真实输入都能成功标准化，且产物已无异常行终止符残留。
- 当前阻塞点：代码实现与真实语料复核已完成，等待 `code-reviewer` 给出最终审查意见。

### 2026-03-28 Task 3 Unicode 行终止符绿测通过

- 执行内容：在 `app/services/normalizer.py` 中补充 `U+2028/U+2029` 到普通换行的归一化，并将分行逻辑收紧为 `splitlines()` 后，于 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `12 passed in 0.02s`。说明 `.doc/.docx` 的现有加载路径与新增 Unicode 行终止符修复可同时成立。
- 当前阻塞点：仍需重生成真实语料产物，并确认 `data/normalized/` 中不再残留异常行终止符。

### 2026-03-28 Task 3 Unicode 行终止符红测成立

- 执行内容：在 `tests/unit/services/test_normalizer.py` 新增 `U+2028/U+2029` Unicode 行终止符用例后，于 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，结果为 `1 failed, 7 passed in 0.04s`。失败断言表明 `clean_text()` 仍保留了 `U+2028/U+2029`，没有把它们标准化成普通换行。
- 当前阻塞点：需要在 `app/services/normalizer.py` 中补充 `U+2028/U+2029` 的换行归一化逻辑，然后重跑测试并重生成 `data/normalized/`。

### 2026-03-28 Task 3 真实语料标准化执行完成

- 执行内容：在 `fire` conda 环境调用当前 `CorpusIngestor + Normalizer` 实现，对 `法律文本/` 下 6 份 `.doc/.docx` 法规执行标准化，输出到 `data/normalized/`，并对 `xiaofangfa_2019` 自动对比 `textutil` 原始提取文本和标准化文本。
- 执行环境：`fire`
- 验证结果：通过，`6` 份文档全部生成标准化文本，无失败报告。对比结果显示 `xiaofangfa_2019` 从 `198` 行标准化为 `197` 行，共有 `86` 处行级变化，主要是三类清洗：章节标题空白压缩（如 `第一章　总  则` -> `第一章 总则`）、条号与正文之间的空白统一（如 `第一条　...` -> `第一条 ...`），以及多余空行折叠。
- 当前阻塞点：当前无新的技术阻塞；下一步可进入 `Task 4`，开始解析章节与条文结构。

### 2026-03-28 Task 3 绿测通过

- 执行内容：修正 `clean_text()` 的空白折叠逻辑与标准化期望夹具读取方式后，在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：通过，结果为 `11 passed in 0.02s`。说明 `Task 2 + Task 3` 的服务层能力已形成回归闭环。
- 当前阻塞点：仍需用真实语料执行一次标准化，确认 `data/normalized/` 产物与清洗结果符合预期。

### 2026-03-28 Task 3 首次绿测失败

- 执行内容：新增 `app/services/normalizer.py` 并在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_normalizer.py -q`，验证文档清洗、`textutil` 转换与标准化落盘。
- 执行环境：`fire`
- 验证结果：失败，结果为 `3 failed, 4 passed in 0.03s`。失败集中在两类问题：`clean_text()` 仍保留了多余空行，以及 `expected_fire_law.txt` 带有尾随换行，导致与标准化输出不一致。
- 当前阻塞点：需要修正空白折叠逻辑与标准化期望夹具，然后重新执行 `Task 3` 单测。

### 2026-03-28 Task 3 红测成立

- 执行内容：新增 `tests/unit/services/test_normalizer.py` 与 `tests/fixtures/normalized/expected_fire_law.txt`，覆盖清洗规则、`textutil` 调用边界、标准化落盘与失败报告后，在 `fire` conda 环境执行 `python -m pytest tests/unit/services/test_normalizer.py -q`。
- 执行环境：`fire`
- 验证结果：按预期失败，报 `ModuleNotFoundError: No module named 'app.services.normalizer'`。说明 `Task 3` 仍处于纯测试阶段，TDD 红测成立。
- 当前阻塞点：需要新增 `app/services/normalizer.py`，实现 `clean_text()`、Office 文档加载、标准化文件输出，以及空结果失败报告。

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

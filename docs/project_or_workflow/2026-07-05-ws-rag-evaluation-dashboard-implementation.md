# W-S RAG 评测 Dashboard 实施计划

> 本计划用于在当前工作区直接分批执行。
>
> **执行状态：** 待执行。本文完成只代表计划可用，不代表 Dashboard 已实现。

**目标：** 在 `fire` conda 环境中实现独立、只读的 Streamlit 本机 Dashboard，安全展示主评测链路发布的完整 Run。

**架构：** Dashboard 复用主评测链路的共享报告 schema，通过独立 loader 发现和校验 Run，再用单页 Streamlit 应用展示四类视图。Dashboard 不改动 `app/`，不重算评测结论，不读取未完整发布的 Run。

**技术栈：** Python 3.14、Streamlit 1.58.x、共享 Pydantic schema、pytest、Streamlit `AppTest`、标准库 `pathlib`/`json`。

---

## 1. 权威依据

执行前按顺序读取：

1. 根目录 `AGENTS.md`；
2. [工程技术标准](../architecture_or_strategy/工程技术标准.md)；
3. [主评测设计](../architecture_or_strategy/2026-07-04-ws-rag-evaluation-design.md)；
4. [主评测实施计划](./2026-07-05-ws-rag-evaluation-implementation.md)；
5. [Dashboard 设计总览](../architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-design.md)；
6. [Dashboard 数据契约](../architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-data-contract.md)；
7. [Dashboard 界面与验证设计](../architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-interface-and-validation.md)；
8. 本计划及当前分卷。

冲突优先级：

- 指标、阈值、`passed` 和报告生成规则服从主评测设计与实施计划；
- Run 交换格式、完整性和比较门禁服从 Dashboard 数据契约；
- 页面行为服从界面与验证设计；
- 本计划只定义实现顺序和验证步骤。

## 2. 阶段启动输入检查

### 2.1 已确认

- Dashboard 是本机开发者工具，不是正式产品前端；
- 四类视图、显式刷新和只读边界已经确定；
- `pyproject.toml` 已声明 `streamlit>=1.58.0,<2.0`；
- 前端不使用 npm、pnpm 或 yarn；
- 所有代码和测试必须通过 conda 环境 `fire` 执行。

### 2.2 开始实现前仍需确认

- 2026-07-05 当前实测 `fire` 环境尚未安装 Streamlit；进入 Phase 2 前必须报备并取得安装确认；
- 主评测计划是否已完成共享 `report_models.py`、稳定错误代码和合法 Run fixture；
- 是否已有可用于最终核对的真实 Run；
- 当前工作区是否存在无法安全避开的用户改动。

缺少前两项时不得开始 UI 实现。缺少真实 Run 时允许完成 mock/fixture 驱动开发，但不得完成 Phase 3 收口。

### 2.3 默认值

- 报告根目录：`reports/ws_rag_eval/`；
- 服务地址：`127.0.0.1:8501`；
- 有效 Run 按 `created_at` 倒序；
- 首次选择最新有效 Run；
- 不兼容 Run 只展示诊断，不展示部分业务内容。

## 3. 依赖与包管理

| 环境 | 包管理工具 | 本计划要求 |
| --- | --- | --- |
| Python | conda 环境 `fire` | 所有 Python、pytest 和 Streamlit 命令均使用 `conda run -n fire` |
| Python 依赖 | `python -m pip` + `pyproject.toml` | 直接依赖 `streamlit>=1.58.0,<2.0` |
| 测试 | `python -m pytest` | 沿用 `.[dev]` 中的 pytest |
| 前端 | 不适用 | 不安装 npm/pnpm/yarn 包 |
| 浏览器 | 优先复用已有浏览器能力 | 不私自安装 Playwright |

**依赖检查意图：** 确认 Streamlit 是否已安装，不改变环境。

```bash
conda run -n fire python -m pip show streamlit
```

**预期输出：** 显示版本且满足 `>=1.58.0,<2.0`。若未安装，停止并向用户报备：

- 依赖：`streamlit>=1.58.0,<2.0`；
- 用途：Dashboard 运行与 `AppTest`；
- 安装位置：conda 环境 `fire`；
- 包管理工具：`python -m pip`。

获批后的安装命令：

```bash
conda run -n fire python -m pip install "streamlit>=1.58.0,<2.0"
```

## 4. 分卷导航

为保持每卷低于 420 行预警线，本计划拆为：

1. 本文：范围、依赖、顺序、硬门禁、全局验证和 Git 策略；
2. [分卷一：共享契约、Run 发现与比较 loader](./2026-07-05-ws-rag-evaluation-dashboard-implementation-part-1.md)；
3. [分卷二：Streamlit 页面、状态与错误处理](./2026-07-05-ws-rag-evaluation-dashboard-implementation-part-2.md)；
4. [分卷三：浏览器、真实 Run 与文档收口](./2026-07-05-ws-rag-evaluation-dashboard-implementation-part-3.md)。

## 5. Phase 顺序

| Phase | 任务 | 前置条件 | 完成证据 |
| --- | --- | --- | --- |
| Phase 1 | 共享契约、Run 发现、诊断与比较 loader | 主评测共享 schema 可用 | loader 单元测试通过 |
| Phase 2 | 页面骨架、四视图、session state、刷新与错误态 | Streamlit 依赖获批并可导入；Phase 1 完成 | `AppTest` 通过 |
| Phase 3 | 浏览器、真实 Run、完整回归和文档收口 | 主评测真实 Run 可用；Phase 2 完成 | 字段核对、浏览器验证、完整回归通过 |

禁止跳过 Phase 1 直接根据 mock JSON 手写页面字段。

## 6. 全局硬门禁

1. 代码只能新增到 `scripts/eval_ws_rag/` 和 `tests/eval_ws_rag/`；
2. 不修改 `app/`、FastAPI API 或正式产品静态资源；
3. 复用主评测 `report_models.py`，不得复制另一套 schema；
4. 不重算或覆盖报告的 `passed`、文件指标和通过率；
5. 不内置另一套阈值；
6. 忽略暂存目录、隐藏目录、符号链接和不完整 Run；
7. schema、计数或引用一致性失败时，不展示部分业务结果；
8. 非同口径 Run 不显示涨跌、箭头、修复或退化结论；
9. 普通交互不得重新扫描磁盘，只有显式刷新替换 Run 快照；
10. 不启用 `unsafe_allow_html=True`；
11. Streamlit 默认只绑定 `127.0.0.1`；
12. 新依赖必须先报备，禁止计划执行者自行扩大依赖；
13. mock、AppTest 或计划完成不能把能力标记为 `implemented`；
14. 真实 Run、浏览器和完整回归未通过时不得收口。

## 7. 全局验证命令

### 7.1 loader

**意图：** 验证 Run 发现、校验、诊断和比较门禁。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py -q
```

**预期输出：** 全部 PASS，无新增 warning、skip 或 xfail。

### 7.2 Streamlit `AppTest`

**意图：** 验证页面状态与四类视图。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_app.py -q
```

**预期输出：** 全部 PASS。

### 7.3 评测系统与 Dashboard 联合测试

**意图：** 验证共享 schema 和真实报告兼容。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag -q
```

**预期输出：** 评测与 Dashboard 专项测试全部 PASS。

### 7.4 仓库回归

**意图：** 确认没有破坏既有摄取、检索、API 和前端行为。

```bash
conda run -n fire python -m pytest -q
```

**预期输出：** 全部 PASS，且不新增 warning、skip 或 xfail。

## 8. Git 策略

本计划授权实施阶段在每个 Task 对应测试和真实验证通过后，提交该 Task 的范围：

| 范围 | 中文 commit 说明 |
| --- | --- |
| Phase 1 | `feat(eval): 实现 Dashboard Run 加载与比较门禁` |
| Phase 2A | `feat(eval): 实现 Dashboard 骨架与总览文件视图` |
| Phase 2B | `feat(eval): 实现问题下钻与双轮对比视图` |
| Phase 2C | `feat(eval): 完成 Dashboard 刷新和错误状态` |
| Phase 3 | `docs(eval): 完成 Dashboard 真实报告验收与状态收口` |

- 每次提交前运行 `git diff --cached --check` 并检查 staged diff；
- 不夹带用户已有改动；
- 无法安全拆分时停止提交；
- 本计划不授权 push、merge、rebase、reset、checkout 或历史改写。

## 9. 完成定义

只有以下证据同时存在，Dashboard 才能标记为 `implemented`：

- 主评测链路发布的真实 Run 通过共享 schema 和一致性校验；
- loader、`AppTest`、评测专项和仓库完整回归通过；
- 浏览器中四类视图、选择兜底、刷新和错误态通过；
- 至少一组同口径双 Run 比较通过；
- 真实 Run 的 summary、文件、问题、证据、引文和错误字段完成人工核对；
- 文档索引、读取规则、路线图和能力状态与事实一致。

计划完成、依赖声明、mock 页面或单个测试通过都不是完成证据。

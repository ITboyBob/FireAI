# W-S RAG 评测 Dashboard 设计

> 本文是 [Word/W 阶段单文件 RAG 问答评测设计](./2026-07-04-ws-rag-evaluation-design.md) 的 Dashboard 扩展项总览与设计入口。
>
> **设计状态：** 已审查完善，待按实施计划执行。
> **能力状态：** `planned`。设计、计划或 mock 验证完成都不等于能力已经实现。

## 1. 设计目标

为 Word/W 单文件 RAG 问答评测提供本机只读工作台，让开发者和评测维护者能够：

- 查看单轮总体结果和每份法规的评分卡；
- 下钻到问题、回答、检索证据、Judge 结果和失败原因；
- 查看评测运行产生的结构化错误；
- 在评测口径一致时比较两个 Run，判断变化来自哪里。

Dashboard 只展示评测系统已经发布的完整 Run，不启动评测、不修改阈值，也不重新计算评测结论。

## 2. 已选方案

采用独立 Streamlit 本地应用：

```text
scripts/eval_ws_rag/dashboard.py
```

选型理由：

- 表格筛选、字段下钻和双 Run 对比是首版核心任务；
- 不修改现有 FastAPI + Jinja2 产品前端，不把内部评测工具混入正式问答页面；
- Streamlit 能用 Python 快速形成可测试的本机数据工作台。

主要代价：

- `streamlit>=1.58.0,<2.0` 是新增直接依赖；
- Dashboard 使用独立进程和端口，视觉风格不与正式产品保持一致；
- Streamlit 的控件交互会触发脚本重跑，必须显式管理会话状态，不能把“刷新报告”实现成每次交互都重新扫描磁盘。

未选方案：

| 方案 | 本阶段未选原因 |
| --- | --- |
| FastAPI + Jinja2 新页面 | 多列筛选、字段折叠、选择联动和双 Run 对比需要更多手写前端状态 |
| 静态 HTML 报告 | 缺少问题下钻和交互式对比能力 |

若未来要求同域导航、多用户、权限或对外部署，必须重新评审技术选型，不能把本机 Streamlit 直接提升为生产前端。

## 3. 首版范围

### 3.1 纳入范围

- 独立 Streamlit 本机工作台；
- 只读取 `reports/ws_rag_eval/<run_id>/` 下已完整发布的 Run；
- 总览、文件列表、问题下钻、两轮对比四类视图；
- 显式刷新；
- 缺失文件、损坏 JSON、schema 不兼容、跨字段不一致和非同口径对比提示；
- mock、单元测试、Streamlit `AppTest`、浏览器烟雾验证和真实报告核对。

### 3.2 不纳入范围

- 启动或取消评测；
- 修改阈值、修复报告、删除报告；
- 实时监听、自动轮询、评测进度流；
- 多用户、权限、云部署；
- 与正式产品导航或 FastAPI API 集成；
- 在 Dashboard 内重算 `passed`、`overall_pass_rate` 或文件级指标。

## 4. 架构与职责边界

```text
主评测链路
  ├─ 共享 report schema / 校验模型
  ├─ 暂存 Run 目录
  ├─ 写 report.json + errors.json
  ├─ 完整性与跨字段校验
  └─ 原子发布 Run 目录
             │
             ▼
Dashboard loader
  ├─ 只发现完整 Run
  ├─ 复用共享 schema
  ├─ 验证比较口径
  └─ 形成只读展示模型
             │
             ▼
Streamlit 四类视图
```

职责边界：

| 组件 | 负责 | 不负责 |
| --- | --- | --- |
| 主评测链路 | 生成问题、运行 RAG、Judge、规则校验、聚合、发布 Run | 页面展示 |
| 共享 schema | 字段类型、枚举、跨字段约束和版本兼容 | 业务评分 |
| Dashboard loader | 发现、读取、校验、筛选和安全的展示派生 | 改写报告、重新判分 |
| Streamlit 页面 | 展示、导航、显式刷新、错误提示 | 评测执行、自动修复 |

## 5. 分卷导航

为遵守单文档不超过 500 行及 420 行预警线，本专项拆为：

1. 本文：目标、选型、范围、架构和全局门禁；
2. [Dashboard 数据契约](./2026-07-05-ws-rag-evaluation-dashboard-data-contract.md)：Run 发布、字段、错误、完整性和比较兼容性；
3. [Dashboard 界面与验证设计](./2026-07-05-ws-rag-evaluation-dashboard-interface-and-validation.md)：页面、状态、刷新、测试、依赖和验收。

发生冲突时：

1. 评测指标定义和通过判定以主评测设计及其执行计划为准；
2. Run 数据交换格式以数据契约分卷为准；
3. 页面行为和验证标准以界面与验证分卷为准；
4. 具体实施顺序以 [Dashboard 实施计划](../project_or_workflow/2026-07-05-ws-rag-evaluation-dashboard-implementation.md) 为准。

## 6. 关键设计决策

### 6.1 单一结论来源

- `report.json` 保存评测结果，`errors.json` 保存执行错误；两者组成一个不可分割的 Run 产物。
- `report.json` 不再复制 `errors` 数组。
- Dashboard 读取并展示评测系统写入的 `passed`、指标和通过率，不维护第二套阈值或判分逻辑。
- 页面需要的派生统计只能用于展示，并必须能从 Run 中稳定重建。

### 6.2 Run 级原子发布

评测系统先在同一父目录写完整暂存目录，校验通过后再把整个目录原子重命名为 `<run_id>/`。Dashboard 忽略暂存目录、隐藏目录、符号链接和缺少任一正式文件的目录，避免读取“只发布了一半”的结果。

### 6.3 对比必须同口径

两轮比较前至少校验：

- schema 主版本兼容；
- `dataset_fingerprint` 相同；
- `protocol_fingerprint` 相同；
- 文档集合和问题集合可对齐。

不同口径只能并排查看元信息，不能显示涨跌箭头、改进/退化结论或文件修复状态。

### 6.4 显式刷新

- 首次进入会话时扫描一次 Run；
- 普通筛选、选择和视图切换只使用 `st.session_state` 中的已加载快照；
- 仅点击“刷新报告”时重新扫描磁盘并替换快照；
- 不使用定时轮询；无必要时不额外调用 `st.rerun()`。

## 7. 全局硬门禁

1. 不得修改 `app/` 或正式问答前端；
2. 不得在 Dashboard 内重算评测通过结论；
3. 不得内置另一套指标阈值；
4. 不得展示未完成发布或校验失败的 Run；
5. 不得对不同数据集或不同评测协议输出“提升/下降”判断；
6. 不得把用户可见文本交给 `unsafe_allow_html=True`；
7. 服务默认绑定 `127.0.0.1`，不得默认暴露到局域网；
8. 依赖安装必须在 `fire` conda 环境中，经用户确认后使用 `python -m pip`；
9. mock 验证、计划完成或页面能启动都不能把能力标记为 `implemented`；
10. 只有主评测真实 Run、自动化测试、浏览器验证和人工字段核对全部通过后才能收口。

## 8. 依赖与执行入口

- Python：`>=3.14,<3.15`；
- conda 环境：`fire`；
- Python 包管理：`python -m pip` 读取 `pyproject.toml`；
- Dashboard 直接依赖：`streamlit>=1.58.0,<2.0`；
- 前端包管理：不使用 npm、pnpm 或 yarn；
- 当前任务只维护文档，不执行依赖安装。

实施前必须重新核对 Streamlit 最新官方兼容性和 `fire` 环境实际安装状态。具体安装、TDD、真实验证和 Git 策略见 [Dashboard 实施计划](../project_or_workflow/2026-07-05-ws-rag-evaluation-dashboard-implementation.md)。

## 9. 官方依据

- Streamlit 执行模型与脚本重跑：<https://docs.streamlit.io/get-started/fundamentals/main-concepts>
- `st.session_state` 生命周期与 callback 顺序：<https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state>
- `st.dataframe` 选择事件：<https://docs.streamlit.io/develop/api-reference/data/st.dataframe>
- `st.rerun` 行为与风险：<https://docs.streamlit.io/develop/api-reference/execution-flow/st.rerun>
- Streamlit `AppTest`：<https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest>

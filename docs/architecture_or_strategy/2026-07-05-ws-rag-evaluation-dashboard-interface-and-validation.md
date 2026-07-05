# W-S RAG 评测 Dashboard 界面与验证设计

> 本文是 [Dashboard 设计总览](./2026-07-05-ws-rag-evaluation-dashboard-design.md) 的界面、状态、错误处理、测试与验收分卷。
>
> 数据字段和比较门禁见 [Dashboard 数据契约](./2026-07-05-ws-rag-evaluation-dashboard-data-contract.md)。

## 1. 页面状态模型

Dashboard 是单页 Streamlit 应用。普通控件交互会触发脚本重跑，因此页面必须把已发现的 Run 快照、当前 Run、当前视图、筛选条件和下钻对象保存在 `st.session_state`。

页面状态：

| 状态 | 条件 | 主内容区 |
| --- | --- | --- |
| `empty` | 报告根目录不存在或没有有效 Run | 空目录提示 |
| `ready` | 当前 Run 完整且校验通过 | 四类视图 |
| `invalid_run` | 选中 Run 缺失、损坏或不一致 | 结构化错误提示 |
| `comparison_unavailable` | 首轮只有一个 mock Run | 固定不可比较提示 |
| `refreshing` | 用户主动刷新快照 | spinner，不展示旧新混合状态 |

首次会话加载一次磁盘快照。切换视图、筛选、排序或选择问题时不得重新扫描目录。

## 2. 页面骨架

### 2.1 侧边栏

- 当前 Run 选择器；
- 四个视图入口：总览、文件列表、问题下钻、对比状态；
- “刷新报告”按钮；
- 当前 Run 的 `created_at`、生成模型、Judge 模型、代码 commit、dataset ID；
- 本机调试工具提示。

页面显示名称使用目录名，数据契约要求它与 `run_id` 一致。

### 2.2 主内容区

- 顶部固定显示视图标题和当前 Run；
- 正常状态展示业务内容；
- 无结果时显示“暂无数据”；
- 报告不可用时显示文件路径、失败类别、简短原因和恢复建议；
- 不展示原始 JSON dump。

## 3. 视图一：总览

用途：快速判断本轮是否可接受，以及主要问题集中在哪里。

| 区域 | 内容 |
| --- | --- |
| 关键数字 | 文件数、问题数、Overall Pass Rate、失败问题数、红线失败数 |
| 评测元信息 | dataset、protocol、代码 commit、模型、top-k、语料指纹 |
| 指标表 | 六项报告指标、当轮阈值和达标状态 |
| 文件状态分布 | 通过、普通失败、红线失败数量 |
| 失败原因 Top | 按稳定 `failure_reasons[].code` 聚合 |
| 执行错误摘要 | `errors.json` 数量和阶段分布 |

Dashboard 直接显示报告结果。若一致性校验发现摘要与明细不一致，整个 Run 进入 `invalid_run`，不得挑选其中一套数字继续展示。

图表优先使用 Streamlit 自带的 Altair 接口，不引入 Plotly 直接依赖。

## 4. 视图二：文件列表

表格列：

- 标题、`document_id`；
- 问题数、失败问题数、红线失败数；
- 文件状态；
- Overall Pass Rate；
- 六项指标。

交互：

- 表头排序；
- 只看失败、只看红线、按某指标未达标筛选；
- 使用 `st.dataframe(on_select="rerun", selection_mode="single-row")` 选择文件；
- 同时提供稳定的文件选择器作为兜底，因为表格排序会重置行选择；
- 选中文件后写入 `st.session_state`，跳转到问题下钻。

状态颜色：

- 绿色：文件内所有问题通过且无红线；
- 黄色：存在普通失败但无红线；
- 红色：存在任一红线代码。

颜色不是唯一信息，必须同时显示中文状态文本。

## 5. 视图三：问题下钻

采用三栏布局：

1. 问题列表与筛选；
2. 问题结果和失败原因；
3. 检索证据与引文绑定。

### 5.1 问题列表

- 显示问题文本、问题类型、通过状态和红线标记；
- 支持只看失败、只看红线和按问题类型筛选；
- 选择变化写入 `st.session_state`。

### 5.2 问题结果

- `passed` 和 `red_line_failures`；
- 六项 `scores` 及本轮阈值；
- `failure_reasons` 的稳定代码、中文说明、观测值与阈值；
- RAG 答案、是否拒答和 `uncertainty`；
- `expected_article` 与问题生成来源。

### 5.3 证据与引文

每个 `retrieved_chunks[]` 显示：

- chunk ID、条文路径和检索分数；
- chunk 原文；
- 是否被引用。

每个 `citations[]` 显示条文路径、引文文本和 `matched_chunk_id`。页面只展示契约已经绑定的关系，不自行通过字符串匹配推断引文。

当存在红线代码时，仅在当前问题附近显示对应中文说明；不在没有红线的页面堆叠全部规则。

## 6. 视图四：不可比较状态

首轮只存在一个合法 mock Run，不提供 Baseline 和 Current 选择器。

展示：

- “当前只有一个 Run，暂无可比较对象”；
- 当前 Run ID、dataset ID、dataset fingerprint 和 protocol fingerprint；
- 未来比较要求的简短说明。

不得显示差值、变化箭头、红绿高亮、修复/新增失败或“变好/变差”结论。双 Run 比较属于未来扩展，兼容条件继续由数据契约定义。

## 7. 显式刷新

刷新流程：

1. 点击按钮触发 callback；
2. callback 在脚本主体重新执行前扫描并校验 Run；
3. 只有新快照整体构建成功后才替换 `st.session_state` 中的旧快照；
4. 当前 Run 仍存在时保留选择，否则选择最新有效 Run；
5. 使用 `st.spinner("刷新中…")` 表达进行中状态；
6. 不额外调用 `st.rerun()`，除非实现证据表明 callback 后的正常重跑不足。

页面不得承诺在同步 callback 运行期间把同一个按钮即时变成 disabled；核心验收是不会重复扫描和不会展示旧新混合数据。

## 8. 错误与空状态

### 8.1 空目录

- Run 选择器显示“无可用报告”；
- 主内容显示“你还没有任何评测结果，先去评测一下吧”；
- 不抛 traceback。

### 8.2 不可用 Run

错误类别：

| 类别 | 页面提示要点 |
| --- | --- |
| 文件缺失 | 缺少 `report.json` 或 `errors.json` |
| JSON 语法错误 | 文件无法解析 |
| schema 不支持 | 显示实际和支持的版本 |
| 字段校验失败 | 显示字段路径和简要原因 |
| 跨文件不一致 | 显示 `run_id`、版本或时间不匹配 |
| 跨字段不一致 | 显示计数、指标或引用关系错误 |

任一类别都不得展示该 Run 的部分业务内容，也不得自动改写文件。

### 8.3 安全边界

- 忽略符号链接和根目录外路径；
- 用户文本使用 Streamlit 默认转义，不启用不安全 HTML；
- 页面不显示凭据、header、完整 prompt 或 traceback；
- 服务默认绑定 `127.0.0.1`；
- 页面明确标记“本机评测调试工具”。

## 9. 依赖与运行

| 环境 | 包管理工具 | 依赖 |
| --- | --- | --- |
| Python | conda 环境 `fire` + `python -m pip` | `streamlit>=1.58.0,<2.0` |
| 测试 | `python -m pytest` | 沿用 `.[dev]` |
| 前端 | 不使用 npm/pnpm/yarn | 无 |
| 浏览器验证 | 优先使用已有浏览器能力 | 不为本计划私自安装 Playwright |

建议启动命令：

```bash
conda run -n fire python -m streamlit run scripts/eval_ws_rag/dashboard.py --server.address 127.0.0.1
```

命令意图：只在本机启动 Dashboard。
预期输出：控制台给出本机访问地址，且无 import 或 schema 错误。

## 10. 测试矩阵

### 10.1 共享 schema 与 loader

- 正常 Run；
- 缺失文件、损坏 JSON、未知 major；
- 目录名和 `run_id` 不一致；
- summary/documents/questions 计数不一致；
- 引文绑定不存在的 chunk；
- 暂存目录、隐藏目录和符号链接被忽略；
- 唯一合法 mock Run 可被加载；
- 对比状态固定为不可用。

### 10.2 Streamlit `AppTest`

- 页面首次加载和四视图入口；
- 空目录和不可用 Run 提示；
- Run、文件、问题选择写入 session state；
- 普通筛选不重新扫描磁盘；
- 显式刷新替换快照并保留或回退当前选择；
- 单 Run 对比状态不出现差值和方向结论。

每次修改 widget 值后必须显式调用 `AppTest.run()`。不要把 AppTest 未覆盖的浏览器布局行为误报为已验证。

### 10.3 浏览器烟雾验证

- 服务仅监听 `127.0.0.1`；
- 四类视图可达；
- 三栏布局在目标桌面宽度下不遮挡；
- 表格排序、选择器兜底和视图跳转可用；
- 总览数字和 fixture 原值一致；
- 页面没有 traceback、敏感信息和不安全 HTML。

### 10.4 单个 mock Run 核对

只使用一份共享 schema 合法 fixture，至少核对：

- Run 数量严格为 1；
- 顶层 summary；
- 文件行数和状态；
- 一个通过问题、一个普通失败和一个红线失败；
- 检索证据、引文绑定和错误报告；
- 对比视图固定显示不可比较状态。

## 11. 完成定义

只有同时满足以下条件，本轮 Dashboard 才能标记为 `mock_mvp`：

- 唯一 mock Run 已按共享契约通过校验；
- schema/loader 单元测试和 `AppTest` 全部通过；
- 仓库完整回归无新增失败；
- 浏览器烟雾验证通过；
- mock Run 字段级核对通过；
- Dashboard 与主评测执行计划的交叉依赖已经收口；
- 索引、读取规则、能力路线图和实际状态一致。

`mock_mvp` 不代表 Dashboard 能力已经 `implemented`；真实 Run 和双 Run 比较留待未来独立验收。

具体 TDD Task、命令、预期失败、真实验证和中文 commit 策略见 [Dashboard 实施计划](../project_or_workflow/2026-07-05-ws-rag-evaluation-dashboard-implementation.md)。

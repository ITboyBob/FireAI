# 项目学习路线

**基础**

- Agent 工程化核心概念；理解 **Agent**、**Runner**、**Model**、**Tool**、**Session**、**Memory**、**Graph** 等基础抽象，以及一次 Agent 调用从用户输入到事件流输出的完整链路。
- 跑通 Python / Go Quickstart；基于 **LlmAgent**、**Runner** 和模型配置，完成一个支持多轮对话与流式输出的基础 Agent。
- Function Calling 与工具调用；学习如何把普通函数封装为 **FunctionTool**，理解工具 schema、入参、返回值、错误处理以及模型触发工具调用的过程。
- Session 会话管理；掌握消息、状态、事件、token usage 的管理方式，理解 InMemory、Redis、SQL 等不同会话后端的适用场景。

**进阶**

- Memory 与 Knowledge / RAG；学习长期记忆的写入、检索、召回和个性化信息沉淀；理解知识库的文档加载、切分、向量化、检索和提示词拼接流程。
- 多 Agent 协作与图编排；掌握 Chain、Parallel、Cycle、TeamAgent、GraphAgent 等编排方式，理解节点、边、条件路由、状态 reducer、checkpoint、interrupt / resume 等机制。
- MCP、A2A 与 AG-UI 协议；理解 Agent 如何接入外部工具服务、与其他 Agent 互通、向前端输出结构化事件，并通过 FastAPI、Gateway Server 或 Go Server 暴露为线上服务。
- Skills 与 CodeExecutor；学习 `SKILL.md` 的技能描述方式，理解 skill load / run、workspace runtime、本地执行、容器执行、Cube / E2B 沙箱执行的安全边界。
- 评测、优化与可观测性；掌握 Eval set、metric、LLM Judge、rubric evaluator、prompt iteration、AgentOptimizer、OpenTelemetry、Langfuse、token usage、延迟和错误率等生产级 Agent 分析能力。

**实战**

- 构建一个支持工具调用和多轮对话的基础助手；例如天气查询、搜索、文件处理、计算器、时间查询等工具型 Agent。
- 构建一个基于知识库的 RAG 问答 Agent；完成文档加载、向量检索、上下文拼接、多轮追问和答案生成。
- 使用 Redis 或 SQL 持久化 Session；验证多轮会话恢复、历史裁剪、会话摘要和 token usage 统计。
- 编写并调用一个自定义 Skill；通过 **SKILL.md** 封装可复用任务能力，并让 Agent 在运行过程中调用。
- 将 Agent 服务化；通过 MCP、A2A、AG-UI 或 FastAPI / Gateway Server，把本地 Agent 变成可被前端、工具平台或其他 Agent 调用的服务。

**进阶挑战**

- 多 Agent 企业知识助手；构建一个"企业知识助手"，支持多轮对话、工具调用、知识库检索、长期记忆、任务拆解、流式前端事件和运行日志。
- 研发自动化助手；结合 Skills、CodeExecutor、MCP 工具和 Session / Memory，完成需求分析、代码检索、任务拆解、执行反馈和结果总结。
- GraphAgent 工作流编排；用条件路由、状态 reducer、checkpoint、interrupt / resume 实现审批、诊断、规划或多步骤任务执行流程。
- Agent 评测体系建设；为 Agent 增加 evaluation cases、LLM Judge、rubric 指标和 tracing，通过数据比较不同 prompt、模型和工具策略的效果。

**学习资源**

**项目文档与源码**

- tRPC-Agent-Python 仓库 README 与 examples/ 示例
- tRPC-Agent-Go 仓库 README 与基础 Agent、GraphAgent、Server 示例
- docs/ 文档：Session、Memory、Knowledge、Tools、MCP、A2A、AG-UI、Evaluation、Observability

**推荐阅读路径**

- Quickstart：先跑通 Python 或 Go 的最小 Agent
- Tools：学习 FunctionTool、MCPToolset、Streaming Tool 和 Agent-as-Tool
- Session / Memory / Knowledge：理解短期上下文、长期记忆和外部知识
- Multi-Agent / GraphAgent：学习链式、并行、循环和图编排
- Server / Protocols：学习 MCP、A2A、AG-UI 和服务化部署
- Evaluation / Observability：学习评测、日志、tracing、metrics 和质量优化

**学习成果验收**

完成学习后，建议交付一个综合项目：企业知识助手或研发自动化助手。

项目应至少包含：多轮对话、工具调用、知识库检索、长期记忆、任务拆解、流式事件输出、运行日志、评测集和一种服务化协议。

如果学习者能够清楚解释一次 Agent 运行中的模型输入、工具调用、状态变化、记忆召回、事件输出和评测结果，就说明已经从"使用 Agent 框架"进入到"理解 Agent 工程系统"的阶段。

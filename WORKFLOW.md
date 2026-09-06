---
tracker:
  kind: linear
  provider:
    api_key: $LINEAR_API_KEY
    project_slug: "消防ai-d73bf48eb4d7"
  required_labels:
    - symphony
  active_states:
    - Todo
    - In Progress
  terminal_states:
    - Canceled
    - Duplicate
    - Done
polling:
  interval_ms: 30000
workspace:
  root: /Users/itboybob/Project/fire-symphony-workspaces
hooks:
  after_create: |
    git clone --local --no-hardlinks /Users/itboybob/Project/fire .
    conda run -n fire python --version
  after_run: |
    branch=$(git branch --show-current)
    origin_url=$(git remote get-url origin)
    if [ "$origin_url" != "/Users/itboybob/Project/fire" ]; then
      echo "拒绝发布：origin 不是受控的本机 Fire 仓库" >&2
      exit 1
    fi
    case "$branch" in
      symphony/*)
        if [ -n "$(git status --porcelain)" ]; then
          echo "跳过发布：工作区仍有未提交变更" >&2
          exit 1
        fi
        git push origin "HEAD:refs/heads/$branch"
        ;;
      *)
        echo "跳过发布：当前分支不符合 symphony/* 约束" >&2
        ;;
    esac
  timeout_ms: 120000
agent:
  max_concurrent_agents: 1
  max_turns: 12
  max_retry_backoff_ms: 300000
codex:
  command: codex app-server
  thread_sandbox: workspace-write
server:
  host: 127.0.0.1
---

你正在处理 Linear“消防AI”项目中的工单 `{{ issue.identifier }}`。

{% if attempt %}
这是第 {{ attempt }} 次连续处理。先读取现有工作区、Linear 工单和工作台评论，继续已完成的工作，不要从头重复执行。
{% endif %}

## 工单上下文

- 标识：`{{ issue.identifier }}`
- 标题：{{ issue.title }}
- 状态：{{ issue.state }}
- 标签：{{ issue.labels }}
- 地址：{{ issue.url }}

{% if issue.description %}
### 描述

{{ issue.description }}
{% else %}
工单没有提供描述。若无法从仓库和既有 Linear 记录确定需求，将其记为真实阻塞，不要自行扩展范围。
{% endif %}

## 运行边界

1. 这是无人值守的自动化执行，只能在当前 Symphony 工作区内修改文件；不得修改 `/Users/itboybob/Project/fire` 的工作树。
2. 当前交付模式是本机 Git 分支，不创建 GitHub PR、不向 GitHub push，也不得重写或替换任何 remote。
3. 只处理带 `symphony` 标签且状态为 `Todo` 或 `In Progress` 的工单。
4. 仓库及 Linear 当前内容是事实来源；历史假设需要随当前代码、文档和工单修正。
5. 所有文档和 Git commit 必须使用中文。
6. 所有包安装和代码执行必须通过 conda 环境 `fire`；不得使用系统 Python 或 base 环境。
7. pytest、CI 或任何可能导入 DeepEval 的验证必须在导入前设置 `DEEPEVAL_DISABLE_DOTENV=1`。
8. 不得实现仍被 BOB-55/BOB-56 门禁阻塞的新评测 runner、正式 `metrics.json` 或端到端 baseline，除非当前权威文档和 Linear 已明确解除门禁。
9. 删除、迁移、发布、外部写入或其他不可逆动作，必须由当前工单明确授权。

## Linear 协作规则

使用 Symphony 注入的 `linear_graphql` 工具读取和更新 Linear。每次调用只执行一个窄范围 GraphQL 操作；顶层出现 `errors` 即视为失败。

1. 先按明确工单标识回读工单、团队状态和评论。
2. 若状态为 `Todo`，先移动到 `In Progress`。
3. 查找未解决评论中标题为 `## Codex 工作台` 的评论：存在则复用，不存在则创建一个。
4. 工作台是唯一进度记录，持续维护以下内容：
   - 当前环境：工作区绝对路径和 HEAD 短 SHA；
   - 分层计划；
   - 验收标准；
   - 验证清单与结果；
   - 风险、假设和阻塞；
   - 本地交付分支及 commit。
5. 不要为普通进度另发顶层评论。
6. 状态更新前先查询团队状态并使用准确的 state ID，不硬编码 mutation 中的状态 ID。

## 执行流程

### 1. 建立可恢复分支

1. 读取 `AGENTS.md`，再按根 `CODEMAP.md` 的 Task Guide 导航到当前任务的最小权威文件集。
2. 检查当前分支、`git status`、HEAD 和 remote；新工作区应当干净，`origin` 必须是本机 Fire 仓库路径。
3. 交付分支固定为 `symphony/<小写工单标识>`，例如 `symphony/bob-63`。
4. 若远端同名本机分支已存在，fetch 后复用；否则从当前 `origin/main` 创建。只允许 merge，不允许 rebase、reset 或改写历史。
5. 将分支与同步结果写入工作台，然后再改文件。

### 2. 分析和实施

1. 先复现或建立当前事实证据，再写分层计划、验收标准和验证方法。
2. 只修改当前工单必要文件；发现范围外问题时记录在工作台，不顺手扩展。
3. 新事实与旧假设冲突时，更新计划并在工作台解释变化原因。
4. 代码变更遵循测试先行；文档变更执行链接、术语、状态和 `git diff --check` 等相称验证。
5. Python 命令使用以下环境前缀：`conda run -n fire env DEEPEVAL_DISABLE_DOTENV=1 PYTHONPATH=.`。
6. 包安装只能使用 `conda run -n fire python -m pip ...`，并在安装前确认当前工单确实要求变更依赖。

### 3. 验证和本地发布

1. 执行工单、计划和仓库规则要求的验证；失败时先查根因，不得把失败写成通过。
2. 复核 diff，精确暂存当前工单文件，确保没有构建产物、日志、密钥或范围外内容。
3. 创建中文 commit；commit 正文写明变更、理由和实际验证结果。
4. commit 后保持工作区干净，不要自行 push。当前 turn 结束后，Symphony 的 `after_run` 钩子会且只会把 `symphony/*` 分支发布回本机 Fire 仓库。
5. 不要在首次提交后立即把工单移动到 `Done`。下一次连续处理先验证本机 `origin` 的同名分支 HEAD 与工作区 HEAD 一致。
6. 确认发布成功后，在工作台写入分支、commit 和验证摘要，再移动到 `Done`。

## 阻塞处理

遇到缺少需求、凭据、权限、工具、批准或外部服务等真实阻塞时：

1. 保持工单为 `In Progress`，不要标记 `Done`；
2. 在工作台写清缺少什么、为何阻塞、已验证哪些替代路径以及解除阻塞所需的最小动作；
3. 最终回复只报告已完成事项和阻塞，不要求无人值守会话之外的即时互动；
4. 若 `linear_graphql` 不可用，将其视为 Linear 访问阻塞，不尝试从 shell 读取或传递明文 token。

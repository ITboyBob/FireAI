#!/bin/zsh

set -euo pipefail

readonly symphony_root="/Users/itboybob/Symphony/elixir"
readonly workflow_path="/Users/itboybob/Project/fire/WORKFLOW.md"
readonly logs_root="${symphony_root}/log/fire"
readonly dashboard_port="${SYMPHONY_PORT:-4400}"

if [[ -z "${LINEAR_API_KEY:-}" ]]; then
  if [[ ! -t 0 ]]; then
    print -u2 "缺少 LINEAR_API_KEY；请在交互式终端运行或预先导出该变量。"
    exit 2
  fi

  read -r -s "LINEAR_API_KEY?请输入 Linear Personal API Key："
  print
  export LINEAR_API_KEY
fi

if [[ -z "${LINEAR_API_KEY}" ]]; then
  print -u2 "LINEAR_API_KEY 不能为空。"
  exit 2
fi

cd "${symphony_root}"

exec mise exec -- ./bin/symphony \
  --i-understand-that-this-will-be-running-without-the-usual-guardrails \
  --logs-root "${logs_root}" \
  --port "${dashboard_port}" \
  "${workflow_path}"

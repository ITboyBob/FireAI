from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.eval_ws_rag.baseline import BaselineError, compare_runs, load_baseline

LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="比较两次 W-S RAG 评测 Run，要求属于同一 dataset 与 protocol。"
    )
    parser.add_argument(
        "--baseline-run",
        type=Path,
        required=True,
        help="基线 run 目录（例如 reports/ws_rag_eval/run_001）。",
    )
    parser.add_argument(
        "--current-run",
        type=Path,
        default=None,
        help="当前 run 目录；省略时仅显示 baseline 信息。",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/eval/ws_rag_baselines.json"),
        help="baseline registry 路径。",
    )
    parser.add_argument(
        "--baseline-name",
        default=None,
        help="从 registry 读取 baseline run 路径，与 --baseline-run 互斥。",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    baseline_run = args.baseline_run
    if args.baseline_name:
        try:
            entry = load_baseline(name=args.baseline_name, registry_path=args.registry)
            baseline_run = Path(entry["run_path"])
        except BaselineError as exc:
            LOGGER.error("%s", exc)
            return 1

    if args.current_run is None:
        LOGGER.info("仅存在 baseline Run，等待 current Run 后再进行方向性比较。")
        LOGGER.info("baseline_run: %s", baseline_run)
        return 0

    try:
        result = compare_runs(
            baseline_run_dir=baseline_run,
            current_run_dir=args.current_run,
        )
    except BaselineError as exc:
        LOGGER.error("比较失败: %s", exc)
        return 1

    if not result["comparable"]:
        LOGGER.error("两次 Run 非同口径，不可计算方向变化:")
        for reason in result["reasons"]:
            LOGGER.error("  - %s", reason)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

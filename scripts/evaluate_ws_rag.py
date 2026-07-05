from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Allow direct execution as `python scripts/evaluate_ws_rag.py` by adding the repo root.
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from scripts.eval_ws_rag.orchestrator import FatalEvaluationError, load_config, run_evaluation, write_debug_bundle
from scripts.eval_ws_rag.runtime_config import load_runtime_config

LOGGER = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="执行 W-S1/W-S2 Word 法规 RAG 端到端评测，生成不可变 run 目录。"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="已持久化的 dataset.json 路径。",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="本次 run 的唯一标识，将用作 reports/ws_rag_eval/<run_id> 目录名。",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="显示当前运行配置摘要（不含 API Key）并退出，不执行评测。",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="数据根目录，默认 data。",
    )
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=Path("reports/ws_rag_eval"),
        help="评测报告根目录，默认 reports/ws_rag_eval。",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("scripts/eval_ws_rag/config.json"),
        help="评测运行时配置文件路径。",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )

    if args.show_config:
        try:
            runtime_cfg = load_runtime_config(args.config)
        except Exception as exc:
            LOGGER.error("加载运行配置失败: %s", exc)
            return 1
        print(json.dumps(runtime_cfg.non_secret_summary(), ensure_ascii=False, indent=2))
        return 0

    if not args.dataset or not args.run_id:
        parser.error("--dataset 和 --run-id 是必填参数")

    if not args.dataset.exists():
        LOGGER.error("dataset 不存在: %s", args.dataset)
        return 1

    try:
        config = load_config(args.config)
    except Exception as exc:
        LOGGER.error("加载配置文件失败: %s", exc)
        return 1

    # Surface configured model identities without printing secrets.
    answer_model = os.environ.get("CHAT_MODEL", "<未设置>").strip()
    judge_model = os.environ.get("WS_RAG_JUDGE_MODEL", "<未设置>").strip()

    try:
        result = run_evaluation(
            dataset_path=args.dataset,
            run_id=args.run_id,
            data_dir=args.data_dir,
            reports_root=args.reports_root,
            config=config,
        )
    except FatalEvaluationError as exc:
        debug_path = write_debug_bundle(args.run_id, exc.evaluation_error)
        LOGGER.error("评测致命失败，已写入 debug: %s", debug_path)
        LOGGER.error("错误阶段: %s | %s", exc.evaluation_error.stage, exc.evaluation_error.message)
        return 1
    except Exception as exc:
        LOGGER.error("评测发生未预期错误: %s", exc)
        return 1

    LOGGER.info("run_id: %s", result.report.run_id)
    LOGGER.info("dataset_id: %s", result.report.dataset.dataset_id)
    LOGGER.info("dataset_fingerprint: %s", result.report.dataset.dataset_fingerprint)
    LOGGER.info("answer_model: %s", result.report.protocol.answer_model)
    LOGGER.info("judge_model: %s", result.report.protocol.judge_model)
    LOGGER.info("protocol_fingerprint: %s", result.report.protocol.protocol_fingerprint)
    LOGGER.info("published run: %s", result.run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

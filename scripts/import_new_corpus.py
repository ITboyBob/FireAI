import argparse
import json
from pathlib import Path
import sys
import uuid


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import Settings
from app.services.corpus_ingestor import build_document_id
from app.services.embedder import SentenceTransformerEmbedder
from app.services.incremental_import import IncrementalImportError, run_incremental_import
from app.services.legal_ingestion_batch import BatchFileResult, FileState, load_batch_report, save_batch_report


def _parse_source_path(value: str) -> Path:
    return Path(value.strip()).expanduser()


def _parse_manifest_path(value: str) -> Path:
    path = Path(value.strip()).expanduser()
    if not path.exists():
        raise argparse.ArgumentTypeError(f"批次清单不存在: {path}")
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"批次清单必须是文件: {path}")
    return path


def _resolve_manifest_sources(
    manifest_path: Path,
    source_root: Path | None,
    extraction_class: str,
    content_class: str,
) -> list[Path]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise IncrementalImportError("批次清单必须是条目数组")

    root = (source_root if source_root is not None else manifest_path.parent).resolve()
    selected: list[Path] = []
    for item in raw:
        if not isinstance(item, dict):
            raise IncrementalImportError("批次清单条目必须是对象")
        if item.get("expected_extraction_class") != extraction_class:
            continue
        if item.get("expected_content_class") != content_class:
            continue
        relative_path = item.get("relative_path")
        if not relative_path:
            raise IncrementalImportError("批次清单条目缺少 relative_path")
        if Path(relative_path).is_absolute():
            raise IncrementalImportError(f"relative_path 必须是相对路径: {relative_path}")
        candidate = (root / relative_path).resolve()
        if not str(candidate).startswith(str(root)):
            raise IncrementalImportError(
                f"relative_path 不允许跳出 source_root: {relative_path}"
            )
        selected.append(candidate)
    return selected


def _sha256_file(path: Path) -> str:
    from hashlib import sha256

    return sha256(path.read_bytes()).hexdigest()


def _build_batch_report_path(data_dir: Path, run_id: str) -> Path:
    return data_dir / "manifests" / "legal_ingestion_batches" / run_id / f"{run_id}.batch.json"


def _exit_code_for_result(result: BatchFileResult) -> int:
    if result.final_state is FileState.REVIEW_REQUIRED:
        return 4
    if result.final_state is FileState.FAILED:
        if result.reason_code and result.reason_code.endswith("_unsupported"):
            return 3
        return 1
    return 0


def _print_single_summary(summary: object) -> None:
    print(f"run_id={summary.run_id}")
    print(f"documents={','.join(summary.committed_document_ids)}")
    print(f"chunks={summary.total_chunks}")
    print(f"manifest={summary.manifest_path}")
    print("warning=第一版只做机械冲突检测；语义重复法规无法只靠文件名或 hash 完整识别")


def _print_batch_summary(
    *,
    run_id: str,
    selected: int,
    results: tuple[BatchFileResult, ...],
    batch_report_path: Path,
) -> int:
    counts = {
        "committed": 0,
        "auto_passed": 0,
        "review_required": 0,
        "failed": 0,
        "unsupported": 0,
        "discovered": 0,
    }
    exit_code = 0
    for result in results:
        exit_code = max(exit_code, _exit_code_for_result(result))
        value = result.final_state.value
        if value in counts:
            counts[value] += 1
        if value == "failed" and result.reason_code and result.reason_code.endswith("_unsupported"):
            counts["unsupported"] += 1

    print(f"batch_id={run_id}")
    print(f"selected={selected}")
    print(f"committed={counts['committed']}")
    print(f"auto_passed={counts['auto_passed']}")
    print(f"review_required={counts['review_required']}")
    print(f"failed={counts['failed']}")
    print(f"unsupported={counts['unsupported']}")
    print(f"discovered={counts['discovered']}")
    print(f"batch_report={batch_report_path}")
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="显式导入全新法规文件或批次",
        exit_on_error=False,
    )
    parser.add_argument(
        "source_path",
        nargs="?",
        type=_parse_source_path,
        help="新增法规 .doc/.docx 文件路径；推荐使用绝对路径",
    )
    parser.add_argument(
        "--source",
        dest="source_options",
        action="append",
        default=[],
        type=_parse_source_path,
        help="新增法规 .doc/.docx 文件路径；兼容旧写法，第一版只允许传入一次",
    )
    parser.add_argument(
        "--batch-manifest",
        dest="batch_manifest",
        type=_parse_manifest_path,
        default=None,
        help="显式批次清单 JSON 路径；默认只处理 expected_extraction_class=W 且 expected_content_class=S1 的条目",
    )
    parser.add_argument(
        "--source-root",
        dest="source_root",
        type=_parse_source_path,
        default=None,
        help="批次清单中 relative_path 的解析根目录；默认使用清单所在目录",
    )
    parser.add_argument(
        "--extraction-class",
        dest="extraction_class",
        type=str,
        choices=["W", "PT", "PS", "PX"],
        default="W",
        help="批次清单筛选的提取策略轴；默认 W（Word 直接提取）",
    )
    parser.add_argument(
        "--content-class",
        dest="content_class",
        type=str,
        choices=["S1", "S2", "S3", "S4"],
        default="S1",
        help="批次清单筛选的内容类型轴；默认 S1（单一颁布文本）",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="只生成质量报告和批次报告，不写入正式语料、索引和 manifest",
    )
    parser.add_argument(
        "--verify-source-only",
        dest="verify_source_only",
        action="store_true",
        help="只校验源文件存在并输出 selected 数量",
    )
    parser.add_argument(
        "--run-id",
        dest="run_id",
        type=str,
        default=None,
        help="批次或单文件运行 ID；省略则自动生成 UUID",
    )
    try:
        args = parser.parse_args(argv)
    except argparse.ArgumentError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    has_single_source = args.source_path is not None or args.source_options
    has_batch = args.batch_manifest is not None
    has_class_filter = args.extraction_class != "W" or args.content_class != "S1"

    if has_single_source and has_batch:
        print("单文件参数与 --batch-manifest 互斥", file=sys.stderr)
        return 2
    if args.dry_run and not has_batch:
        print("--dry-run 只能与 --batch-manifest 一起使用", file=sys.stderr)
        return 2
    if args.verify_source_only and not has_batch:
        print("--verify-source-only 只能与 --batch-manifest 一起使用", file=sys.stderr)
        return 2
    if has_single_source and has_class_filter:
        print("单文件参数与 --extraction-class/--content-class 互斥", file=sys.stderr)
        return 2

    run_id = args.run_id or str(uuid.uuid4())
    settings = Settings()

    if has_batch:
        try:
            sources = _resolve_manifest_sources(
                args.batch_manifest,
                args.source_root,
                extraction_class=args.extraction_class,
                content_class=args.content_class,
            )
        except (IncrementalImportError, json.JSONDecodeError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2

        missing = [path for path in sources if not path.exists()]
        if missing:
            print(f"批次清单中的源文件缺失: {missing[0]}", file=sys.stderr)
            return 1

        batch_report_path = _build_batch_report_path(settings.data_dir, run_id)

        if args.verify_source_only:
            results: list[BatchFileResult] = []
            for path in sources:
                document_id = build_document_id(path.stem)
                attempt_id = f"{run_id}-{document_id}"
                results.append(
                    BatchFileResult(
                        relative_path=str(path),
                        source_sha256=_sha256_file(path),
                        document_id=document_id,
                        attempt_id=attempt_id,
                        final_state=FileState.DISCOVERED,
                    )
                )
            report = save_batch_report(
                batch_report_path,
                batch_id=run_id,
                source_root=args.source_root or args.batch_manifest.parent,
                results=tuple(results),
            )
            return _print_batch_summary(
                run_id=run_id,
                selected=len(sources),
                results=report.results,
                batch_report_path=batch_report_path,
            )

        if not settings.embedding_model_name and not args.dry_run:
            print("未配置 EMBEDDING_MODEL_NAME，无法更新真实向量索引。", file=sys.stderr)
            return 1

        embedder = (
            object()
            if args.dry_run
            else SentenceTransformerEmbedder(
                model_name_or_path=settings.embedding_model_name,
                device=settings.embedding_device,
                batch_size=settings.embedding_batch_size,
                max_seq_length=settings.embedding_max_seq_length,
            )
        )

        try:
            summary = run_incremental_import(
                sources=sources,
                data_dir=settings.data_dir,
                index_dir=settings.index_dir,
                manifest_path=settings.manifests_dir / "incremental_imports.json",
                staging_root=settings.incremental_staging_dir,
                embedder=embedder,
                run_id=run_id,
                dry_run=args.dry_run,
                force_batch=True,
            )
        except IncrementalImportError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if summary.batch_report_path is None:
            print("批次报告路径缺失", file=sys.stderr)
            return 1

        report = load_batch_report(summary.batch_report_path)
        return _print_batch_summary(
            run_id=summary.run_id,
            selected=len(sources),
            results=report.results,
            batch_report_path=summary.batch_report_path,
        )

    sources: list[Path] = []
    if args.source_path is not None:
        sources.append(args.source_path)
    sources.extend(args.source_options)

    if not sources:
        print("必须显式指定新增法规文件", file=sys.stderr)
        return 2
    if len(sources) > 1:
        print("第一版一次只能导入一个法规文件", file=sys.stderr)
        return 2

    if not settings.embedding_model_name:
        print("未配置 EMBEDDING_MODEL_NAME，无法更新真实向量索引。", file=sys.stderr)
        return 1

    embedder = SentenceTransformerEmbedder(
        model_name_or_path=settings.embedding_model_name,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        max_seq_length=settings.embedding_max_seq_length,
    )

    try:
        summary = run_incremental_import(
            sources=sources,
            data_dir=settings.data_dir,
            index_dir=settings.index_dir,
            manifest_path=settings.manifests_dir / "incremental_imports.json",
            staging_root=settings.incremental_staging_dir,
            embedder=embedder,
            run_id=run_id,
        )
    except IncrementalImportError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    _print_single_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

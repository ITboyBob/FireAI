import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import Settings
from app.services.embedder import SentenceTransformerEmbedder
from app.services.incremental_import import IncrementalImportError, run_incremental_import


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="显式导入一个全新法规文件")
    parser.add_argument(
        "source_path",
        nargs="?",
        type=Path,
        help="新增法规 .doc/.docx 文件路径；推荐使用绝对路径",
    )
    parser.add_argument(
        "--source",
        dest="source_options",
        action="append",
        default=[],
        type=Path,
        help="新增法规 .doc/.docx 文件路径；兼容旧写法，第一版只允许传入一次",
    )
    args = parser.parse_args(argv)
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

    settings = Settings()
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
        )
    except IncrementalImportError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"run_id={summary.run_id}")
    print(f"documents={','.join(summary.committed_document_ids)}")
    print(f"chunks={summary.total_chunks}")
    print(f"manifest={summary.manifest_path}")
    print("warning=第一版只做机械冲突检测；语义重复法规无法仅靠文件名或 hash 完整识别")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

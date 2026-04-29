from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

from app.services.corpus_ingestor import CorpusDocument, build_document_id


class IncrementalImportError(RuntimeError):
    pass


def resolve_explicit_sources(paths: Sequence[Path]) -> list[CorpusDocument]:
    if not paths:
        raise IncrementalImportError("必须显式指定新增法规文件")

    documents: list[CorpusDocument] = []
    seen_document_ids: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise IncrementalImportError(f"新增法规文件不存在: {path}")
        if path.is_dir():
            raise IncrementalImportError("第一版不支持目录自动扫描")

        file_type = path.suffix.lower().lstrip(".")
        if file_type not in {"doc", "docx"}:
            raise IncrementalImportError("第一版只支持 .doc/.docx 法规文件")

        source_name = path.stem
        document_id = build_document_id(source_name)
        if document_id in seen_document_ids:
            raise IncrementalImportError(f"同一次导入存在重复 document_id: {document_id}")
        seen_document_ids.add(document_id)

        documents.append(
            CorpusDocument(
                document_id=document_id,
                source_path=path,
                source_name=source_name,
                file_type=cast(Literal["doc", "docx"], file_type),
            )
        )

    return documents

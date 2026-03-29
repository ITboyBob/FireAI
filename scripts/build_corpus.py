import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.settings import Settings
from app.services.chunk_builder import build_chunks, write_chunks
from app.services.corpus_ingestor import discover_documents
from app.services.normalizer import normalize_document
from app.services.structure_parser import parse_legal_document, write_structured_document


def main() -> int:
    settings = Settings()
    documents = discover_documents(settings.raw_corpus_dir)

    normalized_dir = settings.data_dir / "normalized"
    structured_dir = settings.data_dir / "structured"
    chunks_dir = settings.data_dir / "chunks"

    failures: list[str] = []

    for document in documents:
        result = normalize_document(document, normalized_dir)
        if result.output_path is None:
            failures.append(f"{document.document_id}: {result.error_message}")
            continue

        raw_text = result.output_path.read_text(encoding="utf-8")
        parsed = parse_legal_document(document.document_id, raw_text)
        structured_path = write_structured_document(parsed, structured_dir)
        chunks = build_chunks(
            {
                "document_id": parsed.document_id,
                "title": parsed.title,
                "issuing_authority": parsed.issuing_authority,
                "region": parsed.region,
                "promulgated_on": parsed.promulgated_on,
                "effective_on": parsed.effective_on,
                "articles": [
                    {
                        "article_no": article.article_no,
                        "chapter_title": article.chapter_title,
                        "heading_path": list(article.heading_path),
                        "text": article.text,
                    }
                    for article in parsed.articles
                ],
            }
        )
        chunk_path = write_chunks(chunks, document.document_id, chunks_dir)
        print(f"{document.document_id}: {structured_path} -> {chunk_path}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

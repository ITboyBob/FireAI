from pathlib import Path

from app.services.legal_ingestion_inventory import freeze_batch_input, select_scope
from app.services.legal_ingestion_models import (
    ContentClass,
    ExtractionClass,
    IngestionDisposition,
    IngestionInput,
)
from app.services.legal_ingestion_orchestrator import LegalIngestionOrchestrator
from app.services.legal_source_classifier import classify_source
from app.services.legal_strategy_registry import (
    BoundaryStrategyRegistry,
    CapabilityStatus,
    ExtractionStrategyRegistry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"


def _relative_tree(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    return tuple(
        sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    )


def test_real_ws1_records_resolve_independent_unsupported_strategy_keys():
    batch = freeze_batch_input(TODO_ROOT)
    word_records = tuple(
        classify_source(source)
        for source in batch.sources
        if source.declared_extension in {".doc", ".docx"}
    )
    ws1_records = select_scope(
        word_records,
        extraction_class=ExtractionClass.W,
        content_class=ContentClass.S1,
    )
    record_by_path = {
        record.source.relative_path: record for record in ws1_records
    }
    extraction_registry = ExtractionStrategyRegistry()
    boundary_registry = BoundaryStrategyRegistry()
    staging_root = PROJECT_ROOT / "data" / ".staging"
    staging_before = _relative_tree(staging_root)

    for record in ws1_records:
        orchestrator = LegalIngestionOrchestrator(
            classifier=lambda source, path=record.source.relative_path: record_by_path[
                path
            ],
            extraction_registry=extraction_registry,
            boundary_registry=boundary_registry,
        )
        outcome = orchestrator.prepare(
            IngestionInput(single_source=record.source),
            run_id="real-contract",
        )[0]

        assert outcome.disposition is IngestionDisposition.UNSUPPORTED
        assert outcome.extraction_class is ExtractionClass.W
        assert outcome.content_class is ContentClass.S1
        assert extraction_registry.resolve(ExtractionClass.W).status is (
            CapabilityStatus.UNSUPPORTED
        )
        assert boundary_registry.resolve(ContentClass.S1).status is (
            CapabilityStatus.UNSUPPORTED
        )

    assert len(ws1_records) == 8
    assert staging_before == _relative_tree(staging_root)

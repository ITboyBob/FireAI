import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.services.legal_ingestion_batch import load_batch_report
from app.services.legal_ingestion_orchestrator import run_legal_ingestion


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TODO_ROOT = PROJECT_ROOT / "法律文本" / "todo"
BASELINE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "legal_ingestion" / "todo_baseline.json"
)


def _load_ws2_cases() -> list[dict]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return [
        item
        for item in baseline
        if item["expected_extraction_class"] == "W"
        and item["expected_content_class"] == "S2"
    ]


@pytest.mark.parametrize("case", _load_ws2_cases(), ids=lambda c: c["relative_path"])
def test_ws2_legal_corpus_quality_passes(case: dict, tmp_path: Path) -> None:
    source_path = TODO_ROOT / case["relative_path"]
    assert source_path.exists(), f"缺失真实源文件: {case['relative_path']}"

    before_digest = sha256(source_path.read_bytes()).hexdigest()
    run_id = f"ws2-quality-{sha256(case['relative_path'].encode('utf-8')).hexdigest()[:12]}"

    data_dir = tmp_path / "data"
    summary = run_legal_ingestion(
        sources=[source_path],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=object(),
        run_id=run_id,
        dry_run=True,
    )

    assert sha256(source_path.read_bytes()).hexdigest() == before_digest

    assert summary.batch_report_path is not None
    batch_report = load_batch_report(summary.batch_report_path)
    assert len(batch_report.results) == 1
    result = batch_report.results[0]
    assert result.source_sha256 == before_digest
    assert result.final_state.value == "auto_passed", (
        f"{case['relative_path']} 未通过质量验收: {result.reason_code}"
    )

    quality_report = json.loads(
        Path(result.quality_report_path).read_text(encoding="utf-8")
    )
    assert quality_report["source_sha256"] == before_digest
    assert quality_report["ruleset_version"] == "legal-quality-v2"
    assert quality_report["overall"] == "pass", (
        f"{case['relative_path']} 质量报告 overall 不为 pass"
    )

    gates = {gate["gate_id"]: gate for gate in quality_report["gates"]}
    required_gates = [
        "source_identity",
        "document_identity",
        "boundary_confirmed",
        "article_start",
        "article_numbers",
        "article_non_empty",
        "body_purity",
        "exclusion_isolation",
        "cross_layer_consistency",
        "chunk_coverage",
        "s2_leading_material_isolation",
        "s2_metadata_traceability",
    ]
    for gate_id in required_gates:
        assert gate_id in gates, f"缺少门禁 {gate_id}"
        assert gates[gate_id]["outcome"] == "pass", (
            f"{case['relative_path']} 门禁 {gate_id} 未通过: "
            f"{gates[gate_id].get('reason_code')}"
        )

    assert gates["article_numbers"]["measured"]["article_count"] == case[
        "expected_article_count"
    ]
    assert gates["chunk_coverage"]["measured"]["article_count"] == case[
        "expected_article_count"
    ]
    assert gates["s2_leading_material_isolation"]["measured"][
        "leading_range_count"
    ] >= 1

    assert all(gate["outcome"] == "pass" for gate in quality_report["gates"])


def test_ws2_scope_has_exactly_two_word_cases() -> None:
    cases = _load_ws2_cases()
    assert len(cases) == 2
    assert all(
        set(item)
        == {
            "relative_path",
            "declared_extension",
            "expected_extraction_class",
            "expected_content_class",
            "expected_article_count",
            "risk_codes",
        }
        for item in cases
    )

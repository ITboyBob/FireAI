import json
from hashlib import sha256
from pathlib import Path

import pytest

from app.services.incremental_import import (
    CommitPlan,
    CommittedImport,
    IncrementalImportError,
    create_import_staging,
)
from app.services.legal_qualified_import import (
    CommitQualification,
    CommitQualificationError,
    QualifiedCommitPlan,
    commit_qualified_staged_import,
)


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _quality_report(sha256_value: str, document_id: str) -> dict:
    return {
        "ruleset_version": "legal-quality-v1",
        "source_sha256": sha256_value,
        "document_id": document_id,
        "overall": "pass",
        "gates": [],
        "attempt_id": "attempt-1",
        "attempt_state": "auto_passed",
        "quality_report_sha256": "a" * 64,
        "written_at": "2026-06-29T12:00:00Z",
    }


def _staging(data_dir: Path, document_id: str) -> Path:
    staging = create_import_staging(data_dir / ".staging", run_id="run-123")
    (staging.normalized_dir / f"{document_id}.txt").write_text(
        "新法规\n第一条 新增消防安全责任。", encoding="utf-8"
    )
    (staging.structured_dir / f"{document_id}.json").write_text(
        json.dumps({"document_id": document_id, "title": "新法规"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (staging.chunks_dir / f"{document_id}.jsonl").write_text(
        json.dumps(
            {
                "chunk_id": "new-1",
                "document_id": document_id,
                "title": "新法规",
                "path": "新法规 > 第一条",
                "text": "新增消防安全责任。",
                "article_no": "第一条",
                "chapter_title": None,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return staging


def _qualified_plan(
    tmp_path: Path,
    *,
    document_id: str = "new_fire_rule",
    source_name: str = "新法规",
    source_file_type: str = "doc",
    qualified_state: str = "auto_passed",
    tamper: str | None = None,
) -> QualifiedCommitPlan:
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    source_path = tmp_path / f"{source_name}.{source_file_type}"
    source_path.write_text("source content", encoding="utf-8")
    source_digest = _sha256_file(source_path)
    staging = _staging(data_dir, document_id)

    quality_report = _quality_report(source_digest, document_id)
    quality_path = tmp_path / "attempt-1.quality.json"
    quality_path.write_text(
        json.dumps(quality_report, ensure_ascii=False), encoding="utf-8"
    )
    quality_digest = _sha256_file(quality_path)

    normalized_path = staging.normalized_dir / f"{document_id}.txt"
    structured_path = staging.structured_dir / f"{document_id}.json"
    chunks_path = staging.chunks_dir / f"{document_id}.jsonl"

    # qualification 中的摘要必须是「未被篡改」的原始产物指纹，
    # 这样后续篡改才会触发摘要校验失败。
    original_normalized_sha256 = _sha256_file(normalized_path)
    original_structured_sha256 = _sha256_file(structured_path)
    original_chunks_sha256 = _sha256_file(chunks_path)

    if tamper == "normalized":
        normalized_path.write_text("tampered", encoding="utf-8")
    if tamper == "structured":
        structured_path.write_text("tampered", encoding="utf-8")
    if tamper == "chunks":
        chunks_path.write_text("tampered", encoding="utf-8")

    commit_plan = CommitPlan(
        document_id=document_id,
        source_name=source_name,
        source_path=str(source_path),
        source_file_type=source_file_type,  # type: ignore[arg-type]
        chunk_count=1,
        staging=staging,
        data_dir=data_dir,
        index_dir=index_dir,
        manifest_path=manifest_path,
        run_id="run-123",
    )
    qualification = CommitQualification(
        attempt_id="attempt-1",
        qualified_state=qualified_state,  # type: ignore[arg-type]
        ruleset_version="legal-quality-v1",
        source_sha256=source_digest,
        quality_report_sha256=quality_digest,
        normalized_sha256=original_normalized_sha256,
        structured_sha256=original_structured_sha256,
        chunks_sha256=original_chunks_sha256,
    )
    return QualifiedCommitPlan(
        commit_plan=commit_plan,
        quality_report_path=quality_path,
        quality_report_sha256=quality_digest,
        qualification=qualification,
    )


def test_commit_qualified_staged_import_rejects_processing_state(tmp_path: Path):
    plan = _qualified_plan(tmp_path, qualified_state="processing")

    with pytest.raises(CommitQualificationError, match="qualified_state"):
        commit_qualified_staged_import(plan, embedder=object())


def test_commit_qualified_staged_import_rejects_review_required_state(tmp_path: Path):
    plan = _qualified_plan(tmp_path, qualified_state="review_required")

    with pytest.raises(CommitQualificationError, match="qualified_state"):
        commit_qualified_staged_import(plan, embedder=object())


def test_commit_qualified_staged_import_rejects_failed_state(tmp_path: Path):
    plan = _qualified_plan(tmp_path, qualified_state="failed")

    with pytest.raises(CommitQualificationError, match="qualified_state"):
        commit_qualified_staged_import(plan, embedder=object())


def test_commit_qualified_staged_import_rejects_source_digest_mismatch(
    tmp_path: Path,
):
    plan = _qualified_plan(tmp_path, qualified_state="auto_passed")
    # 篡改源文件使其与 qualification 中的摘要不匹配
    source_path = Path(plan.commit_plan.source_path)
    source_path.write_text("changed", encoding="utf-8")

    with pytest.raises(CommitQualificationError, match="source_sha256"):
        commit_qualified_staged_import(plan, embedder=object())


def test_commit_qualified_staged_import_rejects_quality_report_digest_mismatch(
    tmp_path: Path,
):
    plan = _qualified_plan(tmp_path, qualified_state="auto_passed")
    plan.quality_report_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(CommitQualificationError, match="quality_report_sha256"):
        commit_qualified_staged_import(plan, embedder=object())


@pytest.mark.parametrize("tamper", ["normalized", "structured", "chunks"])
def test_commit_qualified_staged_import_rejects_staged_digest_mismatch(
    tmp_path: Path,
    tamper: str,
):
    plan = _qualified_plan(tmp_path, qualified_state="auto_passed", tamper=tamper)

    with pytest.raises(CommitQualificationError, match=f"{tamper}_sha256"):
        commit_qualified_staged_import(plan, embedder=object())


def test_commit_qualified_staged_import_delegates_after_validation(
    tmp_path: Path,
    monkeypatch,
):
    plan = _qualified_plan(tmp_path, qualified_state="auto_passed")
    calls = []

    def fake_commit_staged_import(commit_plan, *, embedder):
        calls.append((commit_plan, embedder))
        return CommittedImport(
            document_id=commit_plan.document_id,
            chunk_count=commit_plan.chunk_count,
        )

    monkeypatch.setattr(
        "app.services.legal_qualified_import.commit_staged_import",
        fake_commit_staged_import,
    )

    result = commit_qualified_staged_import(plan, embedder="fake-embedder")

    assert result.document_id == plan.commit_plan.document_id
    assert result.chunk_count == plan.commit_plan.chunk_count
    assert len(calls) == 1
    assert calls[0][0] is plan.commit_plan
    assert calls[0][1] == "fake-embedder"


def test_commit_qualified_staged_import_preserves_source_file_type(
    tmp_path: Path,
    monkeypatch,
):
    plan = _qualified_plan(tmp_path, qualified_state="auto_passed", source_file_type="doc")
    captured = []

    def fake_commit_staged_import(commit_plan, *, embedder):
        captured.append(commit_plan.source_file_type)
        return CommittedImport(
            document_id=commit_plan.document_id,
            chunk_count=commit_plan.chunk_count,
        )

    monkeypatch.setattr(
        "app.services.legal_qualified_import.commit_staged_import",
        fake_commit_staged_import,
    )

    commit_qualified_staged_import(plan, embedder=object())

    assert captured == ["doc"]


def test_commit_qualified_staged_import_does_not_call_commit_when_unqualified(
    tmp_path: Path,
    monkeypatch,
):
    plan = _qualified_plan(tmp_path, qualified_state="processing")
    called = []

    def fake_commit_staged_import(commit_plan, *, embedder):
        called.append(True)
        raise IncrementalImportError("should not reach")

    monkeypatch.setattr(
        "app.services.legal_qualified_import.commit_staged_import",
        fake_commit_staged_import,
    )

    with pytest.raises(CommitQualificationError):
        commit_qualified_staged_import(plan, embedder=object())

    assert not called

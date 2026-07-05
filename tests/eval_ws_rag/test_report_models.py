import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from scripts.eval_ws_rag.report_models import (
    CitationRecord,
    DatasetIdentity,
    DocumentScorecard,
    ErrorReport,
    EvaluationError,
    EvaluationProtocol,
    EvaluationReport,
    EvaluatedSystem,
    FailureReason,
    MetricScores,
    QuestionResult,
    RetrievedChunk,
    compute_protocol_fingerprint,
)


def _build_valid_question(**overrides):
    defaults = dict(
        question_id="q_001",
        question="示例问题",
        question_type="frequent",
        answerable=True,
        expected_behavior="answer",
        expected_article="第十条",
        source_chunk_id="chunk_001",
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id="chunk_001",
                document_id="doc_xxx",
                path="/a/b.jsonl",
                text="示例条文",
                retrieval_score=0.9,
                keyword_score=0.8,
                vector_score=0.85,
                sources=["keyword", "vector"],
                cited=True,
            )
        ],
        answer="示例答案",
        citations=[
            CitationRecord(
                document_id="doc_xxx",
                path="/a/b.jsonl",
                text="示例条文",
                matched_chunk_id="chunk_001",
                citation_label="《示例》第十条",
            )
        ],
        refused=False,
        uncertainty=None,
        metrics=MetricScores(
            context_relevancy=0.9,
            source_coverage=1.0,
            faithfulness=0.95,
            answer_relevance=0.9,
            citation_validity=1.0,
            refusal_appropriateness=1.0,
        ),
        red_line_failures=[],
        failure_reasons=[],
        judge_result=None,
        passed=True,
    )
    defaults.update(overrides)
    return QuestionResult(**defaults)


def _build_valid_document(**overrides):
    defaults = dict(
        document_id="doc_xxx",
        title="示例法规",
        source_sha256="abc123",
        content_class="S1",
        question_count=1,
        metrics=MetricScores(
            context_relevancy=0.9,
            source_coverage=1.0,
            faithfulness=0.95,
            answer_relevance=0.9,
            citation_validity=1.0,
            refusal_appropriateness=1.0,
        ),
        overall_pass_rate=1.0,
        failed_questions=[],
        questions=[_build_valid_question()],
    )
    defaults.update(overrides)
    return DocumentScorecard(**defaults)


def _build_valid_protocol(**overrides):
    thresholds = EvaluationProtocol.default_thresholds()
    fingerprint = compute_protocol_fingerprint(
        judge_model="doubao-seed-2-1-pro-260628",
        judge_prompt_version="judge_v1",
        judge_repetitions=3,
        evidence_order_strategy="seed_shuffled",
        metric_algorithm_version="v1",
        thresholds=thresholds,
    )
    return EvaluationProtocol(
        schema_version="1.0.0",
        protocol_fingerprint=fingerprint,
        judge_model="doubao-seed-2-1-pro-260628",
        judge_prompt_version="judge_v1",
        judge_temperature=0.0,
        judge_repetitions=3,
        judge_calibrated=False,
        evidence_order_strategy="seed_shuffled",
        metric_algorithm_version="v1",
        thresholds=thresholds,
        answer_model="doubao-1-5-lite-32k-250115",
        answer_prompt_version="answer_v1",
        top_k=5,
        **overrides,
    )


def _build_valid_report(**overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        schema_version="1.0.0",
        run_id="run_20260705_000000_abc123",
        created_at=now,
        dataset=DatasetIdentity(
            dataset_id="ds_001",
            dataset_fingerprint="fp_001",
            document_ids=["doc_xxx"],
        ),
        protocol=_build_valid_protocol(),
        system=EvaluatedSystem(
            git_commit="abc123",
            git_dirty=False,
            corpus_fingerprint="corpus_abc",
        ),
        summary=DocumentScorecard(
            document_id="__summary__",
            title="总体统计",
            question_count=1,
            metrics=MetricScores(
                context_relevancy=0.9,
                source_coverage=1.0,
                faithfulness=0.95,
                answer_relevance=0.9,
                citation_validity=1.0,
                refusal_appropriateness=1.0,
            ),
            overall_pass_rate=1.0,
            failed_questions=[],
            questions=[],
        ),
        documents=[_build_valid_document()],
    )
    defaults.update(overrides)
    return EvaluationReport(**defaults)


class TestScoreRanges:
    def test_score_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            MetricScores(context_relevancy=-0.1)

    def test_score_above_one_rejected(self):
        with pytest.raises(ValidationError):
            MetricScores(faithfulness=1.01)

    def test_score_boundary_accepted(self):
        scores = MetricScores(
            context_relevancy=0.0,
            source_coverage=0.0,
            faithfulness=0.0,
            answer_relevance=0.0,
            citation_validity=0.0,
            refusal_appropriateness=0.0,
        )
        assert scores.context_relevancy == 0.0


class TestRequiredTopLevelObjects:
    def test_missing_dataset_rejected(self):
        data = _build_valid_report().model_dump(mode="json")
        del data["dataset"]
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)

    def test_missing_protocol_rejected(self):
        data = _build_valid_report().model_dump(mode="json")
        del data["protocol"]
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)

    def test_missing_system_rejected(self):
        data = _build_valid_report().model_dump(mode="json")
        del data["system"]
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)


class TestIdentityAndFingerprint:
    def test_dataset_id_required(self):
        data = _build_valid_report().model_dump(mode="json")
        del data["dataset"]["dataset_id"]
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)

    def test_dataset_fingerprint_required(self):
        data = _build_valid_report().model_dump(mode="json")
        del data["dataset"]["dataset_fingerprint"]
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)

    def test_protocol_fingerprint_required(self):
        data = _build_valid_report().model_dump(mode="json")
        del data["protocol"]["protocol_fingerprint"]
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)

    def test_judge_calibrated_required_and_false(self):
        data = _build_valid_report().model_dump(mode="json")
        data["protocol"]["judge_calibrated"] = True
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)

    def test_protocol_fingerprint_covers_required_fields(self):
        protocol = _build_valid_protocol()
        fp = protocol.protocol_fingerprint
        assert "doubao-seed-2-1-pro-260628" in fp
        assert "judge_v1" in fp
        assert "seed_shuffled" in fp
        assert "v1" in fp
        for key in EvaluationProtocol.default_thresholds():
            assert key in fp


class TestSummaryConsistency:
    def _summary_with_count(self, question_count: int, **overrides):
        return DocumentScorecard(
            document_id="__summary__",
            title="总体统计",
            question_count=question_count,
            metrics=MetricScores(
                context_relevancy=0.9,
                source_coverage=1.0,
                faithfulness=0.95,
                answer_relevance=0.9,
                citation_validity=1.0,
                refusal_appropriateness=1.0,
            ),
            overall_pass_rate=1.0,
            failed_questions=[],
            questions=[],
            **overrides,
        )

    def test_summary_question_count_matches_documents(self):
        doc = _build_valid_document()
        doc.question_count = 2
        doc.questions = [_build_valid_question(), _build_valid_question(question_id="q_002")]
        summary = self._summary_with_count(2)
        report = _build_valid_report(documents=[doc], summary=summary)
        assert report.summary.question_count == 2

    def test_summary_passed_count_matches_questions(self):
        q1 = _build_valid_question(passed=True)
        q2 = _build_valid_question(question_id="q_002", passed=False)
        doc = _build_valid_document(questions=[q1, q2], question_count=2)
        summary = self._summary_with_count(2, passed_questions=1, failed_questions_count=1)
        report = _build_valid_report(documents=[doc], summary=summary)
        assert report.summary.passed_questions == 1
        assert report.summary.failed_questions_count == 1

    def test_red_line_count_consistent(self):
        q = _build_valid_question(
            passed=False,
            red_line_failures=[FailureReason(code="citation_invalid", description="引文无效")],
        )
        doc = _build_valid_document(questions=[q])
        summary = self._summary_with_count(1, red_line_failures_count=1)
        report = _build_valid_report(documents=[doc], summary=summary)
        assert report.summary.red_line_failures_count == 1


class TestReportErrorsPair:
    def test_report_and_errors_headers_match(self):
        report = _build_valid_report()
        errors = ErrorReport(
            schema_version=report.schema_version,
            run_id=report.run_id,
            created_at=report.created_at,
            errors=[],
        )
        assert errors.schema_version == report.schema_version
        assert errors.run_id == report.run_id

    def test_errors_cannot_have_non_empty_traceback_in_snapshot(self):
        error = EvaluationError(
            document_id="doc_xxx",
            question_id="q_001",
            stage="answer_generation",
            stage_description="答案生成",
            error_type="model_error",
            message="模型调用失败",
            recoverable=False,
            input_snapshot={"question": "示例问题"},
        )
        assert "traceback" not in error.model_dump(mode="json")


class TestVersionCompatibility:
    def test_unknown_major_version_rejected(self):
        data = _build_valid_report().model_dump(mode="json")
        data["schema_version"] = "2.0.0"
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)

    def test_supported_minor_version_accepted(self):
        data = _build_valid_report().model_dump(mode="json")
        data["schema_version"] = "1.1.0"
        report = EvaluationReport.model_validate(data)
        assert report.schema_version == "1.1.0"

    def test_unsupported_minor_version_rejected(self):
        data = _build_valid_report().model_dump(mode="json")
        data["schema_version"] = "1.99.0"
        with pytest.raises(ValidationError):
            EvaluationReport.model_validate(data)


class TestRoundTrip:
    def test_valid_report_round_trips(self):
        report = _build_valid_report()
        payload = report.model_dump(mode="json")
        restored = EvaluationReport.model_validate(payload)
        assert restored.run_id == report.run_id
        assert restored.documents[0].document_id == "doc_xxx"


class TestConfig:
    def test_default_thresholds_match_design(self):
        thresholds = EvaluationProtocol.default_thresholds()
        assert thresholds["context_relevancy"] == 0.8
        assert thresholds["source_coverage"] == 0.9
        assert thresholds["faithfulness"] == 0.9
        assert thresholds["answer_relevance"] == 0.8
        assert thresholds["citation_validity"] == 1.0
        assert thresholds["refusal_appropriateness"] == 0.9


class TestFixture:
    def test_valid_fixture_round_trips(self):
        import pathlib

        fixture_path = pathlib.Path(__file__).with_name("fixtures") / "valid_report.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        report = EvaluationReport.model_validate(raw)
        assert report.schema_version == "1.0.0"

    def test_errors_fixture_round_trips(self):
        import pathlib

        fixture_path = pathlib.Path(__file__).with_name("fixtures") / "valid_errors.json"
        raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        errors = ErrorReport.model_validate(raw)
        assert errors.schema_version == "1.0.0"

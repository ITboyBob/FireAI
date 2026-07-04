from dataclasses import dataclass

import pytest

from app.services.legal_ingestion_models import ContentClass, ExtractionClass
from app.services.legal_strategy_registry import (
    BoundaryStrategyRegistry,
    CapabilityStatus,
    ExtractionStrategyRegistry,
    build_boundary_strategy_registry,
    build_extraction_strategy_registry,
)
from app.services.legal_content_boundary import S1BoundaryStrategy
from app.services.legal_s2_boundary import S2BoundaryStrategy
from app.services.legal_s3_boundary import S3BoundaryStrategy
from app.services.legal_textutil import TextutilRunResult
from app.services.legal_word_extractor import WordLegalExtractor


@dataclass(frozen=True)
class FakeExtractor:
    kind: str = "W"
    version: str = "fake-v1"

    def extract(self, request):
        raise NotImplementedError


@dataclass(frozen=True)
class FakeBoundary:
    kind: str = "S1"
    version: str = "fake-v1"

    def identify(self, extraction, *, source, expected_title=None):
        return object()


@dataclass(frozen=True)
class FakeS2Boundary:
    kind: str = "S2"
    version: str = "fake-v1"

    def identify(self, extraction, *, source, expected_title=None):
        return object()


@dataclass(frozen=True)
class FakeS3Boundary:
    kind: str = "S3"
    version: str = "fake-v1"

    def identify(self, extraction, *, source, expected_title=None):
        return object()


def test_default_registries_expose_every_stable_key_with_explicit_status():
    extraction = ExtractionStrategyRegistry()
    boundary = BoundaryStrategyRegistry()

    assert {
        key: extraction.resolve(key).status
        for key in (ExtractionClass.W, ExtractionClass.PT, ExtractionClass.PS)
    } == {
        ExtractionClass.W: CapabilityStatus.UNSUPPORTED,
        ExtractionClass.PT: CapabilityStatus.UNSUPPORTED,
        ExtractionClass.PS: CapabilityStatus.UNSUPPORTED,
    }
    assert {
        key: boundary.resolve(key).status
        for key in (ContentClass.S1, ContentClass.S2, ContentClass.S3, ContentClass.S4)
    } == {
        ContentClass.S1: CapabilityStatus.UNSUPPORTED,
        ContentClass.S2: CapabilityStatus.UNSUPPORTED,
        ContentClass.S3: CapabilityStatus.UNSUPPORTED,
        ContentClass.S4: CapabilityStatus.REVIEW_REQUIRED,
    }
    assert (
        boundary.resolve(ContentClass.S4).reason_code
        == "boundary_strategy_review_required"
    )


def test_registries_register_independent_axis_strategies():
    extraction = ExtractionStrategyRegistry()
    boundary = BoundaryStrategyRegistry()
    extractor = FakeExtractor()
    boundary_strategy = FakeBoundary()

    extraction.register(ExtractionClass.W, extractor)
    boundary.register(ContentClass.S1, boundary_strategy)

    assert extraction.resolve(ExtractionClass.W).strategy is extractor
    assert boundary.resolve(ContentClass.S1).strategy is boundary_strategy
    assert extraction.resolve(ExtractionClass.PT).status is CapabilityStatus.UNSUPPORTED
    assert boundary.resolve(ContentClass.S2).status is CapabilityStatus.UNSUPPORTED


def test_extraction_registry_assembly_registers_only_word_strategy():
    word = WordLegalExtractor(
        run_textutil=lambda source: TextutilRunResult(
            returncode=0,
            stdout="某规定\n第一条 正文",
            stderr="",
        )
    )

    registry = build_extraction_strategy_registry(word_extractor=word)

    assert registry.resolve(ExtractionClass.W).strategy is word
    assert registry.resolve(ExtractionClass.PT).status is CapabilityStatus.UNSUPPORTED
    assert registry.resolve(ExtractionClass.PS).status is CapabilityStatus.UNSUPPORTED


def test_boundary_registry_assembly_registers_only_s1_strategy():
    s1 = S1BoundaryStrategy()

    registry = build_boundary_strategy_registry(s1_strategy=s1)

    assert registry.resolve(ContentClass.S1).strategy is s1
    assert registry.resolve(ContentClass.S2).status is CapabilityStatus.UNSUPPORTED
    assert registry.resolve(ContentClass.S3).status is CapabilityStatus.UNSUPPORTED
    assert registry.resolve(ContentClass.S4).status is CapabilityStatus.REVIEW_REQUIRED


def test_boundary_registry_assembly_registers_s1_and_s2_strategies():
    s1 = S1BoundaryStrategy()
    s2 = S2BoundaryStrategy()

    registry = build_boundary_strategy_registry(s1_strategy=s1, s2_strategy=s2)

    assert registry.resolve(ContentClass.S1).strategy is s1
    assert registry.resolve(ContentClass.S2).strategy is s2
    assert registry.resolve(ContentClass.S3).status is CapabilityStatus.UNSUPPORTED
    assert registry.resolve(ContentClass.S4).status is CapabilityStatus.REVIEW_REQUIRED


def test_boundary_registry_assembly_registers_s3_strategy():
    s3 = S3BoundaryStrategy()

    registry = build_boundary_strategy_registry(s3_strategy=s3)

    assert registry.resolve(ContentClass.S3).strategy is s3
    assert registry.resolve(ContentClass.S1).status is CapabilityStatus.UNSUPPORTED
    assert registry.resolve(ContentClass.S2).status is CapabilityStatus.UNSUPPORTED
    assert registry.resolve(ContentClass.S4).status is CapabilityStatus.REVIEW_REQUIRED


def test_boundary_registry_assembly_registers_all_implemented_strategies():
    s1 = S1BoundaryStrategy()
    s2 = S2BoundaryStrategy()
    s3 = S3BoundaryStrategy()

    registry = build_boundary_strategy_registry(
        s1_strategy=s1, s2_strategy=s2, s3_strategy=s3
    )

    assert registry.resolve(ContentClass.S1).strategy is s1
    assert registry.resolve(ContentClass.S2).strategy is s2
    assert registry.resolve(ContentClass.S3).strategy is s3
    assert registry.resolve(ContentClass.S4).status is CapabilityStatus.REVIEW_REQUIRED


def test_boundary_registry_rejects_s3_kind_mismatch():
    registry = build_boundary_strategy_registry()

    with pytest.raises(ValueError, match="正文边界策略 kind 必须与内容轴键一致"):
        registry.register(ContentClass.S3, FakeBoundary(kind="S1"))


def test_boundary_registry_rejects_s2_kind_mismatch():
    registry = build_boundary_strategy_registry()

    with pytest.raises(ValueError, match="正文边界策略 kind 必须与内容轴键一致"):
        registry.register(ContentClass.S2, FakeBoundary(kind="S1"))


def test_boundary_registry_rejects_duplicate_s2():
    registry = build_boundary_strategy_registry(s2_strategy=S2BoundaryStrategy())

    with pytest.raises(ValueError, match="正文边界策略已注册"):
        registry.register(ContentClass.S2, S2BoundaryStrategy(version="other"))


@pytest.mark.parametrize("invalid_key", ["W-S1", ("W", "S1"), ExtractionClass.PX])
def test_extraction_registry_rejects_combination_and_px_keys(invalid_key):
    registry = ExtractionStrategyRegistry()

    with pytest.raises((TypeError, ValueError), match="提取"):
        registry.register(invalid_key, FakeExtractor())


@pytest.mark.parametrize("invalid_key", ["W-S1", "W-S2", "W-S3", ("W", "S3"), "W-S4"])
def test_boundary_registry_rejects_combination_keys(invalid_key):
    registry = BoundaryStrategyRegistry()

    with pytest.raises(TypeError, match="正文边界"):
        registry.register(invalid_key, FakeBoundary())

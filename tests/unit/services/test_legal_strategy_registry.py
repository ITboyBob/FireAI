from dataclasses import dataclass

import pytest

from app.services.legal_ingestion_models import ContentClass, ExtractionClass
from app.services.legal_strategy_registry import (
    BoundaryStrategyRegistry,
    CapabilityStatus,
    ExtractionStrategyRegistry,
    build_extraction_strategy_registry,
)
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


@pytest.mark.parametrize("invalid_key", ["W-S1", ("W", "S1"), ExtractionClass.PX])
def test_extraction_registry_rejects_combination_and_px_keys(invalid_key):
    registry = ExtractionStrategyRegistry()

    with pytest.raises((TypeError, ValueError), match="提取"):
        registry.register(invalid_key, FakeExtractor())


@pytest.mark.parametrize("invalid_key", ["W-S1", ("W", "S1")])
def test_boundary_registry_rejects_combination_keys(invalid_key):
    registry = BoundaryStrategyRegistry()

    with pytest.raises(TypeError, match="正文边界"):
        registry.register(invalid_key, FakeBoundary())

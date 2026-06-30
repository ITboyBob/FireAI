from pathlib import Path
from dataclasses import asdict
from hashlib import sha256
import json

import pytest

from app.services.chunk_builder import (
    build_chunks,
    build_intermediate_chunks,
    write_chunks,
)
from app.services.legal_content_boundary import identify_s1_target_body
from app.services.legal_s2_boundary import S2BoundaryStrategy
from app.services.legal_extractor import (
    ExtractedBlock,
    ExtractedPage,
    ExtractionResult,
    SourceLocation,
)
from app.services.legal_ingestion_models import IngestionDisposition, SourceRef
from app.services.structure_parser import parse_legal_intermediate


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "chunks"


def _confirmed_pair(tmp_path: Path):
    source_path = tmp_path / "某规定.doc"
    source_path.write_bytes(b"sample")
    source = SourceRef(
        relative_path="某规定.doc",
        source_path=source_path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )
    lines = ("某规定", "第一条 第一款正文。", "第二条 第二条正文。")
    blocks = tuple(
        ExtractedBlock(
            order=order,
            text=line,
            location=SourceLocation(
                logical_page=1,
                page_number=None,
                block_order=order,
                line_number=order + 1,
            ),
        )
        for order, line in enumerate(lines)
    )
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=(
            ExtractedPage(
                logical_page=1,
                page_number=None,
                block_orders=tuple(range(len(blocks))),
            ),
        ),
        text_blocks=blocks,
        disposition=IngestionDisposition.READY,
    )
    intermediate = identify_s1_target_body(
        extraction,
        source=source,
        expected_title="某规定",
    )
    return intermediate, parse_legal_intermediate(intermediate)


def _s2_confirmed_pair(tmp_path: Path):
    source_path = tmp_path / "某规定.doc"
    source_path.write_bytes(b"sample")
    source = SourceRef(
        relative_path="某规定.doc",
        source_path=source_path,
        source_sha256=sha256(b"sample").hexdigest(),
        size_bytes=6,
        declared_extension=".doc",
    )
    lines = (
        "某省人民政府",
        "关于修订《某规定》的决定",
        "某规定",
        "（2020年1月1日公布）",
        "第一条 第一款正文。",
        "第二款正文。",
        "第二条 第二条正文。",
    )
    blocks = tuple(
        ExtractedBlock(
            order=order,
            text=line,
            location=SourceLocation(
                logical_page=1,
                page_number=None,
                block_order=order,
                line_number=order + 1,
            ),
        )
        for order, line in enumerate(lines)
    )
    extraction = ExtractionResult(
        source_sha256=source.source_sha256,
        extractor_kind="W",
        extractor_version="fake-v1",
        pages=(
            ExtractedPage(
                logical_page=1,
                page_number=None,
                block_orders=tuple(range(len(blocks))),
            ),
        ),
        text_blocks=blocks,
        disposition=IngestionDisposition.READY,
    )
    intermediate = S2BoundaryStrategy().identify(
        extraction,
        source=source,
        expected_title="某规定",
    )
    return intermediate, parse_legal_intermediate(intermediate)


def test_build_chunks_preserves_article_path_and_metadata():
    structured = {
        "document_id": "xiaofangfa_2019",
        "title": "中华人民共和国消防法",
        "issuing_authority": None,
        "region": "全国",
        "promulgated_on": None,
        "effective_on": "2009年5月1日",
        "articles": [
            {
                "article_no": "第二条",
                "chapter_title": "第一章 总则",
                "heading_path": ["第一章 总则"],
                "text": "国家实行消防安全责任制。",
            }
        ],
    }

    chunks = build_chunks(structured)

    assert chunks == [
        {
            "chunk_id": "xiaofangfa_2019#article-1",
            "document_id": "xiaofangfa_2019",
            "title": "中华人民共和国消防法",
            "path": "中华人民共和国消防法 > 第一章 总则 > 第二条",
            "text": "国家实行消防安全责任制。",
            "article_no": "第二条",
            "article_index": 1,
            "chapter_title": "第一章 总则",
            "heading_path": ["第一章 总则"],
            "issuing_authority": None,
            "region": "全国",
            "promulgated_on": None,
            "effective_on": "2009年5月1日",
            "revision_events": None,
            "version_basis": None,
            "chunk_index": 1,
            "chunk_total": 1,
        }
    ]


def test_build_chunks_splits_long_article_by_paragraph_without_losing_path():
    structured = {
        "document_id": "hebei_xiaofang_tiaoli",
        "title": "河北省消防条例",
        "issuing_authority": None,
        "region": "河北省",
        "promulgated_on": None,
        "effective_on": "2010年7月1日",
        "articles": [
            {
                "article_no": "第一条",
                "chapter_title": "第一章 总则",
                "heading_path": ["第一章 总则"],
                "text": "第一段说明。\n第二段说明。\n第三段说明。",
            }
        ],
    }

    chunks = build_chunks(structured, max_chunk_chars=8)

    assert [chunk["chunk_id"] for chunk in chunks] == [
        "hebei_xiaofang_tiaoli#article-1-part-1",
        "hebei_xiaofang_tiaoli#article-1-part-2",
        "hebei_xiaofang_tiaoli#article-1-part-3",
    ]
    assert [chunk["path"] for chunk in chunks] == [
        "河北省消防条例 > 第一章 总则 > 第一条",
        "河北省消防条例 > 第一章 总则 > 第一条",
        "河北省消防条例 > 第一章 总则 > 第一条",
    ]
    assert [chunk["text"] for chunk in chunks] == [
        "第一段说明。",
        "第二段说明。",
        "第三段说明。",
    ]
    assert [chunk["chunk_total"] for chunk in chunks] == [3, 3, 3]


def test_build_chunks_omits_missing_heading_from_path():
    structured = {
        "document_id": "hebei_xiaofang_anquan_zerenzhi_shishi_banfa",
        "title": "河北省消防安全责任制实施办法",
        "issuing_authority": "河北省人民政府",
        "region": "河北省",
        "promulgated_on": "2009年10月29日",
        "effective_on": "2009年12月1日",
        "articles": [
            {
                "article_no": "第一条",
                "chapter_title": None,
                "heading_path": [],
                "text": "为明确和落实消防安全责任，制定本办法。",
            }
        ],
    }

    chunks = build_chunks(structured)

    assert chunks[0]["path"] == "河北省消防安全责任制实施办法 > 第一条"
    assert chunks[0]["heading_path"] == []


def test_write_chunks_persists_jsonl(tmp_path: Path):
    structured = {
        "document_id": "xiaofangfa_2019",
        "title": "中华人民共和国消防法",
        "issuing_authority": None,
        "region": "全国",
        "promulgated_on": None,
        "effective_on": "2009年5月1日",
        "articles": [
            {
                "article_no": "第二条",
                "chapter_title": "第一章 总则",
                "heading_path": ["第一章 总则"],
                "text": "国家实行消防安全责任制。",
            }
        ],
    }

    chunks = build_chunks(structured)
    output_path = write_chunks(chunks, "xiaofangfa_2019", tmp_path / "data" / "chunks")

    assert output_path == tmp_path / "data" / "chunks" / "xiaofangfa_2019.jsonl"

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["chunk_id"] == "xiaofangfa_2019#article-1"
    assert payload["path"] == "中华人民共和国消防法 > 第一章 总则 > 第二条"


def test_build_intermediate_chunks_propagates_confirmed_source_contract(tmp_path):
    intermediate, parsed = _confirmed_pair(tmp_path)

    chunks = build_intermediate_chunks(intermediate, parsed)

    assert len(chunks) == 2
    assert all(
        chunk["source_sha256"] == intermediate.source_ref.source_sha256
        and chunk["extraction_class"] == "W"
        and chunk["content_class"] == "S1"
        and chunk["boundary_status"] == "confirmed"
        for chunk in chunks
    )
    assert chunks[0]["source_span"] == asdict(parsed.articles[0].source_span)
    assert chunks[1]["source_span"] == asdict(parsed.articles[1].source_span)


def test_build_intermediate_chunks_rejects_digest_mismatch_before_build(
    tmp_path,
    monkeypatch,
):
    intermediate, parsed = _confirmed_pair(tmp_path)
    parsed = type(parsed)(
        document_id=parsed.document_id,
        title=parsed.title,
        issuing_authority=parsed.issuing_authority,
        region=parsed.region,
        promulgated_on=parsed.promulgated_on,
        effective_on=parsed.effective_on,
        articles=parsed.articles,
        source_sha256="f" * 64,
        extraction_class=parsed.extraction_class,
        content_class=parsed.content_class,
        boundary_status=parsed.boundary_status,
        version_basis=parsed.version_basis,
    )
    calls = []
    monkeypatch.setattr(
        "app.services.chunk_builder.build_chunks",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(ValueError, match="摘要"):
        build_intermediate_chunks(intermediate, parsed)

    assert calls == []


def test_build_intermediate_chunks_propagates_s2_metadata_to_chunks(tmp_path):
    intermediate, parsed = _s2_confirmed_pair(tmp_path)

    chunks = build_intermediate_chunks(intermediate, parsed)

    assert len(chunks) == 2
    assert all(
        chunk["issuing_authority"] == parsed.issuing_authority
        and chunk["promulgated_on"] == parsed.promulgated_on
        and chunk["revision_events"] == parsed.revision_events
        and chunk["version_basis"] == parsed.version_basis
        and chunk["source_sha256"] == intermediate.source_ref.source_sha256
        and chunk["content_class"] == "S2"
        for chunk in chunks
    )
    assert "metadata_evidence" not in chunks[0]


def test_build_intermediate_chunks_rejects_metadata_mismatch_with_intermediate(
    tmp_path,
):
    intermediate, parsed = _s2_confirmed_pair(tmp_path)
    parsed = type(parsed)(
        document_id=parsed.document_id,
        title=parsed.title,
        issuing_authority=parsed.issuing_authority,
        region=parsed.region,
        promulgated_on=parsed.promulgated_on,
        effective_on=parsed.effective_on,
        articles=parsed.articles,
        source_sha256=parsed.source_sha256,
        extraction_class=parsed.extraction_class,
        content_class=parsed.content_class,
        boundary_status=parsed.boundary_status,
        version_basis="mismatched",
        revision_events=parsed.revision_events,
        metadata_evidence=parsed.metadata_evidence,
    )

    with pytest.raises(ValueError, match="版本依据"):
        build_intermediate_chunks(intermediate, parsed)


def test_build_chunks_do_not_carry_full_metadata_evidence():
    structured = {
        "document_id": "doc-1",
        "title": "某规定",
        "issuing_authority": "某机关",
        "region": None,
        "promulgated_on": "2020年1月1日",
        "effective_on": None,
        "version_basis": "v1",
        "revision_events": ("第一次修正",),
        "metadata_evidence": (
            {
                "field_name": "issuing_authority",
                "value": "某机关",
                "source_span": {
                    "start": {"logical_page": 1, "page_number": None, "block_order": 0, "line_number": 1},
                    "end": {"logical_page": 1, "page_number": None, "block_order": 0, "line_number": 1},
                    "start_char_offset": 0,
                    "end_char_offset": 3,
                },
                "extraction_status": "confirmed",
            },
        ),
        "articles": [
            {
                "article_no": "第一条",
                "chapter_title": None,
                "heading_path": [],
                "text": "正文。",
            }
        ],
    }

    chunks = build_chunks(structured)

    assert chunks[0]["issuing_authority"] == "某机关"
    assert chunks[0]["revision_events"] == ("第一次修正",)
    assert "metadata_evidence" not in chunks[0]

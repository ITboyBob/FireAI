from hashlib import sha1
from pathlib import Path
import shutil

from app.services.corpus_ingestor import discover_documents


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "raw"


def _stage_fixture(tmp_path: Path, filename: str) -> None:
    shutil.copy(FIXTURE_DIR / filename, tmp_path / filename)


def test_discover_documents_builds_stable_manifest(tmp_path: Path):
    _stage_fixture(tmp_path, "消防法--2019年4月23日.doc")
    _stage_fixture(tmp_path, "河北省消防条例.docx")
    (tmp_path / "机关、团体、企业、事业单位消防安全管理规定.doc").write_text(
        "stub",
        encoding="utf-8",
    )

    manifest = discover_documents(tmp_path)

    assert [
        (
            item.document_id,
            item.source_path.name,
            item.source_name,
            item.file_type,
        )
        for item in manifest
    ] == [
        (
            "hebei_xiaofang_tiaoli",
            "河北省消防条例.docx",
            "河北省消防条例",
            "docx",
        ),
        (
            "jiguan_tuanti_qiye_shiye_danwei_xiaofang_anquan_guanli_guiding",
            "机关、团体、企业、事业单位消防安全管理规定.doc",
            "机关、团体、企业、事业单位消防安全管理规定",
            "doc",
        ),
        (
            "xiaofangfa_2019",
            "消防法--2019年4月23日.doc",
            "消防法--2019年4月23日",
            "doc",
        ),
    ]


def test_discover_documents_ignores_unsupported_files(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")

    manifest = discover_documents(tmp_path)

    assert manifest == []


def test_discover_documents_builds_ascii_slug_for_unmapped_ascii_names(tmp_path: Path):
    (tmp_path / "Fire Rule 2024!!.docx").write_text("stub", encoding="utf-8")

    manifest = discover_documents(tmp_path)

    assert [item.document_id for item in manifest] == ["fire_rule_2024"]


def test_discover_documents_falls_back_to_hash_for_unmapped_non_ascii_names(
    tmp_path: Path,
):
    filename = "未知法规草案.docx"
    (tmp_path / filename).write_text("stub", encoding="utf-8")

    manifest = discover_documents(tmp_path)

    expected_hash = sha1("未知法规草案".encode("utf-8")).hexdigest()[:12]
    assert [item.document_id for item in manifest] == [f"doc_{expected_hash}"]

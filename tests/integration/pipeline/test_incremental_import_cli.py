from dataclasses import dataclass
from pathlib import Path
import runpy


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_import_new_corpus_cli_requires_explicit_source(capsys):
    module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "import_new_corpus.py"))

    result = module["main"]([])

    assert result == 2
    captured = capsys.readouterr()
    assert "必须显式指定新增法规文件" in captured.err


def test_import_new_corpus_cli_rejects_multiple_sources(tmp_path, capsys):
    first = tmp_path / "第一份.docx"
    second = tmp_path / "第二份.docx"
    first.write_text("placeholder", encoding="utf-8")
    second.write_text("placeholder", encoding="utf-8")
    module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "import_new_corpus.py"))

    result = module["main"](["--source", str(first), "--source", str(second)])

    assert result == 2
    captured = capsys.readouterr()
    assert "第一版一次只能导入一个法规文件" in captured.err


def test_import_new_corpus_cli_rejects_positional_and_option_source(tmp_path, capsys):
    positional = tmp_path / "位置参数.docx"
    option = tmp_path / "选项参数.docx"
    positional.write_text("placeholder", encoding="utf-8")
    option.write_text("placeholder", encoding="utf-8")
    module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "import_new_corpus.py"))

    result = module["main"]([str(positional), "--source", str(option)])

    assert result == 2
    captured = capsys.readouterr()
    assert "第一版一次只能导入一个法规文件" in captured.err


def test_import_new_corpus_cli_accepts_single_positional_source(
    tmp_path,
    monkeypatch,
    capsys,
):
    source = tmp_path / "新消防规定.docx"
    source.write_text("placeholder", encoding="utf-8")
    data_dir = tmp_path / "data"
    calls = []
    module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "import_new_corpus.py"))

    @dataclass(frozen=True)
    class FakeSummary:
        run_id: str
        committed_document_ids: list[str]
        total_chunks: int
        manifest_path: Path

    def fake_run_incremental_import(**kwargs):
        calls.append(kwargs)
        return FakeSummary(
            run_id="run-123",
            committed_document_ids=["doc_new"],
            total_chunks=1,
            manifest_path=kwargs["manifest_path"],
        )

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("INDEX_DIR", str(data_dir / "index"))
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "local-model")
    monkeypatch.setitem(
        module["main"].__globals__,
        "run_incremental_import",
        fake_run_incremental_import,
    )

    result = module["main"]([str(source)])

    assert result == 0
    assert calls[0]["sources"] == [source]
    captured = capsys.readouterr()
    assert "run_id=run-123" in captured.out


def test_import_new_corpus_cli_wires_settings_source_and_embedder(
    tmp_path,
    monkeypatch,
    capsys,
):
    source = tmp_path / "新消防规定.docx"
    source.write_text("placeholder", encoding="utf-8")
    data_dir = tmp_path / "data"
    calls = []
    module = runpy.run_path(str(PROJECT_ROOT / "scripts" / "import_new_corpus.py"))

    @dataclass(frozen=True)
    class FakeSummary:
        run_id: str
        committed_document_ids: list[str]
        total_chunks: int
        manifest_path: Path

    def fake_run_incremental_import(**kwargs):
        calls.append(kwargs)
        return FakeSummary(
            run_id="run-123",
            committed_document_ids=["doc_new"],
            total_chunks=1,
            manifest_path=kwargs["manifest_path"],
        )

    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("INDEX_DIR", str(data_dir / "index"))
    monkeypatch.setenv("EMBEDDING_MODEL_NAME", "local-model")
    monkeypatch.setitem(
        module["main"].__globals__,
        "run_incremental_import",
        fake_run_incremental_import,
    )

    result = module["main"](["--source", str(source)])

    assert result == 0
    assert calls[0]["sources"] == [source]
    assert calls[0]["data_dir"] == data_dir
    assert calls[0]["index_dir"] == data_dir / "index"
    assert calls[0]["manifest_path"] == data_dir / "manifests" / "incremental_imports.json"
    assert calls[0]["staging_root"] == data_dir / ".staging"
    captured = capsys.readouterr()
    assert "run_id=run-123" in captured.out
    assert "documents=doc_new" in captured.out
    assert "warning=第一版只做机械冲突检测" in captured.out

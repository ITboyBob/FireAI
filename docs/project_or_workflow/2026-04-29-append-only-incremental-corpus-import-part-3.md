# 显式新法规 Append-Only 增量导入实施计划（分卷三）

> 本文为实施计划分卷三；分卷导航见[实施计划总览](./2026-04-29-append-only-incremental-corpus-import.md)。

## Task 9: 两阶段提交与失败回滚 / 不可见提交

**Files:**
- Modify: `app/services/incremental_import.py`
- Modify: `tests/unit/services/test_incremental_import.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

增加提交失败时正式目录不出现半成品的测试：

```python
from pathlib import Path

import pytest

from app.services.incremental_import import (
    CommitPlan,
    IncrementalImportError,
    commit_staged_import,
    create_import_staging,
)


def test_commit_staged_import_does_not_publish_partial_corpus_files(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    staging = create_import_staging(data_dir / ".staging", run_id="run-123")
    (staging.normalized_dir / "new_doc.txt").write_text("normalized", encoding="utf-8")
    (staging.structured_dir / "new_doc.json").write_text("{}", encoding="utf-8")
    (staging.chunks_dir / "new_doc.jsonl").write_text('{"chunk_id":"new-1","document_id":"new_doc"}\n', encoding="utf-8")

    def fail_keyword_append(*args, **kwargs):
        raise IncrementalImportError("模拟关键词索引失败")

    monkeypatch.setattr("app.services.incremental_import.append_keyword_index", fail_keyword_append)

    with pytest.raises(IncrementalImportError, match="模拟关键词索引失败"):
        commit_staged_import(
            CommitPlan(
                document_id="new_doc",
                source_name="新法规",
                source_path="/tmp/new.docx",
                chunk_count=1,
                staging=staging,
                data_dir=data_dir,
                index_dir=index_dir,
                manifest_path=manifest_path,
                run_id="run-123",
            ),
            embedder=object(),
        )

    assert not (data_dir / "normalized" / "new_doc.txt").exists()
    assert not (data_dir / "structured" / "new_doc.json").exists()
    assert not (data_dir / "chunks" / "new_doc.jsonl").exists()
    assert not manifest_path.exists()


def test_commit_staged_import_keeps_formal_keyword_db_unchanged_when_later_step_fails(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    staging = create_import_staging(data_dir / ".staging", run_id="run-123")

    prepare_existing_keyword_db(index_dir / "retrieval.db", document_id="old_doc")
    keyword_count_before = count_keyword_rows(index_dir / "retrieval.db")
    write_staged_new_doc_files(staging, document_id="new_doc")

    def fail_vector_append(*args, **kwargs):
        raise IncrementalImportError("模拟向量索引失败")

    monkeypatch.setattr("app.services.incremental_import.append_vector_index", fail_vector_append)

    with pytest.raises(IncrementalImportError, match="模拟向量索引失败"):
        commit_staged_import(
            CommitPlan(
                document_id="new_doc",
                source_name="新法规",
                source_path="/tmp/new.docx",
                chunk_count=1,
                staging=staging,
                data_dir=data_dir,
                index_dir=index_dir,
                manifest_path=manifest_path,
                run_id="run-123",
            ),
            embedder=object(),
        )

    assert count_keyword_rows(index_dir / "retrieval.db") == keyword_count_before
    assert not keyword_document_exists(index_dir / "retrieval.db", "new_doc")


def test_commit_staged_import_rolls_back_everything_when_manifest_write_fails(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifest_path = data_dir / "manifests" / "incremental_imports.json"
    staging = create_import_staging(data_dir / ".staging", run_id="run-123")

    prepare_existing_keyword_db(index_dir / "retrieval.db", document_id="old_doc")
    prepare_existing_fake_vector_index(index_dir, document_id="old_doc", vector_count=1)
    write_staged_new_doc_files(staging, document_id="new_doc")

    keyword_count_before = count_keyword_rows(index_dir / "retrieval.db")
    vector_count_before = read_fake_vector_count(index_dir / "faiss.index")
    vector_map_before = (index_dir / "vector_map.json").read_text(encoding="utf-8")
    manifest_before = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else None

    def fail_manifest_append(*args, **kwargs):
        raise IncrementalImportError("模拟 manifest 写入失败")

    monkeypatch.setattr("app.services.incremental_import.append_import_record", fail_manifest_append)

    with pytest.raises(IncrementalImportError, match="模拟 manifest 写入失败"):
        commit_staged_import(
            CommitPlan(
                document_id="new_doc",
                source_name="新法规",
                source_path="/tmp/new.docx",
                chunk_count=1,
                staging=staging,
                data_dir=data_dir,
                index_dir=index_dir,
                manifest_path=manifest_path,
                run_id="run-123",
            ),
            embedder=FakeEmbedder(),
        )

    assert count_keyword_rows(index_dir / "retrieval.db") == keyword_count_before
    assert not keyword_document_exists(index_dir / "retrieval.db", "new_doc")
    assert read_fake_vector_count(index_dir / "faiss.index") == vector_count_before
    assert (index_dir / "vector_map.json").read_text(encoding="utf-8") == vector_map_before
    assert not (data_dir / "normalized" / "new_doc.txt").exists()
    assert not (data_dir / "structured" / "new_doc.json").exists()
    assert not (data_dir / "chunks" / "new_doc.jsonl").exists()
    if manifest_before is None:
        assert not manifest_path.exists()
    else:
        assert manifest_path.read_text(encoding="utf-8") == manifest_before
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_commit_staged_import_does_not_publish_partial_corpus_files tests/unit/services/test_incremental_import.py::test_commit_staged_import_keeps_formal_keyword_db_unchanged_when_later_step_fails tests/unit/services/test_incremental_import.py::test_commit_staged_import_rolls_back_everything_when_manifest_write_fails -q`

Expected: FAIL，因为提交层尚未实现。

**Step 3: Write minimal implementation**

实现 `commit_staged_import(plan, embedder)`：

推荐提交顺序：

1. 再次执行 `validate_append_only_preflight(...)`，防止 staging 生成后外部状态变化。
2. 读取 staging chunks。
3. 将正式 `data/index/retrieval.db` 复制到 `staging.index_dir / "retrieval.db"`，只在 staged DB 上执行 `append_keyword_index(...)`；禁止直接写正式 DB。
4. 将正式 `data/index/faiss.index` 与 `data/index/vector_map.json` 作为输入，在 `staging.index_dir` 中生成 staged `faiss.index` 与 staged `vector_map.json`；禁止在向量 append 阶段直接替换正式索引。
5. 校验 staged DB 中包含新法规 rows，正式 DB row count 仍等于提交前数量。
6. 校验 staged FAISS `vector_count` 与 staged `vector_map.json` 行数一致。
7. 确认所有 staged index artifacts 成功后，再用独占创建语义发布 `normalized/structured/chunks` 到正式目录。
8. 用临时备份和 `Path.replace()` 仅提交 staged `retrieval.db`、`faiss.index`、`vector_map.json` 三个索引产物。
9. 最后 append manifest 记录。

关键约束：

- 正式语料文件发布禁止使用 `Path.replace()`，因为它会覆盖目标文件。必须使用独占创建语义，例如 `open(target, "xb")` 后复制 bytes，或在同一文件系统内使用 `os.link(staged_file, target)`；目标已存在时必须失败并停止。
- 如果任何 staged 索引步骤失败，不发布正式语料文件，不替换正式索引，不写 manifest。
- 如果 staged keyword append 已成功但 staged vector append 或 manifest 失败，正式 `data/index/retrieval.db` 的 row count 必须保持提交前状态；Task 9 的失败测试必须覆盖这一点。
- 如果 manifest 写入失败，计划中应将本次视为失败；实现必须尝试回滚本次已发布的新增语料文件和已替换索引。Task 9 必须覆盖 staged DB/vector 已生成、正式语料和索引即将或已经提交时，`append_import_record(...)` 失败后正式 `retrieval.db` row count、`faiss.index` 或 fake vector count、`vector_map.json`、语料文件和 manifest 都恢复到提交前状态。
- 若极端情况下无法完全恢复，必须抛出严重错误，例如 `IncrementalImportRollbackError`；错误信息必须包含人工修复指引，至少指出需要核对或恢复的路径：`data/index/retrieval.db`、`data/index/faiss.index`、`data/index/vector_map.json`、`data/normalized/<document_id>.txt`、`data/structured/<document_id>.json`、`data/chunks/<document_id>.jsonl`、`data/manifests/incremental_imports.json`。这只是异常兜底，不是正常路径；正常路径必须自动回滚并通过失败测试。
- 第一版不做跨进程锁；但同一进程必须在提交前后都做冲突检查。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- staging 成功前正式目录不可见。
- staged 索引失败不会留下新增 `normalized/structured/chunks` 正式文件，也不会改变正式 `retrieval.db`。
- manifest 写入失败会恢复正式关键词索引、向量索引、`vector_map.json`、语料文件和 manifest 到提交前状态；无法完全恢复时错误信息包含人工修复指引。
- manifest 只在完整提交后记录。

## Task 10: 增量导入编排服务

**Files:**
- Modify: `app/services/incremental_import.py`
- Modify: `tests/unit/services/test_incremental_import.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

增加端到端服务编排测试，使用 fake embedder 和 monkeypatch 的语料生成，确认步骤顺序：

```python
from pathlib import Path

import pytest

from app.services.incremental_import import IncrementalImportError, run_incremental_import


def test_run_incremental_import_returns_committed_summary(tmp_path: Path, monkeypatch):
    source = tmp_path / "新消防规定.docx"
    source.write_text("placeholder", encoding="utf-8")
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"

    # 测试中可复用 build_keyword_index/build_vector_index 先准备一个最小旧索引。
    prepare_existing_test_indexes(index_dir)

    summary = run_incremental_import(
        sources=[source],
        data_dir=data_dir,
        index_dir=index_dir,
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id="run-123",
    )

    assert summary.run_id == "run-123"
    assert summary.committed_document_ids == ["doc_<expected>"]
    assert summary.total_chunks > 0


def test_run_incremental_import_rejects_multiple_sources(tmp_path: Path):
    first = tmp_path / "第一份.docx"
    second = tmp_path / "第二份.docx"
    first.write_text("placeholder", encoding="utf-8")
    second.write_text("placeholder", encoding="utf-8")

    with pytest.raises(IncrementalImportError, match="第一版一次只能导入一个法规文件"):
        run_incremental_import(
            sources=[first, second],
            data_dir=tmp_path / "data",
            index_dir=tmp_path / "data" / "index",
            manifest_path=tmp_path / "data" / "manifests" / "incremental_imports.json",
            staging_root=tmp_path / "data" / ".staging",
            embedder=FakeEmbedder(),
            run_id="run-123",
        )
```

实际测试里不要硬编码 hash 结果不透明的 `doc_<expected>`；可以断言 `summary.committed_document_ids == [summary.documents[0].document_id]`，并验证正式目录存在对应文件。

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_run_incremental_import_returns_committed_summary tests/unit/services/test_incremental_import.py::test_run_incremental_import_rejects_multiple_sources -q`

Expected: FAIL，因为 `run_incremental_import` 尚未实现。

**Step 3: Write minimal implementation**

实现 `run_incremental_import(...)`：

```python
def run_incremental_import(
    *,
    sources: Sequence[Path],
    data_dir: Path,
    index_dir: Path,
    manifest_path: Path,
    staging_root: Path,
    embedder: Any,
    run_id: str | None = None,
) -> IncrementalImportSummary:
    ...
```

流程：

1. 若 `len(sources) != 1`，直接抛 `IncrementalImportError("第一版一次只能导入一个法规文件")`；空输入和多文件输入都不得继续。
2. `resolve_explicit_sources(sources)`。
3. `validate_append_only_preflight(...)`。
4. `create_import_staging(...)`。
5. `generate_new_corpus_artifacts(...)`。
6. 对唯一 document 执行 `commit_staged_import(...)`。
7. 返回 summary，包含 `run_id`、`committed_document_ids`、`total_chunks`、`manifest_path`。

未来若要支持多文件导入，必须先设计 run 级原子提交：所有文件先完成 staging 生成、冲突校验和 staged index 生成，再整体提交；在这套机制成熟前，禁止开放多个 `--source`。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 增量导入的预检、staging、语料生成、索引 append 和 manifest 写入被一个服务函数串联。
- 错误统一抛 `IncrementalImportError` 或更具体的冲突错误。
- 编排层没有绕过任何 append-only 门禁。
- 第一版明确拒绝多文件导入。

## Task 11: CLI / 脚本入口

**Files:**
- Create: `scripts/import_new_corpus.py`
- Create: `tests/integration/pipeline/test_incremental_import_cli.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

新增 CLI 参数解析和失败退出测试：

```python
from pathlib import Path
import runpy


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_import_new_corpus_cli_requires_explicit_source(monkeypatch, capsys):
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
```

再补一个成功路径测试，用 monkeypatch 替换 `run_incremental_import`，只验证 CLI 把 `--source`、Settings 路径和 embedder 接线正确传入。

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_cli.py -q`

Expected: FAIL，因为脚本尚不存在。

**Step 3: Write minimal implementation**

`scripts/import_new_corpus.py`：

- 使用 `argparse`。
- 支持 `--source`，但第一版只允许出现一次；多个 `--source` 或解析后 `len(sources) > 1` 时返回 `2`。
- 默认读取 `Settings()`：
  - `data_dir`
  - `index_dir`
  - `manifests_dir / "incremental_imports.json"`
  - `incremental_staging_dir`
  - embedding 相关配置
- 若 `EMBEDDING_MODEL_NAME` 未配置，退出并报错：`未配置 EMBEDDING_MODEL_NAME，无法更新真实向量索引。`
- 构造 `SentenceTransformerEmbedder`，调用 `run_incremental_import(...)`。
- 成功时打印：
  - `run_id=...`
  - `documents=...`
  - `chunks=...`
  - `manifest=...`
  - `warning=第一版只做机械冲突检测；语义重复法规无法仅靠文件名或 hash 完整识别`
- 冲突或校验失败返回 `1`；参数错误返回 `2`。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_cli.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 用户有一个明确脚本入口执行增量导入。
- CLI 不自动扫描目录，不支持后台监听，也不支持多文件导入。
- CLI 输出明确提醒：语义重复法规无法靠文件名或 hash 完整识别，第一版只做机械冲突检测。
- CLI 错误码能区分参数错误和导入失败。

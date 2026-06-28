# 显式新法规 Append-Only 全链路局部增量导入机制 Implementation Plan

> This plan is intended for direct batch execution in the current workspace.

**Goal:** 为用户显式指定的全新 `.doc/.docx` 法规文件提供 append-only 局部增量导入能力，失败时不污染现有 `data/` 与 `data/index/` 正式产物。

**Architecture:** 保留现有全量入口 `scripts/build_corpus.py` 与 `scripts/build_index.py` 不变，新增一个显式增量入口和一组服务层能力：先在 staging 目录生成新增法规的 `normalized/structured/chunks/index` 临时产物，并把旧 `retrieval.db`、`faiss.index`、`vector_map.json` 复制或重建为 staged index artifacts；所有 staged artifacts 校验通过后，再以两阶段提交发布新增语料、关键词索引、向量索引和 manifest。第一版只做法规级 append-only，不做条文级 diff、旧法规修订替换、删除、多文件导入或后台监听。

**Tech Stack:** Python 3.14、Pydantic Settings、Python 标准库 `argparse/json/sqlite3/pathlib/os/tempfile/shutil`、SQLite FTS5、FAISS、pytest；无需新增依赖，所有代码和测试命令必须使用 `conda run -n fire ...`。

---

## 计划说明

- 本计划只用于实现规划，不在本轮实现代码。
- 执行本计划前，如果需要查询技术文档，必须优先查询最新官方文档；若涉及联网检索、网页抓取、站点映射或内容提取，只能使用 Firecrawl、Exa 或 Tavily。
- 每个任务都按 TDD 执行：先写失败测试，再运行红测，再写最小实现，再运行绿测，最后记录 checkpoint。
- 每个任务默认依赖情况均为：**无需新增依赖，沿用 `fire` 环境。** 若实际执行时发现缺少依赖，必须先向用户报备依赖清单、安装环境 `fire` 和原因，得到确认后才能安装。
- 现有事实：`scripts/build_corpus.py` 和 `scripts/build_index.py` 是全量入口；`app/services/keyword_index.py::build_keyword_index` 当前会 `unlink` 重建 `retrieval.db`；`app/services/vector_index.py::build_vector_index` 当前会重建 `faiss.index` 与 position 型 `vector_map.json`；`data/manifests/` 尚不存在。
- 新增能力必须保持 append-only：冲突时直接失败、停止，不跳过、不覆盖、不替换。
- 冲突包括但不限于：同 `document_id`、正式输出文件已存在、manifest 已记录、关键词索引已有该 `document_id`、向量映射已有该 `document_id`、输入文件不是 `.doc/.docx`、输入文件不是全新法规。
- 真实验证要求：新增或修改测试后，先运行对应测试，再基于真实上游产物 `法律文本/`、`data/normalized/`、`data/structured/`、`data/chunks/`、`data/index/` 做 smoke。

## 拟新增命令

```bash
conda run -n fire python scripts/import_new_corpus.py \
  --source /absolute/path/to/new-law.docx
```

第一版不支持自动扫描目录，也不支持一次导入多个文件。用户必须显式传入且只能传入一个新增法规文件；`len(sources) > 1` 属于参数错误，应直接失败。

## 拟新增正式产物

- `data/manifests/incremental_imports.json`：记录每次已成功提交的新增法规导入状态。
- `data/.staging/incremental-import-<run_id>/`：导入过程中的临时目录。提交成功后可删除；失败时默认保留以便排查，正式 `data/normalized`、`data/structured`、`data/chunks`、`data/index` 不应被污染。

## Task 1: 增量导入 Settings 与路径约定

**Files:**
- Modify: `app/core/settings.py`
- Modify: `tests/unit/core/test_settings.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

在 `tests/unit/core/test_settings.py` 增加路径默认值和 `DATA_DIR` 覆盖测试：

```python
from pathlib import Path

from app.core.settings import Settings


def test_settings_build_incremental_import_paths():
    settings = Settings.model_validate({})

    assert settings.manifests_dir == Path("data") / "manifests"
    assert settings.incremental_staging_dir == Path("data") / ".staging"


def test_settings_build_incremental_paths_from_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "custom-data"))

    settings = Settings()

    assert settings.data_dir == tmp_path / "custom-data"
    assert settings.manifests_dir == tmp_path / "custom-data" / "manifests"
    assert settings.incremental_staging_dir == tmp_path / "custom-data" / ".staging"
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/core/test_settings.py::test_settings_build_incremental_import_paths -q`

Expected: FAIL，因为 `Settings` 还没有 `manifests_dir` 和 `incremental_staging_dir`。

**Step 3: Write minimal implementation**

在 `app/core/settings.py` 的 `Settings` 增加从 `data_dir` 派生的只读属性，不要硬编码 `Path("data") / ...`：

```python
@property
def manifests_dir(self) -> Path:
    return self.data_dir / "manifests"

@property
def incremental_staging_dir(self) -> Path:
    return self.data_dir / ".staging"
```

不要改变现有 `data_dir`、`raw_corpus_dir`、`index_dir` 默认值。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/core/test_settings.py::test_settings_build_incremental_import_paths -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 配置层明确区分正式 manifest 目录与 staging 目录，且二者始终从当前 `data_dir` 派生。
- 未新增环境依赖，未安装包。
- 现有全量构建入口不受影响。

## Task 2: Manifest / Build-State 数据模型与原子写入

**Files:**
- Create: `app/services/incremental_manifest.py`
- Create: `tests/unit/services/test_incremental_manifest.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

在 `tests/unit/services/test_incremental_manifest.py` 增加 manifest 读写和重复记录测试：

```python
from pathlib import Path

import pytest

from app.services.incremental_manifest import (
    IncrementalImportManifest,
    ManifestConflictError,
    append_import_record,
    load_manifest,
)


def test_manifest_append_records_document_once(tmp_path: Path):
    manifest_path = tmp_path / "incremental_imports.json"

    append_import_record(
        manifest_path,
        document_id="new_fire_rule",
        source_name="新消防规定",
        source_path="/tmp/新消防规定.docx",
        chunk_count=2,
        run_id="run-1",
    )

    manifest = load_manifest(manifest_path)
    assert isinstance(manifest, IncrementalImportManifest)
    assert [item.document_id for item in manifest.imports] == ["new_fire_rule"]
    assert manifest.imports[0].status == "committed"

    with pytest.raises(ManifestConflictError, match="manifest 已记录"):
        append_import_record(
            manifest_path,
            document_id="new_fire_rule",
            source_name="新消防规定",
            source_path="/tmp/新消防规定.docx",
            chunk_count=2,
            run_id="run-2",
        )
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_manifest.py -q`

Expected: FAIL，因为 `app.services.incremental_manifest` 尚不存在。

**Step 3: Write minimal implementation**

实现：

```python
class ManifestConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class IncrementalImportRecord:
    document_id: str
    source_name: str
    source_path: str
    chunk_count: int
    run_id: str
    status: Literal["committed"]
    imported_at: str


@dataclass(frozen=True)
class IncrementalImportManifest:
    version: int
    imports: list[IncrementalImportRecord]
```

实现 `load_manifest(path)`：

- 文件不存在时返回 `version=1, imports=[]`。
- 文件存在时解析 JSON，校验顶层 `version` 和 `imports`。
- 解析失败时抛 `ValueError("manifest 不是合法 JSON")`，禁止静默重建。

实现 `append_import_record(...)`：

- 若 `document_id` 已存在，抛 `ManifestConflictError("manifest 已记录 document_id: ...")`。
- 写入时先写同目录临时文件，再用 `Path.replace()` 原子替换正式 manifest。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_manifest.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- `data/manifests/incremental_imports.json` 的格式和重复记录行为已被测试固定。
- manifest 写入具备临时文件到正式文件的原子替换语义。
- 仍未触碰正式 `data/` 产物。

## Task 3: 显式输入文件解析与新法规预检

**Files:**
- Create: `app/services/incremental_import.py`
- Create: `tests/unit/services/test_incremental_import.py`
- Modify: `app/services/corpus_ingestor.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

在 `tests/unit/services/test_incremental_import.py` 增加显式文件解析和扩展名拒绝测试：

```python
from pathlib import Path

import pytest

from app.services.incremental_import import IncrementalImportError, resolve_explicit_sources


def test_resolve_explicit_sources_accepts_only_doc_and_docx(tmp_path: Path):
    docx_path = tmp_path / "新消防规定.docx"
    docx_path.write_text("placeholder", encoding="utf-8")
    pdf_path = tmp_path / "新消防规定.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")

    documents = resolve_explicit_sources([docx_path])

    assert documents[0].source_path == docx_path
    assert documents[0].source_name == "新消防规定"
    assert documents[0].file_type == "docx"
    assert documents[0].document_id.startswith("doc_")

    with pytest.raises(IncrementalImportError, match="第一版只支持 .doc/.docx"):
        resolve_explicit_sources([pdf_path])
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_resolve_explicit_sources_accepts_only_doc_and_docx -q`

Expected: FAIL，因为 `resolve_explicit_sources` 尚不存在。

**Step 3: Write minimal implementation**

实现 `resolve_explicit_sources(paths: Sequence[Path]) -> list[CorpusDocument]`：

- 输入为空时报 `IncrementalImportError("必须显式指定新增法规文件")`。
- 路径不存在时报错。
- 目录路径报错，第一版不扫描目录。
- 后缀只允许 `.doc` 和 `.docx`。
- 同一次命令中推导出重复 `document_id` 时直接失败。
- 复用 `CorpusDocument` 数据结构和 `corpus_ingestor` 的 `document_id` 推导逻辑；如 `_build_document_id` 当前是私有函数，可以新增公开薄包装 `build_document_id(source_name: str)`，避免复制算法。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_resolve_explicit_sources_accepts_only_doc_and_docx tests/unit/services/test_corpus_ingestor.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 增量导入入口只接受用户显式指定的 `.doc/.docx` 文件。
- 不支持 PDF/TXT/网页，不支持目录自动扫描。
- `document_id` 推导与现有全量发现逻辑保持一致。

## Task 4: 全量冲突检测门禁

**Files:**
- Modify: `app/services/incremental_import.py`
- Modify: `tests/unit/services/test_incremental_import.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

在 `tests/unit/services/test_incremental_import.py` 增加正式产物和索引冲突测试：

```python
import json
import sqlite3
from pathlib import Path

import pytest

from app.services.incremental_import import IncrementalImportError, validate_append_only_preflight
from app.services.corpus_ingestor import CorpusDocument


def test_preflight_fails_when_document_already_exists_in_outputs_or_indexes(tmp_path: Path):
    data_dir = tmp_path / "data"
    index_dir = data_dir / "index"
    manifests_dir = data_dir / "manifests"
    (data_dir / "normalized").mkdir(parents=True)
    (data_dir / "structured").mkdir(parents=True)
    (data_dir / "chunks").mkdir(parents=True)
    index_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)

    document = CorpusDocument(
        document_id="new_fire_rule",
        source_path=tmp_path / "新消防规定.docx",
        source_name="新消防规定",
        file_type="docx",
    )
    (data_dir / "normalized" / "new_fire_rule.txt").write_text("exists", encoding="utf-8")

    with pytest.raises(IncrementalImportError, match="正式输出文件已存在"):
        validate_append_only_preflight(
            [document],
            data_dir=data_dir,
            index_dir=index_dir,
            manifest_path=manifests_dir / "incremental_imports.json",
        )
```

后续在同一个测试文件补齐参数化场景：

- `data/structured/<document_id>.json` 已存在。
- `data/chunks/<document_id>.jsonl` 已存在。
- manifest 已记录该 `document_id`。
- `retrieval.db` 的 `chunks` 表已有该 `document_id`。
- `vector_map.json` 已有该 `document_id`。

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_preflight_fails_when_document_already_exists_in_outputs_or_indexes -q`

Expected: FAIL，因为 `validate_append_only_preflight` 尚未实现。

**Step 3: Write minimal implementation**

实现 `validate_append_only_preflight(documents, data_dir, index_dir, manifest_path)`：

- 对每个 `document_id` 检查正式输出路径：
  - `data/normalized/<document_id>.txt`
  - `data/structured/<document_id>.json`
  - `data/chunks/<document_id>.jsonl`
- 读取 manifest，若已记录则失败。
- 若 `data/index/retrieval.db` 存在，打开 SQLite 查询：

```sql
SELECT 1 FROM chunks WHERE document_id = ? LIMIT 1
```

查询失败不能当作安全通过；应抛出明确错误。

- 若 `data/index/vector_map.json` 存在，解析并检查任何 row 的 `document_id`。
- 任何冲突都抛 `IncrementalImportError`，错误信息必须包含冲突类型和 `document_id`。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py tests/unit/services/test_incremental_manifest.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 所有 append-only 禁止场景都在正式写入前失败。
- 失败时未写入 staging，也未修改正式 `data/`。
- 关键词索引和向量映射冲突不会被忽略。

## Task 5: Staging 目录生命周期与不可见生成

**Files:**
- Modify: `app/services/incremental_import.py`
- Modify: `tests/unit/services/test_incremental_import.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

增加 staging 创建、失败保留和正式目录不可见测试：

```python
from pathlib import Path

from app.services.incremental_import import create_import_staging


def test_create_import_staging_uses_run_scoped_hidden_directory(tmp_path: Path):
    staging_root = tmp_path / "data" / ".staging"

    staging = create_import_staging(staging_root, run_id="run-123")

    assert staging.root == staging_root / "incremental-import-run-123"
    assert staging.normalized_dir == staging.root / "normalized"
    assert staging.structured_dir == staging.root / "structured"
    assert staging.chunks_dir == staging.root / "chunks"
    assert staging.index_dir == staging.root / "index"
    assert staging.manifest_dir == staging.root / "manifests"
    assert staging.root.exists()
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_create_import_staging_uses_run_scoped_hidden_directory -q`

Expected: FAIL，因为 `create_import_staging` 尚未实现。

**Step 3: Write minimal implementation**

新增：

```python
@dataclass(frozen=True)
class ImportStaging:
    root: Path
    normalized_dir: Path
    structured_dir: Path
    chunks_dir: Path
    index_dir: Path
    manifest_dir: Path
```

实现 `create_import_staging(staging_root, run_id)`：

- `run_id` 只允许安全字符，避免路径穿越。
- 如果同名 staging 已存在，直接失败。
- 一次性创建 `normalized/structured/chunks/index/manifests` 子目录。
- 不创建或修改正式 `data/normalized`、`data/structured`、`data/chunks`、`data/index`。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_create_import_staging_uses_run_scoped_hidden_directory -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 每次增量导入都有独立 staging 根目录。
- 后续语料和索引临时产物都能先写入 staging，正式目录在提交前不可见。

## Task 6: 新法规语料 append 生成器

**Files:**
- Modify: `app/services/incremental_import.py`
- Modify: `tests/unit/services/test_incremental_import.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

增加从单个新增法规生成 staging 语料产物的测试。测试可用 monkeypatch 替换 `normalize_document`，避免在单元层依赖 `textutil`：

```python
import json
from pathlib import Path

from app.services.corpus_ingestor import CorpusDocument
from app.services.incremental_import import create_import_staging, generate_new_corpus_artifacts


def test_generate_new_corpus_artifacts_writes_only_to_staging(tmp_path: Path, monkeypatch):
    document = CorpusDocument(
        document_id="new_fire_rule",
        source_path=tmp_path / "新消防规定.docx",
        source_name="新消防规定",
        file_type="docx",
    )
    document.source_path.write_text("placeholder", encoding="utf-8")
    staging = create_import_staging(tmp_path / "data" / ".staging", run_id="run-123")

    def fake_normalize_document(document, output_dir):
        output_path = output_dir / f"{document.document_id}.txt"
        output_path.write_text("新消防规定\n第一条 新增法规正文。", encoding="utf-8")
        return type("Result", (), {"output_path": output_path, "error_message": None})()

    monkeypatch.setattr("app.services.incremental_import.normalize_document", fake_normalize_document)

    result = generate_new_corpus_artifacts([document], staging)

    assert (staging.normalized_dir / "new_fire_rule.txt").exists()
    assert (staging.structured_dir / "new_fire_rule.json").exists()
    assert (staging.chunks_dir / "new_fire_rule.jsonl").exists()
    assert result[0].document_id == "new_fire_rule"
    assert result[0].chunk_count > 0
    assert not (tmp_path / "data" / "chunks" / "new_fire_rule.jsonl").exists()
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py::test_generate_new_corpus_artifacts_writes_only_to_staging -q`

Expected: FAIL，因为 `generate_new_corpus_artifacts` 尚未实现。

**Step 3: Write minimal implementation**

实现 `generate_new_corpus_artifacts(documents, staging)`：

- 对每个 `CorpusDocument` 执行现有链路：
  - `normalize_document(document, staging.normalized_dir)`
  - `parse_legal_document(document.document_id, normalized_text)`
  - `write_structured_document(parsed, staging.structured_dir)`
  - `build_chunks(...)`
  - `write_chunks(chunks, document.document_id, staging.chunks_dir)`
- 若任何文档标准化失败、结构解析失败或 chunk 为空，直接抛 `IncrementalImportError`。
- 返回包含 `document_id`、三个 staging 文件路径和 `chunk_count` 的结果对象。
- 不写正式目录。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q`

Expected: PASS，允许既有已登记 `xfail` 保持 `xfailed`。

**Step 5: Record the completion checkpoint**

Expected state:

- 新法规的 normalized / structured / chunks 可以在 staging 中完整生成。
- 现有全量语料服务层测试未被破坏。
- 失败时正式 `data/` 仍没有新增文件。

## Task 7: 关键词索引 append-only 事务写入

**Files:**
- Modify: `app/services/keyword_index.py`
- Modify: `tests/unit/services/test_keyword_index.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

在 `tests/unit/services/test_keyword_index.py` 增加 append 成功与重复 `document_id` 失败测试：

```python
import pytest

from app.services.keyword_index import (
    KeywordIndexConflictError,
    append_keyword_index,
    build_keyword_index,
    search_keyword_index,
)


def test_append_keyword_index_adds_new_document_without_rebuilding_existing_rows(tmp_path):
    db_path = tmp_path / "retrieval.db"
    build_keyword_index(
        [
            {
                "chunk_id": "old-1",
                "document_id": "old_doc",
                "title": "旧法规",
                "path": "旧法规 > 第一条",
                "text": "旧消防设施要求。",
                "article_no": "第一条",
                "chapter_title": None,
                "region": None,
                "promulgated_on": None,
                "effective_on": None,
            }
        ],
        db_path,
    )

    append_keyword_index(
        [
            {
                "chunk_id": "new-1",
                "document_id": "new_doc",
                "title": "新法规",
                "path": "新法规 > 第一条",
                "text": "新增消防安全责任。",
                "article_no": "第一条",
                "chapter_title": None,
                "region": None,
                "promulgated_on": None,
                "effective_on": None,
            }
        ],
        db_path,
        document_id="new_doc",
    )

    assert search_keyword_index("旧消防设施", db_path, top_k=5)[0]["chunk_id"] == "old-1"
    assert search_keyword_index("新增消防安全责任", db_path, top_k=5)[0]["chunk_id"] == "new-1"

    with pytest.raises(KeywordIndexConflictError, match="关键词索引已有该 document_id"):
        append_keyword_index([], db_path, document_id="new_doc")
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_keyword_index.py::test_append_keyword_index_adds_new_document_without_rebuilding_existing_rows -q`

Expected: FAIL，因为 `append_keyword_index` 尚不存在。

**Step 3: Write minimal implementation**

在 `app/services/keyword_index.py` 增加：

- `KeywordIndexConflictError(RuntimeError)`。
- `_insert_chunks(connection, chunks)`，让 `build_keyword_index` 与 append 共享插入逻辑，避免复制 SQL。
- `append_keyword_index(chunks, db_path, *, document_id)`：
  - `db_path` 必须存在，否则失败；增量入口不负责创建全量索引。
  - 用 `sqlite3.connect(db_path)` 开启事务。
  - 先查 `SELECT 1 FROM chunks WHERE document_id = ? LIMIT 1`，存在则抛冲突。
  - 校验 `chunks` 非空，且所有 chunk 的 `document_id` 都等于参数 `document_id`。
  - `executemany` 插入新 chunk rows。
  - 任一异常由 SQLite 事务回滚；不得留下半插入 rows。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_keyword_index.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 关键词索引支持事务性 append 新法规 chunk rows。
- 重复 `document_id` 时直接失败。
- 现有 `build_keyword_index` 全量重建行为保持兼容。

## Task 8: 向量索引 append 与 vector_map 一致性校验

**Files:**
- Modify: `app/services/vector_index.py`
- Modify: `app/services/vector_store.py`
- Modify: `tests/unit/services/test_vector_index.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境；使用当前已有 `numpy/faiss-cpu/sentence-transformers`，不得安装新包。

**Step 1: Write the failing test**

在 `tests/unit/services/test_vector_index.py` 增加 append 测试：

```python
import json

import pytest

from app.services.vector_index import (
    VectorIndexConflictError,
    append_vector_index,
    build_vector_index,
)


class AppendableRecordingVectorStore(RecordingVectorStore):
    @property
    def vector_count(self):
        return len(self.vectors)

    @classmethod
    def load(cls, path):
        store = cls(dimension=2)
        store.vectors = [[0.6, 0.8]]
        return store

    def add(self, vectors):
        self.vectors.extend([list(vector) for vector in vectors])


def test_append_vector_index_extends_positions_and_rejects_duplicate_document(tmp_path):
    build_vector_index(
        [{"chunk_id": "old-1", "document_id": "old_doc", "text": "消防安全责任制"}],
        tmp_path,
        embedder=FakeEmbedder(),
        vector_store_factory=lambda dimension: RecordingVectorStore(dimension),
    )

    artifacts = append_vector_index(
        [{"chunk_id": "new-1", "document_id": "new_doc", "text": "损坏消防设施"}],
        tmp_path,
        embedder=FakeEmbedder(),
        document_id="new_doc",
        vector_store_loader=AppendableRecordingVectorStore.load,
    )

    vector_map = json.loads(artifacts.vector_map_path.read_text(encoding="utf-8"))
    assert [item["position"] for item in vector_map] == [0, 1]
    assert [item["document_id"] for item in vector_map] == ["old_doc", "new_doc"]
    assert artifacts.vector_count == 2
    assert artifacts.vector_store.vectors[0] == [0.6, 0.8]
    assert len(artifacts.vector_store.vectors) == 2

    with pytest.raises(VectorIndexConflictError, match="向量映射已有该 document_id"):
        append_vector_index(
            [{"chunk_id": "new-2", "document_id": "new_doc", "text": "重复"}],
            tmp_path,
            embedder=FakeEmbedder(),
            document_id="new_doc",
            vector_store_loader=AppendableRecordingVectorStore.load,
        )
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/unit/services/test_vector_index.py::test_append_vector_index_extends_positions_and_rejects_duplicate_document -q`

Expected: FAIL，因为 `append_vector_index` 尚不存在。

**Step 3: Write minimal implementation**

实现：

- `VectorIndexConflictError(RuntimeError)`。
- `validate_vector_map(vector_map)`：
  - `position` 必须从 `0` 连续递增到 `len(vector_map)-1`。
  - 每条必须有 `chunk_id` 和 `document_id`。
  - `chunk_id` 不得重复。
- `VectorStore` Protocol 增加 `vector_count: int` 只读属性。
- `FaissVectorStore.vector_count` 返回底层 FAISS index 的 `ntotal`；如果 index 尚未初始化，返回 `0`。
- `append_vector_index(chunks, output_dir, *, embedder, document_id, vector_store_loader=FaissVectorStore.load)`：
  - 要求 `faiss.index` 和 `vector_map.json` 都存在。
  - 加载并校验现有 `vector_map`。
  - append 前必须校验 `store.vector_count == len(existing_vector_map)`；不一致时抛 `ValueError("faiss.index 与 vector_map.json 数量不一致")`。
  - 若现有 map 中已有 `document_id`，抛冲突。
  - 校验新增 chunks 非空，且所有 chunk 的 `document_id` 都等于参数 `document_id`。
  - 编码新增文本、归一化向量、校验维度与现有 store 一致。
  - 新 position 从 `len(existing_map)` 开始追加。
  - `store.add(vectors)` 必须是 append 语义，不能覆盖旧 vectors；fake store 测试必须证明旧 vectors 仍存在。
  - append 后必须校验 `store.vector_count == len(new_vector_map)`。
  - 只写入 staged `faiss.index` 和 staged `vector_map.json`；不得直接替换正式 `data/index/faiss.index` 或正式 `data/index/vector_map.json`。正式替换只允许由 Task 9 的提交层统一执行。

如 `FaissVectorStore` 已有 `load()`、`add()`、`save()`，不要引入新的 FAISS 依赖。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/unit/services/test_vector_index.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 向量索引支持在现有 FAISS store 上追加新法规 vectors。
- `vector_map.json` position 保持连续并与新增 vectors 数量一致。
- `FaissVectorStore.vector_count` / FAISS `ntotal` 与 `vector_map.json` 行数在 append 前后都一致。
- fake store 证明 append 不覆盖旧 vectors。
- 重复 `document_id`、空文本、维度不一致都应失败。

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

## Task 12: 集成测试：成功 append 后旧索引仍可检索，新法规也可检索

**Files:**
- Modify: `tests/integration/pipeline/test_build_pipeline.py`
- Create or Modify: `tests/integration/pipeline/test_incremental_import_pipeline.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

新增小型离线集成测试：

```python
import json
from pathlib import Path

from app.services.keyword_index import search_keyword_index
from app.services.vector_index import load_vector_map
from app.services.incremental_import import run_incremental_import


def test_incremental_import_appends_new_law_without_losing_existing_index(tmp_path, monkeypatch):
    raw_dir = tmp_path / "法律文本"
    data_dir = tmp_path / "data"
    raw_dir.mkdir(parents=True)

    # 复用 test_build_pipeline.py 的 _write_docx，先创建旧法规并运行全量 build_corpus/build_indexes。
    # 然后创建一个不在 raw_dir 自动发现流程中的显式新增 docx。

    new_source = tmp_path / "新增消防规定.docx"
    _write_docx("新增消防规定\n第一条 新增消防设施维护要求。", new_source)

    summary = run_incremental_import(
        sources=[new_source],
        data_dir=data_dir,
        index_dir=data_dir / "index",
        manifest_path=data_dir / "manifests" / "incremental_imports.json",
        staging_root=data_dir / ".staging",
        embedder=FakeEmbedder(),
        run_id="run-append",
    )

    assert summary.total_chunks > 0
    assert search_keyword_index("国家实行消防安全责任制", data_dir / "index" / "retrieval.db", top_k=5)
    assert search_keyword_index("新增消防设施维护要求", data_dir / "index" / "retrieval.db", top_k=5)

    vector_map = load_vector_map(data_dir / "index" / "vector_map.json")
    positions = [item["position"] for item in vector_map]
    assert positions == list(range(len(vector_map)))
    assert summary.committed_document_ids[0] in {item["document_id"] for item in vector_map}
```

实际测试应沿用当前 `test_build_pipeline.py` 中的 `_write_docx`、`FakeEmbedder`、`RecordingVectorStore`，避免重复大量夹具代码。

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_pipeline.py::test_incremental_import_appends_new_law_without_losing_existing_index -q`

Expected: FAIL，因为增量服务和 append 索引尚未完整实现。

**Step 3: Write minimal implementation**

补齐前序任务中遗漏的集成接线：

- 测试环境中先用全量 `build_corpus.py` 和 `build_indexes(...)` 准备旧 `data/` 与 `data/index/`。
- 增量导入必须只新增一个法规的三类语料文件。
- 关键词检索旧法规和新法规都应命中。
- `vector_map.json` 应包含旧法规和新法规，position 连续。
- staged `retrieval.db`、`faiss.index`、`vector_map.json` 应在提交后一起成为正式索引；不能出现只有关键词索引提交而向量索引未提交的状态。
- manifest 应记录新增法规且状态为 `committed`。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_build_pipeline.py tests/integration/pipeline/test_incremental_import_pipeline.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 小型离线流水线证明 append-only 成功路径可用。
- 旧法规检索能力未丢失。
- 新法规可通过关键词索引和向量映射进入检索候选。

## Task 13: 集成测试：冲突失败不污染正式产物

**Files:**
- Modify: `tests/integration/pipeline/test_incremental_import_pipeline.py`
- Modify: `app/services/incremental_import.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

新增重复导入同一法规的集成测试：

```python
import json

import pytest

from app.services.incremental_import import IncrementalImportError, run_incremental_import


def test_incremental_import_duplicate_document_fails_without_new_rows(tmp_path):
    # 先准备旧索引，并成功导入一次 new_source。
    first_summary = run_incremental_import(...)
    vector_map_before = (data_dir / "index" / "vector_map.json").read_text(encoding="utf-8")
    manifest_before = (data_dir / "manifests" / "incremental_imports.json").read_text(encoding="utf-8")
    keyword_count_before = count_keyword_rows(data_dir / "index" / "retrieval.db")

    with pytest.raises(IncrementalImportError, match="document_id"):
        run_incremental_import(... same source ...)

    assert (data_dir / "index" / "vector_map.json").read_text(encoding="utf-8") == vector_map_before
    assert (data_dir / "manifests" / "incremental_imports.json").read_text(encoding="utf-8") == manifest_before
    assert count_keyword_rows(data_dir / "index" / "retrieval.db") == keyword_count_before
```

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_pipeline.py::test_incremental_import_duplicate_document_fails_without_new_rows -q`

Expected: FAIL，直到所有冲突门禁和回滚语义实现完整。

**Step 3: Write minimal implementation**

如测试暴露半写入问题，修正：

- 提交前再次预检。
- 关键词 append 只作用于从正式 `retrieval.db` 复制出来的 staged DB；正式 DB 在最终提交前不得被写入。
- 向量 append 只生成 staged `faiss.index` 与 staged `vector_map.json`；正式向量产物在最终提交前不得被替换。
- manifest 最后写。
- 冲突失败时不移动 staging 语料文件到正式目录。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_pipeline.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 重复导入直接失败。
- 失败后 `retrieval.db`、`vector_map.json`、manifest 和正式语料文件均保持失败前状态。
- staging 可保留，但不会被在线检索读取。

## Task 14: 真实法律文本 smoke 验证

**Files:**
- Create: `tests/integration/pipeline/test_incremental_import_real_smoke.py`

**依赖情况:** 无需新增依赖，沿用 `fire` 环境；若真实 smoke 需要临时复制真实法律文本，只使用本地文件，不安装包。

**Step 1: Write the failing test**

新增一个可控的真实上游 smoke 测试，默认不修改仓库正式 `data/`：

```python
from pathlib import Path
import shutil


def test_incremental_import_real_docx_smoke(tmp_path):
    source = Path("法律文本") / "河北省消防条例.docx"
    if not source.exists():
        pytest.skip("本机缺少真实 docx 法律文本")

    copied_source = tmp_path / "河北省消防条例新增副本.docx"
    shutil.copy2(source, copied_source)

    # 在 tmp_path 内构造一套已有 data/index，再把 copied_source 作为显式新增法规导入。
    # 断言 normalized/structured/chunks/index/manifest 全部成功产生，并且正式产物只在 tmp_path 下变化。
```

注意：为了避免与现有正式 `hebei_xiaofang_tiaoli` 冲突，复制文件必须改名，让 `document_id` 推导为新的 `doc_<sha1>`。

**Step 2: Run test to verify it fails**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_real_smoke.py -q`

Expected: 初次可能 FAIL，因为真实 smoke 辅助函数尚未补齐；如果本机缺少真实 `.docx`，应 SKIP，而不是误报通过。

**Step 3: Write minimal implementation**

补齐真实 smoke：

- 使用 `tmp_path` 隔离 `RAW_CORPUS_DIR` 和 `DATA_DIR`。
- 先用至少一份真实旧法规生成旧 `data/` 和旧 `data/index/`。
- 将另一份真实 `.docx` 复制并重命名为新增法规显式导入。
- 导入后检查：
  - 新 `normalized` 文本不存在 `HYPERLINK`、`http://`、`https://`、`\\l "#"` 残留。
  - 新 `structured` 可解析且 articles 非空。
  - 新 `chunks` 非空且每行合法 JSON。
  - `retrieval.db` 可检索新法规关键词。
  - `vector_map.json` position 连续。
  - manifest 有且只有一条本次新增记录。

**Step 4: Run test to verify it passes**

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_real_smoke.py -q`

Expected: PASS 或在真实 `.docx` 缺失时明确 SKIP。

同时运行回归：

Run: `conda run -n fire python -m pytest tests/unit/services/test_incremental_import.py tests/unit/services/test_keyword_index.py tests/unit/services/test_vector_index.py tests/integration/pipeline/test_incremental_import_pipeline.py -q`

Expected: PASS。

**Step 5: Record the completion checkpoint**

Expected state:

- 增量导入已用真实法律文本在隔离临时目录验证。
- 新增或修改测试已补做真实上游产物验证。

## Task 15: README 与工程文档更新

**Files:**
- Modify: `README.md`
- Modify: `docs/工程技术标准.md`
- Modify: `docs/文档索引.md` only if新增计划需要被索引长期引用

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

文档任务不强制新增代码测试；先用文本检查命令确认当前 README 未记录增量导入入口：

```bash
rg -n "import_new_corpus|增量导入|append-only|data/manifests" README.md docs/工程技术标准.md docs/文档索引.md
```

Expected: 当前命令不应完整命中新增入口说明。

**Step 2: Run test to verify it fails**

Run: `rg -n "conda run -n fire python scripts/import_new_corpus.py|data/manifests/incremental_imports.json" README.md docs/工程技术标准.md`

Expected: 无完整命中，说明文档尚未同步。

**Step 3: Write minimal implementation**

更新文档：

- `README.md`：
  - 在建库/语料章节补充增量导入命令。
  - 明确第一版只支持用户显式指定一个 `.doc/.docx` 新法规。
  - 明确第一版不支持多文件导入；多文件导入需要等 run 级原子提交成熟后再开放。
  - 明确冲突直接失败，不跳过、不覆盖。
  - 明确 CLI 输出中的风险说明：语义重复法规无法靠文件名或 hash 完整识别，第一版只做机械冲突检测。
- `docs/工程技术标准.md`：
  - 在“建库产物一致性”补充 append-only 增量导入规则。
  - 说明 `data/manifests/` 是增量导入 build-state，`data/.staging/` 是临时不可见产物。
  - 说明关键词索引和向量索引必须先在 staging 中形成一组一致的新索引，再统一提交。
  - 保持“新增或修改测试后必须真实上游验证”的规则。
- `docs/文档索引.md`：
  - 若希望新会话能长期发现本计划，则补一条实施计划索引；否则可不改。

**Step 4: Run test to verify it passes**

Run: `rg -n "conda run -n fire python scripts/import_new_corpus.py|data/manifests/incremental_imports.json|data/.staging" README.md docs/工程技术标准.md`

Expected: 命中新入口、manifest 和 staging 说明。

如实现阶段修改了文档后，还应运行相关测试回归：

Run: `conda run -n fire python -m pytest tests/integration/pipeline/test_incremental_import_pipeline.py tests/integration/pipeline/test_incremental_import_real_smoke.py -q`

Expected: PASS 或真实 smoke 明确 SKIP。

**Step 5: Record the completion checkpoint**

Expected state:

- 用户能从 README 找到增量导入命令。
- 工程标准记录 append-only、manifest、staging、冲突失败和真实验证规则。

## Testing Strategy

- Unit tests:
  - `tests/unit/core/test_settings.py`
  - `tests/unit/services/test_incremental_manifest.py`
  - `tests/unit/services/test_incremental_import.py`
  - `tests/unit/services/test_keyword_index.py`
  - `tests/unit/services/test_vector_index.py`
- Integration tests:
  - `tests/integration/pipeline/test_incremental_import_cli.py`
  - `tests/integration/pipeline/test_incremental_import_pipeline.py`
  - Existing `tests/integration/pipeline/test_build_pipeline.py`
- Real upstream smoke:
  - `tests/integration/pipeline/test_incremental_import_real_smoke.py`
  - 必须基于本机真实 `.doc/.docx` 法律文本复制到 `tmp_path` 后验证，不直接污染正式 `data/`。
- Required command pattern:
  - `conda run -n fire python -m pytest <test-path> -q`
  - 不允许直接使用系统 Python 或 base conda 环境运行代码、测试或服务。
- Final regression after implementation:

```bash
conda run -n fire python -m pytest \
  tests/unit/core/test_settings.py \
  tests/unit/services/test_incremental_manifest.py \
  tests/unit/services/test_incremental_import.py \
  tests/unit/services/test_keyword_index.py \
  tests/unit/services/test_vector_index.py \
  tests/integration/pipeline/test_build_pipeline.py \
  tests/integration/pipeline/test_incremental_import_cli.py \
  tests/integration/pipeline/test_incremental_import_pipeline.py \
  tests/integration/pipeline/test_incremental_import_real_smoke.py \
  -q
```

## Risks & Mitigations

- **Risk:** FAISS index 写入成功但 `vector_map.json` 写入失败，导致索引和 map 不一致。
  - Mitigation: 始终先写 staged FAISS 和 staged map；append 前校验 `store.vector_count == len(existing_vector_map)`，append 后校验 `store.vector_count == len(new_vector_map)`，并校验 map position 连续后再提交正式产物。
- **Risk:** SQLite FTS5 append 过程中半插入。
  - Mitigation: `append_keyword_index` 必须使用单连接事务，且只写 staged DB；异常自动回滚；失败测试检查正式 DB row count 不变。
- **Risk:** staged keyword append 成功后，vector append 或 manifest 写入失败。
  - Mitigation: 正式 `retrieval.db` 在最终提交前不被写入；Task 9 必须覆盖 staged keyword 成功但后续失败时正式 DB row count 不变。
- **Risk:** 语料文件发布覆盖已有正式文件。
  - Mitigation: 发布 `normalized/structured/chunks` 时禁止 `Path.replace()`；必须使用 `open("xb")` 或 `os.link()` 这类独占创建语义，目标存在即失败。
- **Risk:** staging 生成成功后，正式目录被其他进程写入同 `document_id`。
  - Mitigation: 提交前再次执行完整 preflight。第一版不做跨进程锁，但不允许跳过二次检查。
- **Risk:** manifest 与正式产物不一致。
  - Mitigation: manifest 最后写；启动前和提交前都检查 manifest 冲突；Task 9 必须覆盖 manifest 写入失败时的完整回滚，断言正式 `retrieval.db` row count、`faiss.index` 或 fake vector count、`vector_map.json`、语料文件和 manifest 都恢复到提交前状态；真实 smoke 验证 manifest 与正式文件、索引一致。
- **Risk:** 用户把旧法规修订版当作“新增法规”传入。
  - Mitigation: 第一版只做机械 append-only 门禁；若 `document_id`、输出文件、索引或 manifest 任何一处冲突，直接失败。条文级 diff 和法规替换明确不做。
- **Risk:** 未知中文文件名 hash 成新 `document_id`，但语义上其实是旧法规。
  - Mitigation: 计划执行时可以在 CLI 输出导入前 summary，展示推导的 `document_id/source_name/source_path` 并要求用户显式命令触发；第一版不自动判断语义重复。
- **Risk:** 多文件导入中途失败造成部分提交。
  - Mitigation: 第一版直接限制一次只能导入一个文件；未来只有在 run 级原子提交成熟后才开放多文件。

## Success Criteria

- [ ] 用户可通过 `conda run -n fire python scripts/import_new_corpus.py --source <new-law.docx>` 显式导入一个全新法规。
- [ ] 第一版只接受单个 `.doc/.docx` 文件，拒绝 PDF/TXT/网页/目录自动扫描和多文件导入。
- [ ] 同 `document_id`、正式输出文件已存在、manifest 已记录、关键词索引已有记录、向量映射已有记录时全部直接失败。
- [ ] 成功导入后新增 `normalized/structured/chunks` 正式文件，旧文件不被覆盖。
- [ ] 成功导入后 `retrieval.db` 保留旧法规 rows，并新增新法规 rows；失败时正式 DB row count 不变。
- [ ] 成功导入后 `faiss.index` 追加 vectors，`vector_map.json` position 连续且包含新法规 chunks，且 `vector_count/ntotal == len(vector_map)`。
- [ ] 失败时正式 `data/normalized`、`data/structured`、`data/chunks`、`data/index`、`data/manifests` 不出现半成品。
- [ ] manifest 写入失败必须有回滚测试覆盖，确认正式关键词索引、向量索引、`vector_map.json`、语料文件和 manifest 都恢复到提交前状态；无法完全恢复时只能走包含人工修复指引的严重错误兜底。
- [ ] manifest 只记录已完整提交的新增法规导入状态。
- [ ] 单元测试、集成测试和真实法律文本 smoke 均在 `fire` 环境运行。
- [ ] README 和工程技术标准在实现完成后记录命令、manifest、staging 和冲突失败边界。

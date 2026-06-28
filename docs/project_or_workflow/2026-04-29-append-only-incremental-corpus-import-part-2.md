# 显式新法规 Append-Only 增量导入实施计划（分卷二）

> 本文为实施计划分卷二；分卷导航见[实施计划总览](./2026-04-29-append-only-incremental-corpus-import.md)。

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

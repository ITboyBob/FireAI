# 显式新法规 Append-Only 全链路局部增量导入机制 Implementation Plan

> 本文为实施计划分卷一；分卷导航见[实施计划总览](./2026-04-29-append-only-incremental-corpus-import.md)。

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

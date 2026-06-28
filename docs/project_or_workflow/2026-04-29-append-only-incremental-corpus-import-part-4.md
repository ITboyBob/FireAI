# 显式新法规 Append-Only 增量导入实施计划（分卷四）

> 本文为实施计划分卷四；分卷导航见[实施计划总览](./2026-04-29-append-only-incremental-corpus-import.md)。

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
- Modify: `docs/architecture_or_strategy/工程技术标准.md`
- Modify: `docs/system_meta/文档索引.md` only if新增计划需要被索引长期引用

**依赖情况:** 无需新增依赖，沿用 `fire` 环境。

**Step 1: Write the failing test**

文档任务不强制新增代码测试；先用文本检查命令确认当前 README 未记录增量导入入口：

```bash
rg -n "import_new_corpus|增量导入|append-only|data/manifests" README.md docs/architecture_or_strategy/工程技术标准.md docs/system_meta/文档索引.md
```

Expected: 当前命令不应完整命中新增入口说明。

**Step 2: Run test to verify it fails**

Run: `rg -n "conda run -n fire python scripts/import_new_corpus.py|data/manifests/incremental_imports.json" README.md docs/architecture_or_strategy/工程技术标准.md`

Expected: 无完整命中，说明文档尚未同步。

**Step 3: Write minimal implementation**

更新文档：

- `README.md`：
  - 在建库/语料章节补充增量导入命令。
  - 明确第一版只支持用户显式指定一个 `.doc/.docx` 新法规。
  - 明确第一版不支持多文件导入；多文件导入需要等 run 级原子提交成熟后再开放。
  - 明确冲突直接失败，不跳过、不覆盖。
  - 明确 CLI 输出中的风险说明：语义重复法规无法靠文件名或 hash 完整识别，第一版只做机械冲突检测。
- `docs/architecture_or_strategy/工程技术标准.md`：
  - 在“建库产物一致性”补充 append-only 增量导入规则。
  - 说明 `data/manifests/` 是增量导入 build-state，`data/.staging/` 是临时不可见产物。
  - 说明关键词索引和向量索引必须先在 staging 中形成一组一致的新索引，再统一提交。
  - 保持“新增或修改测试后必须真实上游验证”的规则。
- `docs/system_meta/文档索引.md`：
  - 若希望新会话能长期发现本计划，则补一条实施计划索引；否则可不改。

**Step 4: Run test to verify it passes**

Run: `rg -n "conda run -n fire python scripts/import_new_corpus.py|data/manifests/incremental_imports.json|data/.staging" README.md docs/architecture_or_strategy/工程技术标准.md`

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

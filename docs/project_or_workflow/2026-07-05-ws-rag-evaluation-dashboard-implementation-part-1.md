# W-S RAG 评测 Dashboard 实施计划分卷一：共享契约与 loader

> 本分卷执行 Phase 1。开始前先读取 [计划总览](./2026-07-05-ws-rag-evaluation-dashboard-implementation.md) 和 [数据契约](../architecture_or_strategy/2026-07-05-ws-rag-evaluation-dashboard-data-contract.md)。

## Task 1：冻结共享契约前置条件

**依赖：** 无需新增依赖，沿用 `fire` 环境。
**文件：**

- Read: `scripts/eval_ws_rag/report_models.py`
- Read: `tests/eval_ws_rag/fixtures/`
- Modify: `tests/eval_ws_rag/test_dashboard_loader.py`

### Step 1：检查主评测产物

**意图：** 确认 Dashboard 不会复制 schema。

```bash
rg -n "class .*Report|schema_version|dataset_fingerprint|protocol_fingerprint" scripts/eval_ws_rag tests/eval_ws_rag
```

**预期输出：** 能定位共享 Run schema、稳定失败代码和至少一份合法 Run fixture。

若缺失，停止 Phase 1，先按主评测实施计划完成对应 Task。

### Step 2：写共享契约导入测试

测试名：

```python
def test_dashboard_loader_reuses_shared_report_models():
    from scripts.eval_ws_rag import report_models
    assert report_models.EvaluationReport.model_fields["schema_version"]
```

### Step 3：运行并确认测试状态

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py::test_dashboard_loader_reuses_shared_report_models -q
```

**预期输出：** 若 loader 尚不存在，测试因 import 缺失 FAIL；不得因重新定义本地模型而通过。

### Step 4：创建 loader 最小入口

Create: `scripts/eval_ws_rag/dashboard_loader.py`

最小实现只导入共享模型并定义 Dashboard 专属异常：

```python
from scripts.eval_ws_rag.report_models import ErrorReport, EvaluationReport

class DashboardRunError(ValueError):
    pass
```

### Step 5：再次运行

**预期输出：** 该测试 PASS。

### Step 6：记录检查点

完成状态：Dashboard loader 复用共享 schema，没有第二套报告模型。

## Task 2：TDD 实现 Run 发现与排序

**依赖：** 无需新增依赖。
**文件：**

- Modify: `scripts/eval_ws_rag/dashboard_loader.py`
- Modify: `tests/eval_ws_rag/test_dashboard_loader.py`

### Step 1：写失败测试

至少包含：

```python
def test_discover_runs_ignores_staging_hidden_and_symlink(tmp_path): ...
def test_discover_runs_sorts_by_created_at_desc(tmp_path): ...
def test_discover_runs_rejects_directory_run_id_mismatch(tmp_path): ...
```

fixture 必须同时创建：

- 两个合法 Run，目录 mtime 与 `created_at` 顺序相反；
- 一个 `.<run_id>.tmp`；
- 一个缺少 `errors.json` 的目录；
- 一个符号链接；
- 一个目录名与 JSON `run_id` 不一致的目录。

### Step 2：运行并确认失败

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py -k "discover_runs" -q
```

**预期输出：** FAIL，原因是 `discover_runs` 尚未实现。

### Step 3：实现最小接口

```python
def discover_runs(root_dir: Path) -> RunCatalog:
    ...
```

`RunCatalog` 分开保存：

- `valid_runs`：完整且校验通过；
- `invalid_runs`：路径、稳定错误代码和简短原因。

实现要求：

- 只枚举一级真实目录；
- 拒绝符号链接和根目录逃逸；
- 忽略隐藏/暂存目录；
- 同时读取两份文件并复用共享 schema；
- 按 `created_at` 倒序，不按 mtime 代表评测时间；
- 不删除、不改名、不修复任何目录。

### Step 4：运行目标测试

**预期输出：** `discover_runs` 相关测试全部 PASS。

### Step 5：补边界测试

```python
def test_discover_runs_empty_root_returns_empty_catalog(tmp_path): ...
def test_discover_runs_missing_root_returns_empty_catalog(tmp_path): ...
def test_discover_runs_unknown_major_is_invalid(tmp_path): ...
```

### Step 6：运行 loader 测试

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py -q
```

**预期输出：** 全部 PASS。

### Step 7：记录检查点

完成状态：Dashboard 只能发现完整合法 Run，并能把非法 Run 转成可展示诊断。

## Task 3：TDD 实现不可变快照

**依赖：** 无需新增依赖。
**文件：**

- Modify: `scripts/eval_ws_rag/dashboard_loader.py`
- Modify: `tests/eval_ws_rag/test_dashboard_loader.py`

### Step 1：写失败测试

```python
def test_build_snapshot_keeps_previous_snapshot_when_refresh_fails(): ...
def test_build_snapshot_selects_latest_when_current_run_disappears(): ...
```

### Step 2：运行失败测试

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py -k "snapshot" -q
```

**预期输出：** FAIL，原因是快照接口尚未实现。

### Step 3：实现最小接口

```python
def build_snapshot(root_dir: Path, current_run_id: str | None) -> DashboardSnapshot:
    ...
```

快照必须一次性包含：

- 有效和非法 Run 目录清单；
- 当前 Run；
- 加载时间；
- 只读展示数据。

构建失败时抛稳定异常，由页面保留旧快照；不得返回一半新、一半旧的数据。

### Step 4：运行测试

**预期输出：** snapshot 测试 PASS。

### Step 5：记录检查点

完成状态：刷新可以整体替换快照，不会产生旧新混合页面。

## Task 4：TDD 实现比较门禁和展示派生

**依赖：** 无需新增依赖。
**文件：**

- Modify: `scripts/eval_ws_rag/dashboard_loader.py`
- Modify: `tests/eval_ws_rag/test_dashboard_loader.py`

### Step 1：写比较失败测试

```python
def test_compare_blocks_different_dataset_fingerprint(): ...
def test_compare_blocks_different_protocol_fingerprint(): ...
def test_compare_blocks_unaligned_question_ids(): ...
def test_compare_allows_system_version_changes(): ...
```

### Step 2：确认失败

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py -k "compare" -q
```

**预期输出：** FAIL，原因是比较接口缺失。

### Step 3：实现门禁结果

```python
def assess_comparability(
    baseline: RunRecord,
    current: RunRecord,
) -> ComparisonAssessment:
    ...
```

`ComparisonAssessment` 必须包含：

- `comparable`；
- 稳定 `reason_codes`；
- 可并排展示的元信息；
- 仅在同口径时存在的差值。

### Step 4：实现展示派生

允许派生：

- `failure_reasons[].code` 计数；
- `errors[].stage` 计数；
- 同口径 Run 的指标差值；
- 文件从通过到失败或从失败到通过的状态。

禁止派生：

- 重新计算 `passed`；
- 用 Dashboard 阈值重新计算通过率；
- 在非同口径时计算方向结论。

### Step 5：运行测试

**预期输出：** compare 和全部 loader 测试 PASS。

### Step 6：Phase 1 真实 fixture 验证

**意图：** 用主评测共享 fixture 验证 loader，不只使用测试内临时字典。

```bash
conda run -n fire python -m pytest tests/eval_ws_rag/test_dashboard_loader.py -q
```

**预期输出：** 全部 PASS，无 warning、skip 或 xfail。

### Step 7：Phase 1 提交

提交范围只包括 loader、测试及必要 fixture 调整：

```bash
git commit -m "feat(eval): 实现 Dashboard Run 加载与比较门禁"
```

提交前必须检查 staged diff，不得夹带其他 Phase 或用户改动。

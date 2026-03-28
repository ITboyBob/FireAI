# 标准化与切块重构实施计划

> **给 Claude：** 必须使用 `superpowers:executing-plans` 子技能逐任务执行本计划。

**目标：** 在继续任何索引构建工作之前，修复离线语料链路中的内联超链接污染和切块粒度/超长问题。

**架构：** 本次重构保留现有 `normalized -> structured -> chunks` 离线链路，但收紧两个边界。第一，`Normalizer` 必须删除 Office 内联超链接字段码，同时保留法规可见文本。第二，`ChunkBuilder` 必须支持对超限枚举段落做结构感知的二级切块，并通过“局部重建归因 + 最终全量重建”来保证问题可定位、产物口径一致。

**技术栈：** Python 3.14、pytest、macOS `textutil`、基于正则的文本清洗、JSON/JSONL 夹具、现有 `app/services/*` 模块。

---

## 执行规则

- 所有 Python 与 pytest 命令都必须通过 `conda run -n fire ...` 执行。
- 每次执行代码后都必须更新 [项目状态](../status.md)。
- 本仓库禁止代理执行 git 提交；将提交步骤改为“用户自管检查点”。
- 在本计划完成并通过全量重建验证前，`Task 6` 保持阻塞。

### 任务 1：锁定真实回归夹具

**文件：**
- 新建：`tests/fixtures/normalized/inline_hyperlink_raw.txt`
- 新建：`tests/fixtures/normalized/inline_hyperlink_expected.txt`
- 新建：`tests/fixtures/chunks/xiaofangfa_article_62_structured.json`
- 新建：`tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl`
- 修改：`tests/unit/services/test_normalizer.py`
- 修改：`tests/unit/services/test_chunk_builder.py`

**步骤 1：编写失败测试**

```python
def test_clean_text_strips_inline_hyperlink_field_code():
    raw = '依照《 HYPERLINK "http://example.com" \\l "#" 中华人民共和国治安管理处罚法》的规定处罚。'
    cleaned = clean_text(raw)
    assert cleaned == "依照《中华人民共和国治安管理处罚法》的规定处罚。"


def test_build_chunks_matches_real_structured_fixture():
    structured = json.loads(
        (FIXTURE_DIR / "xiaofangfa_article_62_structured.json").read_text(encoding="utf-8")
    )
    chunks = build_chunks(structured, max_chunk_chars=300)
    expected_lines = (
        FIXTURE_DIR / "xiaofangfa_article_62_expected.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    assert [json.dumps(chunk, ensure_ascii=False) for chunk in chunks] == expected_lines
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_normalizer.py tests/unit/services/test_chunk_builder.py -q`  
预期：失败，因为当前还没有实现真实内联超链接清洗和真实 `structured -> chunks` 回归行为。

**步骤 3：补齐最小真实夹具**

从当前真实语料中裁剪并固化最小样本：
- `inline_hyperlink_raw.txt`：一段真实 `.doc` 风格的内联字段码文本
- `inline_hyperlink_expected.txt`：对应的清洗后期望文本
- `xiaofangfa_article_62_structured.json`：`第六十二条` 的真实结构化片段
- `xiaofangfa_article_62_expected.jsonl`：启用二级切块后的期望 chunk 输出

**步骤 4：重新运行测试，确认只在新行为上失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_normalizer.py tests/unit/services/test_chunk_builder.py -q`  
预期：失败应集中在新断言，而不是缺少夹具文件或测试语法错误。

**步骤 5：用户自管检查点**

暂停，允许用户先审阅真实夹具，再进入代码修改。

### 任务 2：在 `normalizer` 中修复内联超链接清洗

**文件：**
- 修改：`app/services/normalizer.py`
- 修改：`tests/unit/services/test_normalizer.py`

**步骤 1：保持 `normalizer` 红测**

运行：`conda run -n fire python -m pytest tests/unit/services/test_normalizer.py::test_clean_text_strips_inline_hyperlink_field_code -q`  
预期：失败，因为 `clean_text()` 仍会把内联 `HYPERLINK` 字段码留在输出中。

**步骤 2：编写最小实现**

```python
INLINE_HYPERLINK_PATTERN = re.compile(
    r'\s*HYPERLINK\s+"[^"]+"\s+(?:\\l\s+"[^"]+"\s+)?'
)


def _strip_inline_hyperlink_fields(line: str) -> str:
    return INLINE_HYPERLINK_PATTERN.sub("", line)
```

将它接入 `clean_text()`，位置放在空白归一化之前，确保字段码被删掉，但显示文本仍保留。

**步骤 3：运行 `normalizer` 测试**

运行：`conda run -n fire python -m pytest tests/unit/services/test_normalizer.py -q`  
预期：通过，包括新的内联超链接回归和既有 `normalizer` 测试。

**步骤 4：仅重建受影响的标准化哨兵样本**

运行：`conda run -n fire python -c "from pathlib import Path; from app.services.corpus_ingestor import discover_documents; from app.services.normalizer import normalize_document; docs=discover_documents(Path('法律文本')); target=[d for d in docs if d.document_id=='xiaofangfa_2019'][0]; result=normalize_document(target, Path('data/normalized')); print(result.output_path)"`  
预期：重生成的 `data/normalized/xiaofangfa_2019.txt` 不再含内联 `HYPERLINK` 字段码。

**步骤 5：用户自管检查点**

暂停，允许用户先检查 `xiaofangfa_2019.txt`，再进入下游阶段。

### 任务 3：在新 `normalized` 基础上验证 `structured` 稳定性

**文件：**
- 修改：`tests/unit/services/test_structure_parser.py`
- 可选新建：`tests/fixtures/structured/xiaofangfa_article_62_clean.txt`

**步骤 1：如有必要，新增哨兵回归测试**

```python
def test_parse_legal_document_keeps_title_and_dates_after_inline_hyperlink_cleanup():
    raw = Path("tests/fixtures/structured/xiaofangfa_article_62_clean.txt").read_text(encoding="utf-8")
    document = parse_legal_document("xiaofangfa_2019", raw)
    assert document.title == "中华人民共和国消防法"
    assert document.articles[0].article_no == "第六十二条"
```

只有在现有 `structure_parser` 测试不足以固定该边界时，才新增这条测试。

**步骤 2：运行结构解析回归**

运行：`conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py -q`  
预期：通过；若失败，也只能失败在新加的哨兵测试上。

**步骤 3：仅重建受影响的结构化哨兵样本**

运行：`conda run -n fire python -c "from pathlib import Path; from app.services.structure_parser import parse_legal_document, write_structured_document; text=Path('data/normalized/xiaofangfa_2019.txt').read_text(encoding='utf-8'); doc=parse_legal_document('xiaofangfa_2019', text); out=write_structured_document(doc, Path('data/structured')); print(out)"`  
预期：`data/structured/xiaofangfa_2019.json` 重建后不出现标题、日期、条号回归。

**步骤 4：将结构化摘要与基线对比**

至少核对：
- `title`
- 首条和末条 `article_no`
- `promulgated_on`
- `effective_on`
- 不再出现内联 `HYPERLINK`

预期：除了污染清理外，元数据和结构边界应保持稳定。

**步骤 5：用户自管检查点**

暂停，允许用户先检查结构化哨兵结果，再修改切块逻辑。

### 任务 4：加入结构感知的段内二级切块

**文件：**
- 修改：`app/services/chunk_builder.py`
- 修改：`tests/unit/services/test_chunk_builder.py`
- 修改：`tests/fixtures/chunks/xiaofangfa_article_62_expected.jsonl`

**步骤 1：保持真实 chunk 回归红测**

运行：`conda run -n fire python -m pytest tests/unit/services/test_chunk_builder.py::test_build_chunks_matches_real_structured_fixture -q`  
预期：失败，因为当前超限枚举段落仍会生成过粗或过长的 chunk。

**步骤 2：编写最小实现**

```python
SUBITEM_PATTERN = re.compile(r"(（[一二三四五六七八九十]+）)")


def _split_enumerated_paragraph(paragraph: str, max_chunk_chars: int) -> list[dict[str, str]]:
    # 1. 拆出引导句和枚举子项
    # 2. 将引导句复制到每个子项 chunk
    # 3. 返回 [{"subitem_no": "（一）", "text": "..."}]
```

只在以下条件同时成立时触发：
- 当前按段切块后，某段仍超过 `max_chunk_chars`
- 该段包含可识别的枚举标记

同时扩展输出元数据：
- `subitem_no`
- 当发生二级切块时，`path` 细化为 `... > （一）`

**步骤 3：运行 `chunk_builder` 测试**

运行：`conda run -n fire python -m pytest tests/unit/services/test_chunk_builder.py -q`  
预期：通过，既包括合成样本测试，也包括新的真实夹具回归。

**步骤 4：仅重建 chunk 哨兵样本**

运行：`conda run -n fire python -c "from pathlib import Path; import json; from app.services.chunk_builder import build_chunks, write_chunks; payload=json.loads(Path('data/structured/xiaofangfa_2019.json').read_text(encoding='utf-8')); chunks=build_chunks(payload); out=write_chunks(chunks, payload['document_id'], Path('data/chunks')); print(out)"`  
预期：目标条文的超限问题被消除，且 chunk 路径能够回到具体枚举子项。

**步骤 5：用户自管检查点**

暂停，允许用户先审阅新的切块形态，再扩大重建范围。

### 任务 5：用分阶段重建做根因定位

**文件：**
- 修改：`docs/status.md`

**步骤 1：重建最小受影响子集**

运行：
- `conda run -n fire python -m pytest tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q`
- 重建 `xiaofangfa_2019`
- 重建 1 个 `.docx` 哨兵样本
- 重建 1 个“历史修改前言”哨兵样本

预期：目标测试全部通过，哨兵样本稳定，且变化能够归因到预期阶段。

**步骤 2：记录阶段性摘要**

更新 [项目状态](../status.md)，至少写清：
- 重建了哪些文件
- 哪些产物发生了变化
- 这些变化来自哪个阶段

**步骤 3：若出现意外漂移，立刻停止**

意外漂移包括：
- `title` 变化
- 首条/末条变化
- 日期提取回退
- chunk 数量异常膨胀

**步骤 4：重跑服务层回归**

运行：`conda run -n fire python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q`  
预期：通过，服务层回归全部为绿。

**步骤 5：用户自管检查点**

暂停，在全量重建前让用户做一次检查。

### 任务 6：全量重建离线产物并解除门禁

**文件：**
- 修改：`docs/status.md`

**步骤 1：重建全部离线语料**

按顺序全量重建：
1. `data/normalized/*.txt`
2. `data/structured/*.json`
3. `data/chunks/*.jsonl`

预期：6 份法规全部由同一代代码重新生成。

**步骤 2：将最终产物与基线摘要对比**

至少核对：
- 不再残留内联 `HYPERLINK`
- 当前已知超限 chunk 不再无解释地存在
- `title` / 首条 / 末条 / 日期仍稳定
- chunk 数量和路径变化可解释

**步骤 3：运行最终回归**

运行：`conda run -n fire python -m pytest tests/unit/services/test_corpus_ingestor.py tests/unit/services/test_normalizer.py tests/unit/services/test_structure_parser.py tests/unit/services/test_chunk_builder.py -q`  
预期：通过。

**步骤 4：更新状态并释放门禁**

更新 [项目状态](../status.md)，明确记录：
- 全量重建已完成
- 最终验证结果
- `Task 6` 是否正式解除阻塞

**步骤 5：用户自管检查点**

暂停，待用户确认后，再恢复原主线计划中的 `Task 6`。

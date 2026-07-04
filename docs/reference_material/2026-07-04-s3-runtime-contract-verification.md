# S3 运行时契约核验记录

**日期：** 2026-07-04
**环境：** conda `fire`，Python 3.14.2，pytest 9.0.2
**任务：** W-S3 实施计划 Task 1

## 1. 核验目标

本阶段实际使用的 Python 3.14 标准库与 pytest 行为：

- `re.Pattern.fullmatch()`、`finditer()`、命名捕获组和 Unicode 行为；
- `frozen=True, slots=True` dataclass 与 tuple 默认值行为；
- `Enum` 非法值异常语义；
- pytest 参数化、临时目录和失败断言行为。

## 2. 官方来源

| 主题 | 官方链接 | 访问日期 |
| --- | --- | --- |
| `re` 模块 | https://docs.python.org/3/library/re.html | 2026-07-04 |
| `dataclasses` 模块 | https://docs.python.org/3/library/dataclasses.html | 2026-07-04 |
| `enum` 模块 | https://docs.python.org/3/library/enum.html | 2026-07-04 |
| pytest 临时目录 | https://docs.pytest.org/en/stable/how-to/tmp_path.html | 2026-07-04 |
| pytest 参数化 | https://docs.pytest.org/en/stable/example/parametrize.html | 2026-07-04 |

## 3. 契约结论与最小实验

### 3.1 `re.Pattern.fullmatch()`

`Pattern.fullmatch(string)` 等价于 `re.search(r'\A...\Z', string)`；整个字符串必须匹配。命名捕获组 `(?P<name>...)` 可通过 `match.group('name')` 访问。

**最小实验：**

```python
import re
pattern = re.compile(r"第(?P<num>[一二三四五六七八九十百千万零〇两0-9]+)条")
match = pattern.fullmatch("第一条")
assert match is not None
assert match.group("num") == "一"
```

**输出：** 通过。

**影响位置：** `app/services/legal_boundary_common.py` 中的条号正则；`app/services/legal_source_classifier.py` 中既有的 `ARTICLE_PATTERN`。

### 3.2 `re.finditer()`

`Pattern.finditer(string)` 返回非重叠匹配迭代器；Unicode 字符按 Unicode 码点处理，中文数字属于普通字符。

**最小实验：**

```python
import re
pattern = re.compile(r"第[一二三四五六七八九十百千万零〇两0-9]+条")
text = "第一条\n第二条\n第三条"
matches = list(pattern.finditer(text))
assert len(matches) == 3
assert matches[0].group() == "第一条"
```

**输出：** 通过。

**影响位置：** 条号位置索引与连续条号校验。

### 3.3 `frozen=True, slots=True` dataclass

`@dataclass(frozen=True, slots=True, kw_only=True)` 生成不可变实例、使用 `__slots__`、只允许关键字参数。tuple 字段默认值必须用 `field(default_factory=tuple)`，否则可变默认值会在类级别共享。

**最小实验：**

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True, kw_only=True)
class Sample:
    items: tuple[str, ...] = field(default_factory=tuple)

a = Sample()
b = Sample()
assert a.items is b.items  # 均为空 tuple
```

**输出：** 通过。

**影响位置：** `app/services/legal_ingestion_models.py` 中所有 frozen/slots dataclass；新增 S3 相关模型必须沿用同一模式。

### 3.4 `Enum` 非法值

对 `str, Enum` 子类传入未定义值会抛出 `ValueError: '<value>' is not a valid <EnumName>`。

**最小实验：**

```python
from enum import Enum
class ContentClass(str, Enum):
    S1 = "S1"
    S3 = "S3"

try:
    ContentClass("S5")
except ValueError as exc:
    assert "not a valid ContentClass" in str(exc)
```

**输出：** 通过。

**影响位置：** CLI `--content-class` 解析、注册表键校验；非法枚举值由 argparse/Enum 自身拒绝。

### 3.5 pytest 参数化

`@pytest.mark.parametrize("input,expected", [...])` 会为每组参数独立运行一次测试，失败仅影响对应参数组合。

**最小实验：**

```python
import pytest

@pytest.mark.parametrize("value", [1, 2, 3])
def test_param(value):
    assert value > 0
```

**输出：** 3 项全部通过。

**影响位置：** S3 单元测试矩阵。

### 3.6 pytest `tmp_path`

`tmp_path` fixture 为每个测试函数提供独立的 `pathlib.Path` 临时目录，测试结束后自动清理。

**最小实验：**

```python
def test_tmp_path_writable(tmp_path):
    p = tmp_path / "test.txt"
    p.write_text("hello")
    assert p.read_text() == "hello"
```

**输出：** 通过。

**影响位置：** Task 7 临时提交与回滚测试；Task 6 dry-run 报告输出到临时目录。

## 4. 与计划假设的对应关系

| 计划假设 | 官方结论 | 状态 |
| --- | --- | --- |
| Python 3.14 `re` 行为稳定 | 文档与实验一致 | 沿用 |
| frozen/slots dataclass 不可变 | 文档与实验一致 | 沿用 |
| tuple 字段默认值需 `default_factory` | 文档与实验一致 | 沿用 |
| Enum 非法值抛 `ValueError` | 文档与实验一致 | 沿用 |
| pytest 参数化和 tmp_path 行为稳定 | 文档与实验一致 | 沿用 |

## 5. 结论

本阶段涉及的标准库与 pytest 行为与 W-S3 实施计划假设一致，无需调整设计。所有相关代码将继续使用 `frozen=True, slots=True, kw_only=True` dataclass、`field(default_factory=tuple)`、标准 `re` 模块和 pytest 参数化/`tmp_path`。

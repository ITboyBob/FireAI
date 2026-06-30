# S2 运行时契约核验记录

**核验日期：** 2026-06-30
**角色：** `reference_material`
**适用范围：** W-S2 Task 1—10 涉及的 Python 3.14 标准库契约，特别是 `dataclasses`、`Enum` 与 `argparse`
**依赖结论：** 无需新增依赖，继续使用 conda 环境 `fire`

## 1. Python 3.14 `dataclasses`

官方页面：[dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html)

核验结论：

- `frozen=True` 禁止字段重新赋值，触发 `FrozenInstanceError`（Python 3.14 下冻结与 slots 同时为真时统一为此异常）；
- `slots=True` 生成 `__slots__`，返回新类，禁止在已定义 `__slots__` 的类上重复装饰；
- `kw_only=True` 使 `__init__()` 参数全部按关键字传入，调用方必须写出字段名；
- 继承时子类仍需显式声明 `@dataclass` 并保持一致参数，父类字段排在子类字段之前；
- `dataclasses.asdict()` 会递归处理 dataclass、`dict`、`list`、`tuple`，其中 `tuple` 保持为 `tuple`，不会自动转为 `list`；其他对象使用 `copy.deepcopy()`；
- 可变默认值应使用 `default_factory`，集合型证据优先使用 `tuple`。

最小实验命令与结果：

```bash
conda run -n fire python /tmp/s2_contract_test.py
```

输出节选：

```
child: Child(a='x', b=('y', 'z'))
asdict: {'a': 'x', 'b': ('y', 'z')}
tuple preserved: True
```

**实现影响：**

- `MetadataEvidence` 与 `TargetMetadata` 继续使用 `frozen=True, slots=True, kw_only=True`；
- `TargetMetadata.evidence` 使用 `tuple[MetadataEvidence, ...]`，避免使用 list 作为 frozen dataclass 字段值；
- 如需把中间格式序列化为 dict，`asdict()` 会保留 tuple 结构，不会破坏证据集合类型。

## 2. Python 3.14 `enum`

官方页面：[enum — Support for enumerations](https://docs.python.org/3/library/enum.html)

核验结论：

- 对 `Enum` 子类传入不在成员中的值会抛出 `ValueError`；
- `value in Enum` 返回 `True` 当且仅当该值与某个成员值相等；
- 自定义解析时应优先使用 `try/except ValueError`，而不是先 `in` 再构造。

最小实验命令与结果：

```bash
conda run -n fire python /tmp/s2_contract_test.py
```

输出节选：

```
enum invalid: 'blue' is not a valid Color
```

**实现影响：**

- CLI 与内部转换函数把字符串解析为 `ExtractionClass`/`ContentClass` 时，捕获 `ValueError` 并映射为 `unsupported` 或 `review_required`；
- 分卷三新增 `--extraction-class`、`--content-class` 参数时，`choices` 直接给出字符串枚举值，由调用方显式转换并处理异常。

## 3. Python 3.14 `argparse`

官方页面：[argparse — Parser for command-line options](https://docs.python.org/3/library/argparse.html)

核验结论：

- `choices` 接受任意序列（list、tuple、自定义序列），传入不在序列中的值会产生 `ArgumentError`（默认退出并打印可用选项）；
- `default` 在命令行未出现该选项时使用，不会经过 `choices` 校验；
- 使用 `exit_on_error=False` 可以在测试中捕获 `ArgumentError`；
- 官方文档不建议直接把 `enum.Enum` 作为 `choices`，因为错误消息与帮助文本不易控制；本 CLI 使用字符串序列并在解析后显式转换。

最小实验命令与结果：

```bash
conda run -n fire python /tmp/s2_contract_test.py
```

输出节选：

```
default: S1
choice error: argument --cc: invalid choice: 'S3' (choose from S1, S2)
```

**实现影响：**

- 分卷三为 `import_new_corpus.py` 增加 `--extraction-class` 与 `--content-class`，使用字符串 `choices`；
- 默认保持 `"W"` 与 `"S1"`，使旧命令行为不变；
- 参数解析后由编排器转换为 `ExtractionClass`/`ContentClass`，无效值进入安全的 `unsupported` 处置路径。

## 4. 结论

当前计划关于不可变 dataclass、元组证据集合、枚举字符串解析和 argparse 字符串 `choices`/`default` 的假设在 Python 3.14 下成立。Task 1—10 无需因标准库契约变化而修订技术路线，也无需安装、替换或升级 Python 依赖。

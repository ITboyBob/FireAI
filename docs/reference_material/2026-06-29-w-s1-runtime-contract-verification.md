# W-S1 运行时契约核验记录

**核验日期：** 2026-06-29
**角色：** `reference_material`
**适用范围：** W-S1 Task 5—9 的 macOS `textutil`、Python 3.14 标准库、pytest 与 SQLite 实现假设
**依赖结论：** 无需新增依赖，继续使用 conda 环境 `fire` 与系统 `/usr/bin/textutil`

## 1. 本机 `textutil(1)`

核验方式：

```bash
conda run -n fire sh -lc 'MANPAGER=cat /usr/bin/man textutil | /usr/bin/col -b'
```

本机手册确认：

- `-convert txt` 可以把受支持的 Word 文件转换为纯文本；
- `-stdout` 让第一个输出直接写入标准输出，不要求创建输出文件；
- `-encoding UTF-8` 明确指定纯文本输出编码，无法转换时命令失败；
- 成功退出码为 `0`，失败退出码为 `1`。

**实现影响：** `run_textutil_stdout()` 继续只接收来源路径并捕获标准输出、标准错误和退出码；不接受输出路径，不创建候选文本文件。

## 2. Python 3.14 `subprocess`

官方页面：[subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html)

核验结论：

- `subprocess.run()` 使用参数数组且保持默认 `shell=False`，避免 shell 解释文件名；
- `capture_output=True` 同时捕获标准输出和标准错误；
- `text=True` 配合明确的 `encoding`、`errors` 形成字符串结果；
- `timeout` 超时抛出 `TimeoutExpired`；进程启动前的系统错误以 `OSError` 暴露；
- `check=False` 保留非零退出码，由领域适配器映射为结构化失败。

**实现影响：** 不改用 shell，不吞并超时或系统错误，不把非零退出误判为可继续结果。

## 3. Python 3.14 `dataclasses`

官方页面：[dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html)

核验结论：

- `frozen=True` 阻止字段重新赋值，但不会递归冻结字段内部的可变对象；
- `slots=True` 为值对象生成 slots，减少意外动态属性；
- `kw_only=True` 强制调用方显式写出字段名；
- 可变默认值必须使用 `default_factory`；本链路优先使用 tuple 保存有序证据。

**实现影响：** 提取请求、来源位置、块、页和失败模型继续使用不可变 dataclass；集合型证据使用 tuple，避免把 list 或 dict 藏在 frozen 模型中造成“表面不可变”。

## 4. Python 3.14 `hashlib`

官方页面：[hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html)

核验结论：

- Python 保证提供 `sha256()`；
- 摘要输入是 bytes，`hexdigest()` 生成十六进制字符串；
- 相同 UTF-8 bytes 可形成稳定的跨层正文与报告身份。

**实现影响：** 来源文件继续按原始 bytes 计算 SHA-256；正文先按统一换行和 UTF-8 编码后计算；摘要只证明内容一致，不代替正文结构门禁。

## 5. Python 3.14 `pathlib`

官方页面：[pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html)

核验结论：

- `Path.replace(target)` 会替换同名文件并返回新路径；
- 目标是文件时，已有目标可被无条件替换；
- 原子批次汇总必须先在目标同目录完成临时文件写入，再执行一次 replace。

**实现影响：** Task 9 的可变批次报告使用同目录临时文件加 `Path.replace()`；不可变 attempt 质量报告不得使用 replace，而应独占创建并拒绝覆盖。

## 6. pytest 当前稳定文档

官方页面：[pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html)、[Parametrizing tests](https://docs.pytest.org/en/stable/example/parametrize.html)

核验结论：

- `pytest.raises()` 用于固定非法状态和机械门禁失败；
- `monkeypatch` 的修改在测试结束后自动撤销，适合证明失败发生在 writer 之前；
- `tmp_path` 提供每项测试独立的临时目录；
- `pytest.mark.parametrize` 适合固定 8 份真实 W-S1 验收矩阵。

**实现影响：** Task 8—9 继续使用参数化真实样本和临时报告目录；不增加 skip、xfail 或文件缺失旁路。

## 7. SQLite 事务

官方页面：[Transaction](https://sqlite.org/lang_transaction.html)、[File Locking And Concurrency In SQLite Version 3](https://sqlite.org/lockingv3.html)

核验结论：

- 显式事务由 `BEGIN` 开始，并持续到 `COMMIT` 或 `ROLLBACK`；
- 事务负责 SQLite 内部原子性，不等于跨 normalized、structured、chunks、向量索引和 manifest 的全局事务；
- 当前 append-only 提交流程仍需保留索引备份、文件独占创建和 manifest 最后写。

**实现影响：** Task 8—9 不改动 SQLite 提交边界；Task 10 只在质量资格通过后委托现有两阶段提交，不把批次报告写入增量 manifest。

## 8. 结论

当前计划关于 stdout、UTF-8、参数数组、超时、不可变值对象、SHA-256、同目录文件替换、pytest 验收和 SQLite 事务的假设成立。Task 5—9 无需修订技术路线，也无需安装、替换或升级依赖。

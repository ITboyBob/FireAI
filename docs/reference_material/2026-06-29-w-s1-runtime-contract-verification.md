# W-S1 运行时契约核验记录

**核验日期：** 2026-06-29  
**角色：** `reference_material`  
**适用范围：** W-S1 Task 5—6 的 macOS `textutil`、Python 3.14 `subprocess` 与 `dataclasses` 实现假设  
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

## 4. 结论

当前计划关于 stdout、UTF-8、参数数组、超时和不可变值对象的假设成立。Task 5—6 无需修订技术路线，也无需安装、替换或升级依赖。

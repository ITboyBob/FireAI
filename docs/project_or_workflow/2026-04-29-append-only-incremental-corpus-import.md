# 显式新法规 Append-Only 增量导入实施计划总览

本文是显式新法规 Append-Only 全链路局部增量导入实施计划的分卷入口。现有计划只覆盖单份全新 `.doc/.docx` 法规的增量提交，不覆盖多格式提取设计。

## 分卷

- [分卷一：配置、Manifest、输入解析与冲突门禁](./2026-04-29-append-only-incremental-corpus-import-part-1.md)
- [分卷二：Staging、语料生成与索引追加](./2026-04-29-append-only-incremental-corpus-import-part-2.md)
- [分卷三：两阶段提交、编排服务与 CLI](./2026-04-29-append-only-incremental-corpus-import-part-3.md)
- [分卷四：集成测试、真实验证、文档、风险与成功标准](./2026-04-29-append-only-incremental-corpus-import-part-4.md)

## 读取规则

- 只读取当前任务对应的分卷。
- 涉及正式产物发布时，同时读取分卷三。
- 涉及真实文件验证或最终验收时，读取分卷四。
- 多格式法规处理方案应读取新的多格式摄取总设计，不得从本历史范围自行推导。

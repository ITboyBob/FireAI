---
paths:
  - "tests/**/*"
  - "**/*test*.py"
  - "pytest.ini"
---

# 测试规则

## 测试执行顺序

1. 新增或修改测试后，**先**运行对应的单元/预编写测试。
2. **再**基于真实上游产物（如 `data/normalized`、`data/structured`、`data/chunks` 或真实源文档）补做一轮真实验证。

## 测试环境

- 所有测试必须在 conda 环境 `fire` 中执行。
- 推荐使用 `conda run -n fire pytest ...` 显式执行。

## 验证要求

- 测试通过不代表任务完成，必须通过真实数据验证才能确认功能正确。

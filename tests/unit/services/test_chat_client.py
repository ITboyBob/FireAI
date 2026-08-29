from __future__ import annotations

import pytest

from app.services.chat_client import _build_response_format


# 注意：参数名不可用 `base_url`——pytest-base-url（pytest-playwright 的依赖）
# 注册的会话级 _verify_url fixture 会与函数级参数化参数 base_url 作用域冲突（ScopeMismatch）。
@pytest.mark.parametrize(
    "endpoint,expected_type",
    [
        ("https://api.openai.com/v1", "json_schema"),
        ("https://api.iflow.cn/v1", "text"),
        ("https://ark.cn-beijing.volces.com/api/v3", "text"),
    ],
)
def test_build_response_format_selects_safe_format(endpoint, expected_type):
    fmt = _build_response_format(endpoint)
    assert fmt["type"] == expected_type
    if expected_type == "json_schema":
        assert "json_schema" in fmt

from __future__ import annotations

import pytest

from app.services.chat_client import _build_response_format


@pytest.mark.parametrize(
    "base_url,expected_type",
    [
        ("https://api.openai.com/v1", "json_schema"),
        ("https://api.iflow.cn/v1", "text"),
        ("https://ark.cn-beijing.volces.com/api/v3", "text"),
    ],
)
def test_build_response_format_selects_safe_format(base_url, expected_type):
    fmt = _build_response_format(base_url)
    assert fmt["type"] == expected_type
    if expected_type == "json_schema":
        assert "json_schema" in fmt

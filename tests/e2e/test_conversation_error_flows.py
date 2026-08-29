"""第一批 E2E：前端 404 读取文案区分与流中会话竞态删除分支。

页面由 FastAPI 模板 + 静态资源提供，因此用线程方式启动存活 uvicorn（随机空闲端口）；
全部 `/api/conversations*` API 响应用 `page.route` mock（NDJSON 行尾含换行），
全程不依赖真实模型/索引，也不使用 waitForTimeout（全部依赖 expect 自动等待）。
"""

import json
import os
import re
import socket
import threading
import time
from urllib.parse import urlparse
from urllib.request import urlopen

import pytest
import uvicorn
from playwright.sync_api import Page, Route, expect

from app.core.settings import get_settings
from app.main import create_app


def _reserve_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def live_server_url():
    port = _reserve_free_port()
    previous_embedding_model = os.environ.get("EMBEDDING_MODEL_NAME")
    # 覆盖 .env，避免 lifespan 预热真实嵌入模型（E2E 只需要页面壳与静态资源）。
    os.environ["EMBEDDING_MODEL_NAME"] = "replace-me"
    get_settings.cache_clear()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with urlopen(f"{base_url}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("E2E live server 未能在 15 秒内就绪")
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if previous_embedding_model is None:
            os.environ.pop("EMBEDDING_MODEL_NAME", None)
        else:
            os.environ["EMBEDDING_MODEL_NAME"] = previous_embedding_model
        get_settings.cache_clear()


def _conversation(conversation_id: str, title: str) -> dict:
    return {
        "id": conversation_id,
        "title": title,
        "auto_title": False,
        "updated_at": "2026-04-11T10:00:00Z",
        "last_message_at": None,
    }


def _install_conversation_api_mock(
    page: Page,
    *,
    list_payload: list[dict],
    created_payload: dict,
    detail_status: int,
    detail_payload: dict,
    stream_lines: list[str],
) -> None:
    """拦截全部 /api/conversations* 请求，按 method + path 分派 mock 响应。"""

    def _json_body(payload) -> str:
        return json.dumps(payload, ensure_ascii=False)

    def _handler(route: Route) -> None:
        request = route.request
        path = urlparse(request.url).path
        if request.method == "GET" and path == "/api/conversations":
            route.fulfill(status=200, content_type="application/json", body=_json_body(list_payload))
            return
        if request.method == "POST" and path == "/api/conversations":
            route.fulfill(status=201, content_type="application/json", body=_json_body(created_payload))
            return
        if request.method == "POST" and path.endswith("/messages/stream"):
            route.fulfill(
                status=200,
                content_type="application/x-ndjson",
                body="".join(line + "\n" for line in stream_lines),
            )
            return
        if request.method == "GET" and path.startswith("/api/conversations/"):
            route.fulfill(
                status=detail_status,
                content_type="application/json",
                body=_json_body(detail_payload),
            )
            return
        route.fulfill(status=404, content_type="application/json", body="{}")

    page.route(re.compile(r"/api/conversations"), _handler)


def test_open_deleted_conversation_shows_not_found_copy(live_server_url, page):
    _install_conversation_api_mock(
        page,
        list_payload=[],
        created_payload={},
        detail_status=404,
        detail_payload={"detail": "会话不存在或已删除"},
        stream_lines=[],
    )

    page.goto(f"{live_server_url}/conversations/conv-gone")

    error_panel = page.locator("#error-panel")
    expect(error_panel).to_be_visible()
    expect(error_panel).to_have_text("会话不存在或已删除")
    # 「回到首页」断言视图层（bootstrap 既有 updateUrl 会把地址栏留在原路径，属既有行为，不在本批改动面）。
    expect(page.get_by_test_id("home-composer-input")).to_be_visible()


def test_open_conversation_with_server_error_keeps_generic_copy(live_server_url, page):
    _install_conversation_api_mock(
        page,
        list_payload=[],
        created_payload={},
        detail_status=500,
        detail_payload={"detail": "数据库连接失败"},
        stream_lines=[],
    )

    page.goto(f"{live_server_url}/conversations/conv-gone")

    error_panel = page.locator("#error-panel")
    expect(error_panel).to_be_visible()
    expect(error_panel).to_have_text("数据库连接失败")
    assert "不存在或已删除" not in error_panel.inner_text()
    expect(page.get_by_test_id("home-composer-input")).to_be_visible()


def test_stream_conversation_not_found_returns_home_and_keeps_draft(live_server_url, page):
    _install_conversation_api_mock(
        page,
        list_payload=[_conversation("conv-other", "其他会话")],
        created_payload=_conversation("conv-race", "新会话"),
        detail_status=404,
        detail_payload={"detail": "会话不存在或已删除"},
        stream_lines=[
            json.dumps(
                {
                    "type": "error",
                    "code": "conversation_not_found",
                    "message": "会话不存在或已删除",
                    "retryable": False,
                },
                ensure_ascii=False,
            )
        ],
    )

    page.goto(live_server_url)
    page.get_by_test_id("home-composer-input").fill("测试竞态删除的问题")
    page.get_by_test_id("home-send-button").click()

    error_panel = page.locator("#error-panel")
    expect(error_panel).to_have_text("会话不存在或已删除")
    expect(page).to_have_url(f"{live_server_url}/")
    list_items = page.get_by_test_id("conversation-list-item")
    expect(list_items).to_have_count(1)
    expect(list_items).to_have_text(re.compile("其他会话"))
    expect(page.get_by_test_id("home-composer-input")).to_have_value("测试竞态删除的问题")
    expect(page.get_by_test_id("request-status").first).to_have_text("会话已失效，已返回首页。")


def test_stream_internal_error_after_received_stays_on_thread(live_server_url, page):
    _install_conversation_api_mock(
        page,
        list_payload=[_conversation("conv-1", "历史会话")],
        created_payload=_conversation("conv-1", "历史会话"),
        detail_status=200,
        detail_payload={
            "conversation": _conversation("conv-1", "历史会话"),
            "messages": [],
            "history_summary": "",
        },
        stream_lines=[
            json.dumps(
                {"type": "received", "message": "已收到问题。", "persisted": True},
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "type": "error",
                    "code": "internal_error",
                    "message": "服务内部异常，请稍后重试。",
                    "retryable": True,
                },
                ensure_ascii=False,
            ),
        ],
    )

    page.goto(f"{live_server_url}/conversations/conv-1")
    page.get_by_test_id("thread-composer-input").fill("追问内容")
    page.get_by_test_id("thread-send-button").click()

    error_panel = page.locator("#error-panel")
    expect(error_panel).to_have_text("服务内部异常，请稍后重试。")
    expect(page).to_have_url(f"{live_server_url}/conversations/conv-1")
    expect(page.get_by_test_id("thread-composer-input")).to_be_visible()

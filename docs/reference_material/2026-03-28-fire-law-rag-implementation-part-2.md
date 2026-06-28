# 消防法律 RAG 实施计划（分卷二）

> 本文为历史实施计划分卷二；分卷导航见[实施计划总览](./2026-03-28-fire-law-rag-implementation.md)。

### 任务 6：构建 SQLite FTS5 关键词索引

**文件：**
- 新建：`app/services/keyword_index.py`
- 新建：`tests/unit/services/test_keyword_index.py`
- 新建：`scripts/build_corpus.py`

**步骤 1：编写失败测试**

```python
from app.services.keyword_index import build_keyword_index, search_keyword_index


def test_keyword_index_returns_matching_article(tmp_path):
    chunks = [
        {"chunk_id": "a1", "text": "国家实行消防安全责任制。", "path": "法 > 章 > 第二条"},
        {"chunk_id": "a2", "text": "任何单位不得损坏消防设施。", "path": "法 > 章 > 第二十八条"},
    ]
    db_path = tmp_path / "retrieval.db"
    build_keyword_index(chunks, db_path)
    results = search_keyword_index("消防设施", db_path, top_k=3)
    assert results[0]["chunk_id"] == "a2"
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_keyword_index.py -q`  
预期：因缺少索引函数而失败。

**步骤 3：编写最小实现**

```python
import sqlite3


def build_keyword_index(chunks: list[dict], db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE VIRTUAL TABLE chunks USING fts5(chunk_id, text, path)")
    conn.executemany(
        "INSERT INTO chunks(chunk_id, text, path) VALUES (?, ?, ?)",
        [(c["chunk_id"], c["text"], c["path"]) for c in chunks],
    )
    conn.commit()
    conn.close()
```

随后补充：
- 基于 `bm25()` 的查询排序
- 地域、时间等元数据过滤字段或侧表关联
- `scripts/build_corpus.py` 入口，负责写出标准化文本、结构化结果和 chunks

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_keyword_index.py -q`  
预期：`1 passed`

**步骤 5：用户检查点（可选）**

必要时可用本地 SQLite 查看器打开生成文件，确认行内容符合预期。

### 任务 7：加入本地嵌入器与向量存储接口

**文件：**
- 新建：`app/services/embedder.py`
- 新建：`app/services/vector_store.py`
- 新建：`app/services/vector_index.py`
- 新建：`tests/unit/services/test_vector_index.py`
- 新建：`scripts/build_index.py`

**执行前依赖提示：**
- 本任务前半段的 `FakeEmbedder` 红绿测试不要求真实向量依赖
- 在接入真实本地嵌入模型或首次运行 `scripts/build_index.py` 之前，必须先将向量检索依赖安装到 `fire` 环境，至少包括 `numpy`、`faiss-cpu`
- 若采用 `sentence-transformers` 作为默认本地嵌入方案，还必须在 `fire` 环境安装 `sentence-transformers`

**步骤 1：编写失败测试**

```python
from app.services.vector_index import build_vector_index


class FakeEmbedder:
    def encode(self, texts):
        return [[1.0, 0.0], [0.0, 1.0]]


def test_build_vector_index_persists_mapping(tmp_path):
    chunks = [
        {"chunk_id": "a1", "text": "消防安全责任制"},
        {"chunk_id": "a2", "text": "损坏消防设施"},
    ]
    build_vector_index(chunks, tmp_path, embedder=FakeEmbedder())
    assert (tmp_path / "vector_map.json").exists()
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_vector_index.py -q`  
预期：因缺少向量索引构建器而失败。

**步骤 3：编写最小实现**

```python
import json
from pathlib import Path


def build_vector_index(chunks: list[dict], output_dir: Path, embedder) -> None:
    vectors = embedder.encode([c["text"] for c in chunks])
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "vector_map.json").write_text(
        json.dumps([{"chunk_id": c["chunk_id"]} for c in chunks], ensure_ascii=False),
        encoding="utf-8",
    )
```

随后扩展为：
- 定义窄接口 `VectorStore`
- 增加基于 FAISS 的默认实现
- 持久化 `faiss.index` 与向量到 chunk 的映射
- `scripts/build_index.py` 中一次构建关键词与向量索引

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_vector_index.py -q`  
预期：`1 passed`

**步骤 5：用户检查点（可选）**

先确认 FakeEmbedder 场景稳定通过，再接入真实本地嵌入模型。

### 任务 8：实现查询规范化与混合检索

**文件：**
- 新建：`app/services/query_normalizer.py`
- 新建：`app/services/retriever.py`
- 新建：`tests/unit/services/test_query_normalizer.py`
- 新建：`tests/unit/services/test_retriever.py`

**步骤 1：编写失败测试**

```python
from app.services.query_normalizer import normalize_query
from app.services.retriever import fuse_results


def test_normalize_query_expands_fire_law_alias():
    normalized = normalize_query("消防法关于职责的规定")
    assert normalized.canonical_terms[0] == "中华人民共和国消防法"


def test_fuse_results_deduplicates_by_chunk_id():
    keyword_hits = [{"chunk_id": "a1", "score": 0.9}]
    vector_hits = [{"chunk_id": "a1", "score": 0.8}, {"chunk_id": "a2", "score": 0.7}]
    fused = fuse_results(keyword_hits, vector_hits, top_k=3)
    assert [item["chunk_id"] for item in fused] == ["a1", "a2"]
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_retriever.py -q`  
预期：因缺少规范化或融合函数而失败。

**步骤 3：编写最小实现**

```python
def normalize_query(query: str):
    if "消防法" in query:
        return {"original": query, "canonical_terms": ["中华人民共和国消防法"]}
    return {"original": query, "canonical_terms": []}


def fuse_results(keyword_hits, vector_hits, top_k: int):
    seen = {}
    for hit in keyword_hits + vector_hits:
        seen.setdefault(hit["chunk_id"], hit)
    return list(seen.values())[:top_k]
```

随后补充：
- 地域 / 时间 / 处罚 / 职责等线索提取
- 先做元数据过滤的检索编排
- 确定性的排序和分数归一
- 返回结果中保留 `document_id`、条文路径和命中来源

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_query_normalizer.py tests/unit/services/test_retriever.py -q`  
预期：`2 passed`

**步骤 5：用户检查点（可选）**

人工看几条规范化后的查询，确认别名映射足够稳定，再接生成层。

### 任务 9：实现答案组装与 OpenAI 兼容聊天客户端

**执行前依赖提示：**
- 本任务依赖 `openai` 兼容 Python 客户端；若当前 `fire` 环境缺少该依赖，应先安装再继续执行
- 若后续接入额外模型协议适配器，也应在本任务开始前一并完成安装

**文件：**
- 新建：`app/schemas/__init__.py`
- 新建：`app/schemas/chat.py`
- 新建：`app/services/chat_client.py`
- 新建：`app/services/answer_service.py`
- 新建：`tests/unit/services/test_answer_service.py`

**步骤 1：编写失败测试**

```python
from app.services.answer_service import build_answer


class FakeChatClient:
    def complete(self, messages):
        return {
            "conclusion": "可以查询到相关依据。",
            "citations": ["《中华人民共和国消防法》第二条"],
            "scope": "适用于一般消防安全责任制说明。",
            "uncertainty": "未检索到地方性补充规定。",
        }


def test_build_answer_returns_refusal_when_evidence_is_empty():
    result = build_answer([], client=FakeChatClient())
    assert result["conclusion"] == "证据不足，无法可靠回答。"
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py -q`  
预期：因缺少答案构建器而失败。

**步骤 3：编写最小实现**

```python
def build_answer(evidence, client):
    if not evidence:
        return {
            "conclusion": "证据不足，无法可靠回答。",
            "citations": [],
            "scope": "",
            "uncertainty": "当前检索结果不足以支持结论。",
        }
    return client.complete(evidence)
```

随后补充：
- 基于 OpenAI 兼容 SDK 的 `ChatClient` 包装层
- 强制固定回答结构的 prompt 组装
- 引文校验，若引文无依据则拒答
- `app/schemas/chat.py` 中的强类型请求 / 响应模型

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_answer_service.py -q`  
预期：`1 passed`

**步骤 5：用户检查点（可选）**

仔细读拒答响应，确认语气是真拒答，而不是伪装成正常回答。

### 任务 10：通过 FastAPI 暴露聊天 API

**文件：**
- 新建：`app/api/chat.py`
- 修改：`app/main.py`
- 新建：`tests/integration/api/test_chat_api.py`

**步骤 1：编写失败测试**

```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_chat_endpoint_returns_structured_answer(monkeypatch):
    client = TestClient(create_app())
    response = client.post("/api/chat", json={"message": "消防法关于职责怎么规定？"})
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"conclusion", "citations", "scope", "uncertainty", "evidence"}
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q`  
预期：因 `404` 或缺少路由而失败。

**步骤 3：编写最小实现**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api")


@router.post("/chat")
def chat(payload: dict) -> dict:
    return {
        "conclusion": "证据不足，无法可靠回答。",
        "citations": [],
        "scope": "",
        "uncertainty": "未完成检索接线。",
        "evidence": [],
    }
```

随后将路由接入 `create_app()`，并用真实的“查询规范化 -> 检索 -> 答案生成”链路替换 stub，同时确保接口能区分“建库错误”和“证据不足”。

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/integration/api/test_chat_api.py -q`  
预期：`1 passed`

**步骤 5：用户检查点（可选）**

用 `curl` 或 FastAPI docs 页面手工打一次接口，确认 JSON 结构已经稳定。

### 任务 11：增加极薄网页聊天界面与端到端文档

**执行前依赖提示：**
- 本任务默认复用现有 `fastapi`、`jinja2`、`httpx` 与 `pytest`，通常不需要新增依赖
- 若后续将浏览器端验证升级为真实浏览器自动化，再按实际方案安装额外依赖（例如 `playwright`）

**文件：**
- 新建：`app/templates/index.html`
- 新建：`app/static/app.css`
- 新建：`app/static/app.js`
- 修改：`app/main.py`
- 新建：`tests/integration/pipeline/test_build_pipeline.py`
- 修改：`README.md`

**步骤 1：编写失败测试**

```python
from fastapi.testclient import TestClient
from app.main import create_app


def test_root_page_renders_chat_shell():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "消防法律 RAG" in response.text


def test_build_pipeline_creates_expected_outputs(tmp_path):
    assert (tmp_path / "normalized").exists() is False
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/integration/pipeline/test_build_pipeline.py tests/integration/api/test_chat_api.py -q`  
预期：因缺少 `/` 路由或缺少流水线入口而失败。

**步骤 3：编写最小实现**

```html
<!-- app/templates/index.html -->
<h1>消防法律 RAG</h1>
<form id="chat-form"></form>
<section id="answer"></section>
```

```javascript
// app/static/app.js
document.getElementById("chat-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
});
```

随后补充：
- `/` 的 Jinja2 模板渲染
- 静态资源服务
- 浏览器侧对 `/api/chat` 的请求逻辑
- 一个在小型 fixtures 上跑通离线流水线的集成测试，确认 `data/normalized/`、`data/structured/`、`data/chunks/`、`data/index/` 会被创建
- README 中的安装、建库、运行、测试和已知限制说明

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/integration/pipeline/test_build_pipeline.py tests/integration/api/test_chat_api.py -q`  
预期：以上测试全部通过。

**步骤 5：用户检查点（可选）**

本地启动应用，跑一遍完整建库，再人工问 5 到 10 个问题，确认是否达到可交付状态。

## 最终验证清单

全部任务完成后，先运行：

```bash
conda run -n fire python -m pytest -q
```

预期：
- 单元测试通过
- 集成测试通过
- 没有任何测试依赖真实外部模型服务

然后运行离线流水线和应用：

```bash
conda run -n fire python scripts/build_corpus.py
conda run -n fire python scripts/build_index.py
conda run -n fire python -m uvicorn app.main:create_app --factory --reload
```

其中，运行 `scripts/build_index.py` 前，需先确认 `Task 7` 所需的向量检索依赖已经安装到 `fire` 环境。

预期：
- `data/normalized/`、`data/structured/`、`data/chunks/`、`data/index/`、`data/manifests/` 存在
- `/health` 返回 `{"status":"ok"}`
- `/` 能渲染极薄聊天界面
- `/api/chat` 返回固定结构响应
- 对证据不足的问题能干净拒答，而不是幻觉补全

历史计划入口已迁移至 `docs/reference_material/2026-03-28-fire-law-rag-implementation.md`。执行方式仍保持：

**1. Subagent-Driven（当前会话）**  
由我逐任务推进，每完成一批就停下来汇报并等待反馈。

**2. Parallel Session（新会话）**  
开一个新会话，按此计划逐项推进。

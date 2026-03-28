# 消防法律 RAG 实施计划

> **给 Claude：** 必须使用 `superpowers:executing-plans` 子技能逐任务执行本计划。

**目标：** 基于 `法律文本/` 构建一套仅在本机运行的纯 RAG 系统，包含离线语料处理、混合检索、OpenAI 兼容聊天后端，以及由 FastAPI 提供的最小网页聊天界面。

**架构：** 系统拆分为离线建库链路和在线查询链路。离线步骤负责标准化法律文本、解析结构、按条切块，并在 `data/` 下构建关键词与向量索引；在线步骤负责规范化查询、读取已建索引、检索证据并生成带引文约束的回答。

**技术栈：** Python 3.14、FastAPI、Pydantic Settings、pytest、SQLite FTS5、通过向量存储接口封装的 FAISS、本地句向量模型适配器、OpenAI 兼容 Python 客户端、Jinja2 模板、原生 HTML/CSS/JS。

**文档定位：** 本文档只记录任务、步骤和验收方式；执行进展统一记录在 [项目状态](../status.md)。

## 计划说明

- 每次开始任务前，先查看本任务涉及库或工具的最新官方文档。
- 严格遵守 TDD：先写失败测试，确认失败，再写最小实现，确认通过。
- 本仓库禁止代理擅自执行 git commit。若用户需要 checkpoint，由用户自行决定如何提交。
- 所有代码执行命令默认使用 `conda run -n fire ...`。若命令未带环境前缀，视为文档缺陷，需要修正。
- 每次完成代码执行后，必须同步更新 [项目状态](../status.md)。

### 任务 1：初始化项目骨架与本地配置

**文件：**
- 新建：`pyproject.toml`
- 新建：`.gitignore`
- 新建：`.env.example`
- 新建：`README.md`
- 新建：`app/__init__.py`
- 新建：`app/main.py`
- 新建：`app/core/__init__.py`
- 新建：`app/core/settings.py`
- 新建：`app/api/__init__.py`
- 新建：`app/api/health.py`
- 新建：`tests/unit/core/test_settings.py`
- 新建：`tests/integration/api/test_health_api.py`

**步骤 1：编写失败测试**

```python
# tests/unit/core/test_settings.py
from app.core.settings import Settings


def test_settings_build_default_paths():
    settings = Settings.model_validate({})
    assert settings.data_dir.name == "data"
    assert settings.raw_corpus_dir.name == "法律文本"


# tests/integration/api/test_health_api.py
from fastapi.testclient import TestClient
from app.main import create_app


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py -q`  
预期：在实现前失败，报 `ModuleNotFoundError` 或缺少 `create_app` / `Settings`。

**步骤 3：编写最小实现**

```python
# app/core/settings.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    raw_corpus_dir: Path = Path("法律文本")


# app/api/health.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# app/main.py
from fastapi import FastAPI
from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    return app
```

同时补充：
- `pyproject.toml` 中的运行时依赖：`fastapi`、`uvicorn`、`pydantic-settings`、`jinja2`、`openai`
- `pyproject.toml` 中的开发依赖：`pytest`、`httpx`
- 与已批准设计一致的 `.gitignore`
- 带聊天模型与嵌入模型占位项的 `.env.example`
- 初始版 `README.md`

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/core/test_settings.py tests/integration/api/test_health_api.py -q`  
预期：`2 passed`

**步骤 5：用户检查点（可选）**

检查项目骨架是否清晰，再由用户自己决定是否创建 git checkpoint。

### 任务 2：增加语料发现与输入清单

**文件：**
- 新建：`app/services/__init__.py`
- 新建：`app/services/corpus_ingestor.py`
- 新建：`tests/unit/services/test_corpus_ingestor.py`
- 新建：`tests/fixtures/raw/消防法--2019年4月23日.doc`
- 新建：`tests/fixtures/raw/河北省消防条例.docx`

**步骤 1：编写失败测试**

```python
from pathlib import Path
from app.services.corpus_ingestor import discover_documents


def test_discover_documents_builds_stable_manifest(tmp_path: Path):
    (tmp_path / "消防法--2019年4月23日.doc").write_text("stub", encoding="utf-8")
    (tmp_path / "河北省消防条例.docx").write_text("stub", encoding="utf-8")

    manifest = discover_documents(tmp_path)

    assert [item.document_id for item in manifest] == [
        "hebei_xiaofang_tiaoli",
        "xiaofangfa_2019",
    ]
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_corpus_ingestor.py -q`  
预期：因缺少 `discover_documents` 或清单顺序不正确而失败。

**步骤 3：编写最小实现**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CorpusDocument:
    document_id: str
    source_path: Path


def discover_documents(raw_dir: Path) -> list[CorpusDocument]:
    documents = []
    for path in sorted(raw_dir.glob("*")):
        if path.suffix.lower() not in {".doc", ".docx"}:
            continue
        document_id = (
            path.stem.lower()
            .replace("消防法--2019年4月23日", "xiaofangfa_2019")
            .replace("河北省消防条例", "hebei_xiaofang_tiaoli")
        )
        documents.append(CorpusDocument(document_id=document_id, source_path=path))
    return documents
```

随后把硬编码逻辑收敛为可复用的 slug 生成函数，并补上原始文件名、文件类型等清单字段。

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_corpus_ingestor.py -q`  
预期：`1 passed`

**步骤 5：用户检查点（可选）**

确认 `document_id` 是否稳定、可读，再继续往下做。

### 任务 3：实现文档标准化

**文件：**
- 新建：`app/services/normalizer.py`
- 新建：`tests/unit/services/test_normalizer.py`
- 新建：`tests/fixtures/normalized/expected_fire_law.txt`
- 修改：`README.md`

**步骤 1：编写失败测试**

```python
from app.services.normalizer import clean_text


def test_clean_text_removes_page_noise():
    raw = "第一章 总则\\n\\nHYPERLINK foo\\n第 1 页\\n消防工作贯彻预防为主。\\n\\n"
    cleaned = clean_text(raw)
    assert "HYPERLINK" not in cleaned
    assert "第 1 页" not in cleaned
    assert "消防工作贯彻预防为主。" in cleaned
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_normalizer.py -q`  
预期：因缺少 `clean_text` 而失败。

**步骤 3：编写最小实现**

```python
import re


def clean_text(raw: str) -> str:
    text = re.sub(r"HYPERLINK\\s+\\S+", "", raw)
    text = re.sub(r"第\\s*\\d+\\s*页", "", text)
    text = re.sub(r"\\n{2,}", "\\n", text)
    return text.strip()
```

随后补充：
- `.doc` 与 `.docx` 的加载辅助函数
- macOS `textutil` 路径下的 `.doc` 转换流程
- 将 `U+2028` / `U+2029` 等 Unicode 行终止符归一化为普通换行
- 向 `data/normalized/<document_id>.txt` 输出标准化文本
- 若转换后为空，写入失败报告

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_normalizer.py -q`  
预期：`1 passed`

**步骤 5：用户检查点（可选）**

人工打开一份标准化文本，确认页面噪声确实被清理掉。

### 任务 4：实现法律结构解析

**文件：**
- 新建：`app/services/structure_parser.py`
- 新建：`tests/unit/services/test_structure_parser.py`
- 新建：`tests/fixtures/structured/fire_law_fragment.txt`

**步骤 1：编写失败测试**

```python
from pathlib import Path
from app.services.structure_parser import parse_legal_document


def test_parse_legal_document_extracts_article_and_chapter():
    raw = Path("tests/fixtures/structured/fire_law_fragment.txt").read_text(encoding="utf-8")
    document = parse_legal_document("xiaofangfa_2019", raw)
    assert document.document_id == "xiaofangfa_2019"
    assert document.title == "中华人民共和国消防法"
    assert document.articles[0].article_no == "第二条"
    assert document.articles[0].chapter_title == "第一章 总则"
```

同时至少补一个“修订决定前言 -> 真正法规标题 -> 条文正文”的用例，避免把前言误识别成标题或第一条正文。
再补一个“带空格中文日期（如 `2001 年 11 月 14 日`）”的元数据提取用例，避免 `promulgated_on` / `effective_on` 因日期格式轻微变化而漏提。

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py -q`  
预期：因缺少解析器或条文提取错误而失败。

**步骤 3：编写最小实现**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedArticle:
    article_no: str
    chapter_title: str | None
    heading_path: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    document_id: str
    title: str
    issuing_authority: str | None
    region: str | None
    promulgated_on: str | None
    effective_on: str | None
    articles: list[ParsedArticle]
```

随后把占位逻辑替换成带类型模型的正式结构，至少覆盖：
- `document_id`
- 规范化标题
- 发布机关
- 地域
- 生效时间相关字段
- 含章节路径和原文的条文记录
- 前言元数据提取与正文条文切分分离，前言不得并入第一条
- 中文日期提取需兼容紧凑写法与带空格写法

并落盘到 `data/structured/<document_id>.json`。

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_structure_parser.py -q`  
预期：新增的结构解析用例全部通过，而不是只通过单个最小样例。

**步骤 5：用户检查点（可选）**

人工查看一个解析后的 JSON，确认章节、条号、条文没有被压成一整块字符串。

### 任务 5：实现按条优先的切块

**文件：**
- 新建：`app/services/chunk_builder.py`
- 新建：`tests/unit/services/test_chunk_builder.py`

**步骤 1：编写失败测试**

```python
from app.services.chunk_builder import build_chunks


def test_build_chunks_preserves_article_path():
    structured = {
        "document_id": "xiaofangfa_2019",
        "title": "中华人民共和国消防法",
        "articles": [
            {
                "article_no": "第二条",
                "chapter_title": "第一章 总则",
                "text": "国家实行消防安全责任制。"
            }
        ],
    }
    chunks = build_chunks(structured)
    assert chunks[0]["path"] == "中华人民共和国消防法 > 第一章 总则 > 第二条"
```

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_chunk_builder.py -q`  
预期：因缺少切块器而失败。

**步骤 3：编写最小实现**

```python
def build_chunks(structured: dict) -> list[dict]:
    article = structured["articles"][0]
    return [
        {
            "chunk_id": f'{structured["document_id"]}#article-2',
            "path": f'{structured["title"]} > {article["chapter_title"]} > {article["article_no"]}',
            "text": article["text"],
        }
    ]
```

随后扩展为：
- 超长条文按段落拆分，但保留同一父路径
- 保留 `document_id`、条号、章节名与过滤元数据
- 向 `data/chunks/<document_id>.jsonl` 落盘

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_chunk_builder.py -q`  
预期：`1 passed`

**步骤 5：用户检查点（可选）**

抽样检查切块结果，确认没有退化成任意句子碎片。

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

预期：
- `data/normalized/`、`data/structured/`、`data/chunks/`、`data/index/`、`data/manifests/` 存在
- `/health` 返回 `{"status":"ok"}`
- `/` 能渲染极薄聊天界面
- `/api/chat` 返回固定结构响应
- 对证据不足的问题能干净拒答，而不是幻觉补全

计划已保存至 `docs/plans/2026-03-28-fire-law-rag-implementation.md`。执行方式仍保持：

**1. Subagent-Driven（当前会话）**  
由我逐任务推进，每完成一批就停下来汇报并等待反馈。

**2. Parallel Session（新会话）**  
开一个新会话，按此计划逐项推进。

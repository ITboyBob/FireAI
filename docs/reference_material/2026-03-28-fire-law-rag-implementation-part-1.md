# 消防法律 RAG 实施计划

> 本文为历史实施计划分卷一；分卷导航见[实施计划总览](./2026-03-28-fire-law-rag-implementation.md)。

> **给 Claude：** 必须使用 `superpowers:executing-plans` 子技能逐任务执行本计划。

**目标：** 基于 `法律文本/` 构建一套仅在本机运行的纯 RAG 系统，包含离线语料处理、混合检索、OpenAI 兼容聊天后端，以及由 FastAPI 提供的最小网页聊天界面。

**架构：** 系统拆分为离线建库链路和在线查询链路。离线步骤负责标准化法律文本、解析结构、按条切块，并在 `data/` 下构建关键词与向量索引；在线步骤负责规范化查询、读取已建索引、检索证据并生成带引文约束的回答。

**技术栈：** Python 3.14、FastAPI、Pydantic Settings、pytest、SQLite FTS5、通过向量存储接口封装的 FAISS、本地句向量模型适配器、OpenAI 兼容 Python 客户端、Jinja2 模板、原生 HTML/CSS/JS。

## 计划说明

- 每次开始任务前，先查看本任务涉及库或工具的最新官方文档。
- 严格遵守 TDD：先写失败测试，确认失败，再写最小实现，确认通过。
- 本仓库禁止代理擅自执行 git commit。若用户需要 checkpoint，由用户自行决定如何提交。
- 所有代码执行命令默认使用 `conda run -n fire ...`。若命令未带环境前缀，视为文档缺陷，需要修正。
- 若实施计划或实际执行表明当前任务依赖尚未安装，代理必须先显式向用户报备待安装的依赖清单；仅在用户确认后，才可将缺少的依赖安装到 `fire` 环境。
- 若某个任务未单独写“执行前依赖提示”，默认表示“无需新增依赖，沿用当前 `fire` 环境”。

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
                "heading_path": ["第一章 总则"],
                "text": "国家实行消防安全责任制。",
            }
        ],
    }
    chunks = build_chunks(structured)
    assert chunks[0]["path"] == "中华人民共和国消防法 > 第一章 总则 > 第二条"
```

同时至少补一个“超长条文按段落拆分但路径不漂移”的用例，以及一个“无章节标题时 path 不出现多余分隔符”的用例。

**步骤 2：运行测试，确认失败**

运行：`conda run -n fire python -m pytest tests/unit/services/test_chunk_builder.py -q`  
预期：因缺少切块器而失败。

**步骤 3：编写最小实现**

```python
def build_chunks(structured: dict) -> list[dict]:
    article = structured["articles"][0]
    return [
        {
            "chunk_id": f'{structured["document_id"]}#article-1',
            "document_id": structured["document_id"],
            "article_no": article["article_no"],
            "chapter_title": article.get("chapter_title"),
            "heading_path": article.get("heading_path", []),
            "path": f'{structured["title"]} > {article["chapter_title"]} > {article["article_no"]}',
            "text": article["text"],
        }
    ]
```

随后扩展为：
- 超长条文按段落拆分，但保留同一父路径
- `chunk_id` 需稳定且可追溯到原条文顺序；分段后追加 `part-n`
- 保留 `document_id`、条号、章节名、`heading_path` 与过滤元数据
- 提供 `write_chunks(chunks, document_id, output_dir)`，向 `data/chunks/<document_id>.jsonl` 落盘

**步骤 4：运行测试，确认通过**

运行：`conda run -n fire python -m pytest tests/unit/services/test_chunk_builder.py -q`  
预期：新增的切块用例全部通过，而不是只通过单个最小样例。

**步骤 5：用户检查点（可选）**

抽样检查真实 `data/chunks/*.jsonl`，确认没有退化成任意句子碎片，且多段条文仍能回到同一条文路径。

> **历史门禁：** `Task 6` 当时要求先完成 [Normalization And Chunking Refactor Design](./2026-03-28-normalization-and-chunking-refactor-design.md) 与 [Normalization And Chunking Refactor Implementation Plan](./2026-03-28-normalization-and-chunking-refactor.md) 中定义的重构与全量重建。原 ADR 当前不在工作树中，不作为读取入口。

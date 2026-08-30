import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# docs/system_meta/ 治理文件（文档索引.md、文档读取规则.md）已随仓库文档体系演进移除，
# 本测试的索引/读取规则断言已相应撤销（2026-08-30）。

W_S1_DOCS = [
    "docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation.md",
    "docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation-part-1.md",
    "docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation-part-2.md",
    "docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation-part-3.md",
    "docs/project_or_workflow/2026-06-29-w-s1-end-to-end-ingestion-implementation-part-4.md",
]

SYNCED_DOCS = [
    "README.md",
    "docs/architecture_or_strategy/工程技术标准.md",
    *W_S1_DOCS,
]


@pytest.mark.parametrize("relative_path", SYNCED_DOCS)
def test_synced_doc_line_count_within_limit(relative_path: str) -> None:
    """所有同步文档均不超过 420 行警戒线。"""
    path = PROJECT_ROOT / relative_path
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 420, f"{relative_path} 超过 420 行: {len(lines)}"


@pytest.mark.parametrize("relative_path", SYNCED_DOCS)
def test_synced_doc_relative_links_exist(relative_path: str) -> None:
    """同步文档中的相对 Markdown 链接均可解析到真实文件。"""
    doc_path = PROJECT_ROOT / relative_path
    text = doc_path.read_text(encoding="utf-8")
    base_dir = doc_path.parent

    for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
        link = match.group(1).strip()
        if link.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_name = link.split("#", 1)[0]
        target = (base_dir / target_name).resolve()
        assert target.exists(), (
            f"{relative_path} 中的链接 '{match.group(0)}' 指向不存在文件: {target}"
        )


def test_engineering_standard_requires_confirmed_and_qualified() -> None:
    """工程技术标准要求正式摄取必须经过统一编排器、confirmed 边界和 qualified 资格。"""
    text = (
        PROJECT_ROOT / "docs/architecture_or_strategy/工程技术标准.md"
    ).read_text(encoding="utf-8")
    assert "统一编排器" in text
    assert "confirmed" in text
    assert "qualified" in text
    assert "正式摄取" in text


def test_readme_lists_unified_cli_only() -> None:
    """README 只列出统一 CLI，并说明单文件、显式批次和行为收紧。"""
    text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "scripts/import_new_corpus.py" in text
    assert "--batch-manifest" in text
    assert "conda run -n fire" in text
    assert "互斥" in text

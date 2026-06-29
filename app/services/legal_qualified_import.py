"""质量资格封装的 Append-Only 提交入口。

``CommitQualification`` 把质量门结论、摘要指纹和规则版本绑定到一次提交尝试；
``commit_qualified_staged_import`` 在真正落盘前再次校验这些指纹，
只有 ``auto_passed`` 或 ``review_passed`` 状态才会委托给 ``commit_staged_import``。
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

from app.services.incremental_import import (
    CommitPlan,
    CommittedImport,
    commit_staged_import,
)


class CommitQualificationError(RuntimeError):
    """质量资格校验失败，提交被拒绝。"""


@dataclass(frozen=True, slots=True, kw_only=True)
class CommitQualification:
    """一次尝试的提交资格证明。

    字段全部来自质量门最终报告，用于在提交前与磁盘上的真实产物做最终核对。
    """

    attempt_id: str
    qualified_state: Literal["auto_passed", "review_passed"]
    ruleset_version: str
    source_sha256: str
    quality_report_sha256: str
    normalized_sha256: str
    structured_sha256: str
    chunks_sha256: str


@dataclass(frozen=True, slots=True, kw_only=True)
class QualifiedCommitPlan:
    """在普通 ``CommitPlan`` 之上追加质量报告与资格证明。"""

    commit_plan: CommitPlan
    quality_report_path: Path
    quality_report_sha256: str
    qualification: CommitQualification


_QUALIFIED_STATES = frozenset({"auto_passed", "review_passed"})


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _require_digest(
    label: str,
    expected: str,
    actual: str,
) -> None:
    if expected != actual:
        raise CommitQualificationError(
            f"{label} 摘要校验失败: expected={expected}, actual={actual}"
        )


def commit_qualified_staged_import(
    plan: QualifiedCommitPlan,
    *,
    embedder: object,
) -> CommittedImport:
    """校验质量资格后执行 Append-Only 提交。

    校验项：
    1. qualified_state 必须是 auto_passed 或 review_passed。
    2. 源文件摘要与 qualification.source_sha256 一致。
    3. 质量报告文件摘要与 qualification.quality_report_sha256 一致。
    4. staging 中的 normalized/structured/chunks 摘要与 qualification 一致。
    全部通过后，委托 ``commit_staged_import`` 完成真正的落盘。
    """
    qualification = plan.qualification
    commit_plan = plan.commit_plan

    if qualification.qualified_state not in _QUALIFIED_STATES:
        raise CommitQualificationError(
            f"qualified_state 不合法: {qualification.qualified_state!r}, "
            f"必须是 auto_passed 或 review_passed"
        )

    source_path = Path(commit_plan.source_path)
    _require_digest(
        "source_sha256",
        qualification.source_sha256,
        _sha256_file(source_path),
    )

    _require_digest(
        "quality_report_sha256",
        qualification.quality_report_sha256,
        _sha256_file(plan.quality_report_path),
    )

    document_id = commit_plan.document_id
    staging = commit_plan.staging
    _require_digest(
        "normalized_sha256",
        qualification.normalized_sha256,
        _sha256_file(staging.normalized_dir / f"{document_id}.txt"),
    )
    _require_digest(
        "structured_sha256",
        qualification.structured_sha256,
        _sha256_file(staging.structured_dir / f"{document_id}.json"),
    )
    _require_digest(
        "chunks_sha256",
        qualification.chunks_sha256,
        _sha256_file(staging.chunks_dir / f"{document_id}.jsonl"),
    )

    return commit_staged_import(commit_plan, embedder=embedder)

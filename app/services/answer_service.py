from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import ValidationError

from app.schemas.chat import ChatResponse, EvidenceItem, ModelAnswer
from app.services.chat_client import ChatCompletionError


REFUSAL_CONCLUSION = "证据不足，无法可靠回答。"
EMPTY_EVIDENCE_UNCERTAINTY = "当前检索结果不足以支持结论。"
INVALID_CITATION_UNCERTAINTY = "模型返回的引文无法在当前证据中验证。"
MODEL_FAILURE_UNCERTAINTY = "模型调用失败，当前无法基于证据生成稳定结论。"
MODEL_FAILURE_PREFIX = "模型调用失败："


class ChatClient(Protocol):
    def complete(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]: ...


def build_answer(
    evidence: Sequence[dict[str, Any] | EvidenceItem],
    *,
    client: ChatClient,
    question: str = "",
) -> dict[str, Any]:
    evidence_items = [EvidenceItem.model_validate(item) for item in evidence]
    if not evidence_items:
        return _build_refusal([], EMPTY_EVIDENCE_UNCERTAINTY)

    allowed_citations = _build_allowed_citations(evidence_items)
    messages = _build_messages(question, evidence_items, allowed_citations)

    try:
        answer = ModelAnswer.model_validate(client.complete(messages))
    except ChatCompletionError as exc:
        return _build_refusal(evidence_items, _format_model_failure_uncertainty(str(exc)))
    except ValidationError:
        return _build_refusal(evidence_items, MODEL_FAILURE_UNCERTAINTY)
    except Exception:
        return _build_refusal(evidence_items, MODEL_FAILURE_UNCERTAINTY)

    if not answer.citations or any(citation not in allowed_citations for citation in answer.citations):
        return _build_refusal(evidence_items, INVALID_CITATION_UNCERTAINTY)

    response = ChatResponse(
        conclusion=answer.conclusion.strip(),
        citations=answer.citations,
        scope=answer.scope.strip(),
        uncertainty=answer.uncertainty.strip(),
        evidence=evidence_items,
    )
    return response.model_dump(mode="json")


def build_citation_label(evidence: EvidenceItem) -> str:
    if evidence.title and evidence.article_no:
        return f"《{evidence.title}》{evidence.article_no}"
    if evidence.title:
        return f"《{evidence.title}》"
    return evidence.path


def _build_allowed_citations(evidence: Sequence[EvidenceItem]) -> list[str]:
    seen: set[str] = set()
    citations: list[str] = []
    for item in evidence:
        citation = build_citation_label(item)
        if citation in seen:
            continue
        seen.add(citation)
        citations.append(citation)
    return citations


def _build_messages(
    question: str,
    evidence: Sequence[EvidenceItem],
    allowed_citations: Sequence[str],
) -> list[dict[str, str]]:
    system_prompt = (
        "你是消防法律 RAG 的答案生成器。"
        "以下输出要求是机器协议，必须逐条遵守："
        "只输出一个 JSON object，首字符必须是 {，末字符必须是 }。"
        "不要 Markdown，不要代码块，不要解释，不要前后缀文本。"
        "JSON object 只能包含 conclusion、citations、scope、uncertainty 四个字段，不得输出额外字段。"
        "字段类型必须严格正确：conclusion、scope、uncertainty 必须是 string；citations 必须是 string array。"
        "空值必须按类型输出：string 字段用空字符串 \"\"；citations 用空数组 []；不得使用 null、数字、布尔值或对象代替。"
        "citations 只能从给定候选引文中逐字选择，不得自造。"
        "若证据不足，必须明确拒答。"
        "格式示例（仅示意，不要照抄内容）："
        "{\"conclusion\":\"...\",\"citations\":[\"候选引文\"],\"scope\":\"\",\"uncertainty\":\"\"}"
    )
    evidence_lines = [
        (
            f"- 引文：{build_citation_label(item)}\n"
            f"  路径：{item.path}\n"
            f"  内容：{item.text}"
        )
        for item in evidence
    ]
    user_prompt = "\n".join(
        [
            f"问题：{question or '请基于证据总结可支持的结论。'}",
            "候选引文（只能从这里选）：",
            *[f"- {citation}" for citation in allowed_citations],
            "证据：",
            *evidence_lines,
        ]
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _build_refusal(
    evidence: Sequence[EvidenceItem],
    uncertainty: str,
) -> dict[str, Any]:
    response = ChatResponse(
        conclusion=REFUSAL_CONCLUSION,
        citations=[],
        scope="",
        uncertainty=uncertainty,
        evidence=list(evidence),
    )
    return response.model_dump(mode="json")


def is_model_failure_uncertainty(uncertainty: str | None) -> bool:
    if not uncertainty:
        return False
    return uncertainty == MODEL_FAILURE_UNCERTAINTY or uncertainty.startswith(MODEL_FAILURE_PREFIX)


def _format_model_failure_uncertainty(detail: str) -> str:
    text = detail.strip()
    if not text:
        return MODEL_FAILURE_UNCERTAINTY
    if text.startswith(MODEL_FAILURE_PREFIX):
        return text
    return f"{MODEL_FAILURE_PREFIX}{text}"

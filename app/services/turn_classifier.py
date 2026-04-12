from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClassifiedTurn:
    is_followup: bool
    context_hints: dict[str, str]


class TurnClassifier:
    FOLLOW_UP_MARKERS = ("它", "这个", "上一条", "上一轮", "继续", "那第二条")
    SCOPE_EXTENSION_MARKERS = ("也适用", "那河北", "河北也", "本地也", "当地也")

    def classify(self, message: str, *, previous_turns: list[dict[str, Any]]) -> ClassifiedTurn:
        if previous_turns and any(marker in message for marker in self.FOLLOW_UP_MARKERS):
            previous = previous_turns[-1]
            return ClassifiedTurn(
                is_followup=True,
                context_hints=self._inherit_context(previous),
            )
        if previous_turns and any(marker in message for marker in self.SCOPE_EXTENSION_MARKERS):
            return ClassifiedTurn(
                is_followup=True,
                context_hints=self._inherit_context(previous_turns[-1], include_article=False),
            )
        return ClassifiedTurn(is_followup=False, context_hints={})

    def _inherit_context(self, previous: dict[str, Any], *, include_article: bool = True) -> dict[str, str]:
        context_hints: dict[str, str] = {}
        canonical_title = str(previous.get("canonical_title", "") or "").strip()
        if canonical_title:
            context_hints["canonical_title"] = canonical_title

        article_no = str(previous.get("article_no", "") or "").strip()
        if include_article and article_no:
            context_hints["article_no"] = article_no
        return context_hints

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClassifiedTurn:
    is_followup: bool
    context_hints: dict[str, str]


class TurnClassifier:
    FOLLOW_UP_MARKERS = ("它", "这个", "上一条", "上一轮", "继续", "那第二条")

    def classify(self, message: str, *, previous_turns: list[dict[str, Any]]) -> ClassifiedTurn:
        if previous_turns and any(marker in message for marker in self.FOLLOW_UP_MARKERS):
            previous = previous_turns[-1]
            return ClassifiedTurn(
                is_followup=True,
                context_hints={
                    "canonical_title": previous.get("canonical_title", "") or "",
                    "article_no": previous.get("article_no", "") or "",
                },
            )
        return ClassifiedTurn(is_followup=False, context_hints={})

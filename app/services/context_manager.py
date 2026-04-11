from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConversationContext:
    recent_turns: list[dict[str, Any]]
    history_summary: str


class ContextManager:
    def __init__(self, *, window_turns: int):
        self.window_turns = window_turns

    def build(self, turns: list[dict[str, Any]], *, history_summary: str) -> ConversationContext:
        if self.window_turns <= 0:
            raise ValueError("window_turns must be positive")

        return ConversationContext(
            recent_turns=turns[-self.window_turns :],
            history_summary=history_summary if history_summary.strip() else "",
        )

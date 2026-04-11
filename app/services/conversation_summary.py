class ConversationSummaryManager:
    def build_summary(self, older_turns: list[dict]) -> str:
        lines: list[str] = []
        for turn in older_turns:
            basis = "、".join(turn.get("legal_basis", [])) or "无明确依据"
            prefix = "已修正前文：" if turn.get("correction_notice") else ""
            lines.append(f"{prefix}{turn['question']} -> {basis}")
        return "\n".join(lines)

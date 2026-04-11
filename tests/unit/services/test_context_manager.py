from app.services.context_manager import ContextManager


def test_context_manager_keeps_recent_turns_and_summary():
    manager = ContextManager(window_turns=2)
    turns = [
        {"question": "第一轮", "answer": "A"},
        {"question": "第二轮", "answer": "B"},
        {"question": "第三轮", "answer": "C"},
    ]

    context = manager.build(turns, history_summary="更早历史摘要")

    assert [turn["question"] for turn in context.recent_turns] == ["第二轮", "第三轮"]
    assert context.history_summary == "更早历史摘要"


def test_context_manager_degrades_to_recent_turns_when_summary_missing():
    manager = ContextManager(window_turns=2)
    turns = [
        {"question": "第一轮", "answer": "A"},
        {"question": "第二轮", "answer": "B"},
        {"question": "第三轮", "answer": "C"},
    ]

    context = manager.build(turns, history_summary="")

    assert [turn["question"] for turn in context.recent_turns] == ["第二轮", "第三轮"]
    assert context.history_summary == ""

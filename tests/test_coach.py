import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel  # noqa: E402
from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

import agent  # noqa: E402
import compare  # noqa: E402
from ledger import Ledger  # noqa: E402

L = Ledger.from_csv(str(ROOT / "sample_data" / "transactions.csv"))


class FakeToolModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_months_and_totals():
    assert L.months() == ["2026-08", "2026-09", "2026-10"]
    oct_ = next(m for m in L.monthly_summary() if m["month"] == "2026-10")
    assert oct_["income"] == 3700.0
    assert oct_["net"] == round(oct_["income"] - oct_["spent"], 2)


def test_planted_delivery_spike_is_the_biggest_change():
    top = L.compare_months("2026-09", "2026-10")[0]
    assert top["category"] == "Food Delivery" and top["change"] > 0
    assert L.find_transactions("quickeats", "2026-10")["count"] == 12


def test_compare_months_reports_counts():
    row = next(r for r in L.compare_months("2026-09", "2026-10") if r["category"] == "Food Delivery")
    assert row["2026-09_count"] == 4
    assert row["2026-10_count"] == 12


def test_system_prompt_requires_tool_sourced_numbers():
    assert "must come from a tool result" in agent.SYSTEM


def test_recurring_catches_price_increase_and_duplicate():
    rec = {r["merchant"]: r for r in L.recurring_charges()}
    assert rec["STREAMFLIX SUBSCRIPTION"]["price_change"] == 2.5
    assert rec["CLOUDSTORE 100GB"]["duplicate_months"] == ["2026-10"]
    assert "FRESH FOODS MARKET" not in rec  # a store with varying amounts isn't a subscription


def test_tools_return_json():
    tools = {t.name: t for t in agent.make_tools(L)}
    out = json.loads(tools["find_transactions"].invoke({"text": "CLOUDSTORE", "month": "2026-10"}))
    assert out["count"] == 2


def test_agent_loop_runs_tool_then_answers():
    fake = FakeToolModel(responses=[
        AIMessage(content="", tool_calls=[{"name": "find_transactions", "args": {"text": "QUICKEATS", "month": "2026-10"},
                                           "id": "call_1"}]),
        AIMessage(content="You placed 12 delivery orders in October.\nANSWER: 12"),
    ])
    r = agent.ask(L, "How many delivery orders in October?", fake)
    assert r["tool_calls"] == [{"tool": "find_transactions", "args": {"text": "QUICKEATS", "month": "2026-10"}}]
    assert compare.parse_number(r["answer"]) == 12


def test_answer_parser():
    assert compare.parse_number("blah\nANSWER: $1,399.24") == 1399.24
    assert compare.parse_number("no number") is None


def test_question_truths_are_computed():
    assert len(compare.QUESTIONS) == 10
    assert all(isinstance(t, (int, float)) for _, t in compare.QUESTIONS)

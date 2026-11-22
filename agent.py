"""Spending Coach: an LLM that answers money questions by calling exact tools over your transactions.

Graph (LangGraph):  agent --(asks for tools)--> tools --> agent ... --(no more tools)--> END
"""
from __future__ import annotations

import json
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from ledger import Ledger

load_dotenv()

SYSTEM = """You are a personal spending coach.
You can't see the transactions directly. Use the tools to get exact numbers; never estimate or do arithmetic in your head.
Months are written YYYY-MM. Start with list_months if you don't know which months exist.
When asked "where did my money go" or for a review: compare the latest month with the one before, find the biggest change,
look at the transactions behind it, and check recurring charges for price increases or duplicates.
Every number you state must come from a tool result in this conversation. If you don't have it, call a tool or don't state it.
Never use words like "roughly", "about" or "around" for counts or amounts the tools can give exactly.
When comparing two months, get data for both months before answering.
Answer like a coach: the headline first with the number, then the cause, then one specific action. Keep it under 120 words."""


def get_llm(provider: str):
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), temperature=0, max_tokens=1500)
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"), temperature=0)
    raise ValueError(f"Unknown provider: {provider}")


def make_tools(ledger: Ledger):
    @tool
    def list_months() -> str:
        """List the months (YYYY-MM) in the data, with income, total spent and net for each."""
        return json.dumps(ledger.monthly_summary())

    @tool
    def spend_by_category(month: str) -> str:
        """Total spent per category in a month (YYYY-MM), largest first."""
        return json.dumps(ledger.spend_by_category(month))

    @tool
    def compare_months(month_a: str, month_b: str) -> str:
        """Spending per category in two months (YYYY-MM): total $ and transaction count for each month,
        plus the change in $ and %, biggest change first."""
        return json.dumps(ledger.compare_months(month_a, month_b))

    @tool
    def find_transactions(text: str = "", month: str = "", category: str = "") -> str:
        """Find transactions whose description contains `text`, optionally filtered by month (YYYY-MM) and category.
        Returns the count, the total spent, and the matching transactions."""
        return json.dumps(ledger.find_transactions(text, month or None, category or None))

    @tool
    def top_merchants(month: str, n: int = 5) -> str:
        """The merchants you spent the most at in a month (YYYY-MM), with totals and number of charges."""
        return json.dumps(ledger.top_merchants(month, n))

    @tool
    def recurring_charges() -> str:
        """Subscriptions and other recurring charges, with price changes, duplicate charges in the same month,
        and the yearly cost at the latest price."""
        return json.dumps(ledger.recurring_charges())

    return [list_months, spend_by_category, compare_months, find_transactions, top_merchants, recurring_charges]


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def build_graph(ledger: Ledger, llm):
    tools = make_tools(ledger)
    model = llm.bind_tools(tools)

    def agent(state: State):
        return {"messages": [model.invoke([SystemMessage(SYSTEM)] + state["messages"])]}

    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(tools))
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


def ask(ledger: Ledger, question: str, llm, max_steps: int = 12) -> dict:
    """Returns the answer, the tool calls made (for the demo and the post), and token usage."""
    result = build_graph(ledger, llm).invoke({"messages": [HumanMessage(question)]},
                                             {"recursion_limit": max_steps * 2 + 1})
    msgs = result["messages"]
    calls = [{"tool": c["name"], "args": c["args"]} for m in msgs for c in (getattr(m, "tool_calls", None) or [])]
    tokens = sum((getattr(m, "usage_metadata", None) or {}).get("total_tokens", 0) for m in msgs)
    content = msgs[-1].content
    answer = content if isinstance(content, str) else "".join(
        b.get("text", "") for b in content if isinstance(b, dict))
    return {"answer": answer, "tool_calls": calls, "tokens": tokens}


def ask_stuffed(ledger: Ledger, question: str, llm) -> dict:
    """The baseline: paste the whole CSV into the prompt and hope the model does the math right."""
    msg = llm.invoke([SystemMessage("You are a personal spending coach. Here are all my transactions as CSV "
                                    "(negative = money out):\n\n" + ledger.to_csv()),
                      HumanMessage(question)])
    usage = (getattr(msg, "usage_metadata", None) or {}).get("total_tokens", 0)
    content = msg.content
    answer = content if isinstance(content, str) else "".join(
        b.get("text", "") for b in content if isinstance(b, dict))
    return {"answer": answer, "tool_calls": [], "tokens": usage}

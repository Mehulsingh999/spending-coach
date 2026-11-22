"""Tools vs. pasting the CSV: 10 questions with exact answers, scored.

Usage:
  python compare.py                          # Claude, both approaches
  python compare.py --provider ollama        # local model
Prints a table you can put in your post.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import time

import agent
from ledger import Ledger

L = Ledger.from_csv(str(pathlib.Path(__file__).parent / "sample_data" / "transactions.csv"))
OCT, SEP = "2026-10", "2026-09"

# Each question ends by asking for one number, so it can be scored exactly. Truth comes from ledger.py.
QUESTIONS = [
    ("How much did I spend in total in October 2026?", next(m["spent"] for m in L.monthly_summary() if m["month"] == OCT)),
    ("How much did I spend on Food Delivery in October 2026?", L.spend_by_category(OCT)["Food Delivery"]),
    ("How many food delivery orders did I place in October 2026?", L.find_transactions("QUICKEATS", OCT)["count"]),
    ("By how many dollars did my Food Delivery spending change from September to October 2026?",
     next(r["change"] for r in L.compare_months(SEP, OCT) if r["category"] == "Food Delivery")),
    ("How much did I spend on Groceries in September 2026?", L.spend_by_category(SEP)["Groceries"]),
    ("What was my net (income minus spending) in October 2026?", next(m["net"] for m in L.monthly_summary() if m["month"] == OCT)),
    ("How much did I spend at CORNER MARKET across all three months?", L.find_transactions("CORNER MARKET")["total_spent"]),
    ("How much did I spend on Restaurants in August 2026?", L.spend_by_category("2026-08")["Restaurants"]),
    ("By how many dollars did my STREAMFLIX subscription price go up?",
     next(r["price_change"] for r in L.recurring_charges() if r["merchant"].startswith("STREAMFLIX"))),
    ("How many times was CLOUDSTORE charged in October 2026?", L.find_transactions("CLOUDSTORE", OCT)["count"]),
]
SUFFIX = "\n\nEnd your reply with a final line in the form: ANSWER: <number>"


def parse_number(text: str) -> float | None:
    m = re.findall(r"ANSWER:\s*\$?\s*(-?[\d,]+(?:\.\d+)?)", text)
    if not m:
        return None
    return float(m[-1].replace(",", ""))


def score(fn, llm) -> dict:
    right, tokens, secs, rows = 0, 0, 0.0, []
    for q, truth in QUESTIONS:
        t0 = time.time()
        try:
            r = fn(L, q + SUFFIX, llm)
            got = parse_number(r["answer"])
            tokens += r["tokens"]
        except Exception as e:
            got = None
            r = {"answer": f"ERROR {type(e).__name__}: {e}"}
        secs += time.time() - t0
        ok = got is not None and abs(abs(got) - abs(truth)) < 0.011
        right += ok
        rows.append((q[:60], truth, got, "ok" if ok else "WRONG"))
    return {"accuracy": right / len(QUESTIONS), "tokens": tokens / len(QUESTIONS),
            "seconds": secs / len(QUESTIONS), "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="anthropic")
    args = ap.parse_args()
    llm = agent.get_llm(args.provider)
    results = {"Paste the CSV": score(agent.ask_stuffed, llm), "Tool calling": score(agent.ask, llm)}
    for name, res in results.items():
        print(f"\n== {name} ({args.provider}) ==")
        for q, truth, got, mark in res["rows"]:
            print(f"  {mark:5} {q:60} truth={truth}  got={got}")
    print(f"\n| Approach ({args.provider}) | Correct answers | Avg tokens per question | Avg seconds |")
    print("| --- | --- | --- | --- |")
    for name, res in results.items():
        print(f"| {name} | {res['accuracy']:.0%} | {res['tokens']:,.0f} | {res['seconds']:.1f} |")


if __name__ == "__main__":
    main()

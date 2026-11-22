"""Exact queries over a bank CSV. No AI here: these are the tools the agent calls.

CSV columns: date (YYYY-MM-DD), description, category, amount (negative = money out).
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Txn:
    date: str
    description: str
    category: str
    amount: float

    @property
    def month(self) -> str:
        return self.date[:7]

    @property
    def spend(self) -> float:
        return -self.amount if self.amount < 0 else 0.0


class Ledger:
    def __init__(self, txns: list[Txn]):
        self.txns = sorted(txns, key=lambda t: t.date)

    @classmethod
    def from_csv(cls, path_or_text: str, is_text: bool = False) -> "Ledger":
        f = io.StringIO(path_or_text) if is_text else open(path_or_text, newline="", encoding="utf-8")
        with f:
            rows = csv.DictReader(f)
            txns = [Txn(r["date"].strip(), r["description"].strip(), (r.get("category") or "Uncategorized").strip(),
                        float(r["amount"])) for r in rows]
        return cls(txns)

    def to_csv(self) -> str:
        lines = ["date,description,category,amount"]
        lines += [f"{t.date},{t.description},{t.category},{t.amount:.2f}" for t in self.txns]
        return "\n".join(lines)

    # ---- queries -------------------------------------------------------------
    def months(self) -> list[str]:
        return sorted({t.month for t in self.txns})

    def categories(self) -> list[str]:
        return sorted({t.category for t in self.txns})

    def monthly_summary(self) -> list[dict]:
        out = []
        for m in self.months():
            ts = [t for t in self.txns if t.month == m]
            income = round(sum(t.amount for t in ts if t.amount > 0), 2)
            spent = round(sum(t.spend for t in ts), 2)
            out.append({"month": m, "income": income, "spent": spent, "net": round(income - spent, 2)})
        return out

    def spend_by_category(self, month: str) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for t in self.txns:
            if t.month == month and t.amount < 0:
                totals[t.category] += t.spend
        return {k: round(v, 2) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])}

    def _spend_and_count_by_category(self, month: str) -> dict[str, tuple[float, int]]:
        totals: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        for t in self.txns:
            if t.month == month and t.amount < 0:
                totals[t.category] += t.spend
                counts[t.category] += 1
        return {k: (round(totals[k], 2), counts[k]) for k in totals}

    def compare_months(self, month_a: str, month_b: str) -> list[dict]:
        a, b = self._spend_and_count_by_category(month_a), self._spend_and_count_by_category(month_b)
        rows = []
        for cat in sorted(set(a) | set(b)):
            va, ca = a.get(cat, (0.0, 0))
            vb, cb = b.get(cat, (0.0, 0))
            pct = None if va == 0 else round((vb - va) / va * 100, 1)
            rows.append({"category": cat, month_a: va, f"{month_a}_count": ca,
                         month_b: vb, f"{month_b}_count": cb,
                         "change": round(vb - va, 2), "change_pct": pct})
        return sorted(rows, key=lambda r: -abs(r["change"]))

    def find_transactions(self, text: str = "", month: str | None = None, category: str | None = None) -> dict:
        ts = [t for t in self.txns
              if text.lower() in t.description.lower()
              and (month is None or t.month == month)
              and (category is None or t.category.lower() == category.lower())]
        return {"count": len(ts), "total_spent": round(sum(t.spend for t in ts), 2),
                "transactions": [t.__dict__ for t in ts[:50]]}

    def top_merchants(self, month: str, n: int = 5) -> list[dict]:
        totals: dict[str, list[float]] = defaultdict(list)
        for t in self.txns:
            if t.month == month and t.amount < 0:
                totals[t.description].append(t.spend)
        rows = [{"merchant": k, "total": round(sum(v), 2), "count": len(v)} for k, v in totals.items()]
        return sorted(rows, key=lambda r: -r["total"])[:n]

    def recurring_charges(self) -> list[dict]:
        """Merchants charged in at least 2 months, with price changes and same-month duplicates flagged."""
        by_merchant: dict[str, list[Txn]] = defaultdict(list)
        for t in self.txns:
            if t.amount < 0:
                by_merchant[t.description].append(t)
        out = []
        for name, ts in by_merchant.items():
            months = sorted({t.month for t in ts})
            if len(months) < 2:
                continue
            amounts = [round(t.spend, 2) for t in ts]
            distinct = list(dict.fromkeys(amounts))  # in order of first appearance
            # A subscription charges the same amount; allow one price step (old -> new) if seen 3+ times
            is_step = (len(distinct) == 2 and len(amounts) >= 3
                       and amounts == sorted(amounts, key=lambda a: distinct.index(a)))
            if not (len(distinct) == 1 or is_step):
                continue  # amounts vary: a regular store, not a subscription
            per_month = defaultdict(int)
            for t in ts:
                per_month[t.month] += 1
            first, last = ts[0].spend, ts[-1].spend
            out.append({
                "merchant": name, "months": len(months), "latest_amount": last,
                "price_change": round(last - first, 2) if abs(last - first) > 0.005 else 0.0,
                "duplicate_months": [m for m, c in per_month.items() if c > 1],
                "yearly_cost": round(last * 12, 2),
            })
        return sorted(out, key=lambda r: -r["yearly_cost"])

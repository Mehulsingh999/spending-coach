"""Generates sample_data/transactions.csv: 3 months of made-up transactions for one person.

Seeded, so it is the same every time. Patterns planted on purpose (so the agent has something to find):
- food delivery jumps in October (3 -> 4 -> 12 orders)
- a streaming subscription raises its price in October
- a cloud storage subscription is charged twice in October
"""
import csv
import pathlib
import random
from datetime import date, timedelta

random.seed(42)
rows = []


def add(d, desc, cat, amt):
    rows.append({"date": d.isoformat(), "description": desc, "category": cat, "amount": f"{amt:.2f}"})


months = [(2026, 8), (2026, 9), (2026, 10)]
delivery_orders = {8: 3, 9: 4, 10: 12}
for y, m in months:
    first = date(y, m, 1)
    days = (date(y + (m == 12), m % 12 + 1, 1) - first).days
    day = lambda n: first + timedelta(days=n - 1)  # noqa: E731

    add(day(1), "PAYROLL DEPOSIT ACME CORP", "Income", 1850.00)
    add(day(15), "PAYROLL DEPOSIT ACME CORP", "Income", 1850.00)
    add(day(1), "MAPLE RIDGE APARTMENTS RENT", "Rent", -1150.00)
    add(day(18), "NORTH TX ELECTRIC", "Utilities", -round(random.uniform(78, 135), 2))
    add(day(22), "FASTNET INTERNET", "Utilities", -60.00)
    # subscriptions
    add(day(5), "STREAMFLIX SUBSCRIPTION", "Subscriptions", -(17.99 if m == 10 else 15.49))
    add(day(9), "MUSICBOX PREMIUM", "Subscriptions", -10.99)
    add(day(3), "GYMPRO MEMBERSHIP", "Subscriptions", -29.99)
    add(day(12), "CLOUDSTORE 100GB", "Subscriptions", -2.99)
    if m == 10:
        add(day(12), "CLOUDSTORE 100GB", "Subscriptions", -2.99)
    # groceries weekly
    for wk in range(0, days - 3, 7):
        store = random.choice(["CORNER MARKET", "FRESH FOODS MARKET"])
        add(day(wk + 2), store, "Groceries", -round(random.uniform(52, 92), 2))
    # gas
    for n in (6, 20):
        add(day(n), "METRO FUEL", "Transportation", -round(random.uniform(34, 48), 2))
    # restaurants
    for _ in range(3):
        place = random.choice(["LAKESIDE CAFE", "BISTRO 12", "TACO CORNER"])
        add(day(random.randint(2, days)), place, "Restaurants", -round(random.uniform(12, 46), 2))
    # food delivery
    for _ in range(delivery_orders[m]):
        add(day(random.randint(1, days)), "QUICKEATS DELIVERY", "Food Delivery", -round(random.uniform(18, 34), 2))
    # shopping
    for _ in range(2):
        add(day(random.randint(1, days)), random.choice(["CITY OUTFITTERS", "HOMEGOODS PLUS", "BOOKNOOK"]),
            "Shopping", -round(random.uniform(15, 85), 2))

rows.sort(key=lambda r: (r["date"], r["description"]))
out = pathlib.Path(__file__).resolve().parents[1] / "sample_data" / "transactions.csv"
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["date", "description", "category", "amount"])
    w.writeheader()
    w.writerows(rows)
print(f"wrote {len(rows)} rows to {out}")

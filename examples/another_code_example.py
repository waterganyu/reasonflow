"""Simple Python script that generates some data for analysis."""

import random

random.seed(42)

sales = {
    "Q1": random.randint(10000, 50000),
    "Q2": random.randint(10000, 50000),
    "Q3": random.randint(10000, 50000),
    "Q4": random.randint(10000, 50000),
}

total = sum(sales.values())
best = max(sales, key=sales.get)
worst = min(sales, key=sales.get)

print(f"Quarterly Sales Report")
print(f"======================")
for q, amount in sales.items():
    print(f"  {q}: ${amount:,}")
print(f"  Total: ${total:,}")
print(f"  Best quarter: {best} (${sales[best]:,})")
print(f"  Worst quarter: {worst} (${sales[worst]:,})")

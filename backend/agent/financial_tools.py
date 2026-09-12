from __future__ import annotations

from datetime import date, timedelta
from collections import defaultdict


def get_financial_history(recent_expenses: list[dict]) -> list[dict]:
    return recent_expenses


def get_recurring_expenses(financial_state: dict) -> list[dict]:
    return financial_state.get("recurring_expenses", [])


def get_pending_payments(financial_state: dict) -> list[dict]:
    return financial_state.get("pending_payments", [])


def get_confirmed_income(financial_state: dict) -> list[dict]:
    return [i for i in financial_state.get("confirmed_income", []) if i.get("confirmed", True)]


def get_recent_expenses(financial_state: dict, days: int = 30) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    out = []
    for exp in financial_state.get("recent_expenses", []):
        d = exp.get("date")
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                continue
        if isinstance(d, date) and d >= cutoff:
            out.append(exp)
    return out


def calculate_cash_flow(financial_state: dict, horizon_days: int = 30) -> float:
    start = financial_state.get("current_balance", 0)
    confirmed_income = sum(i.get("amount", 0) for i in get_confirmed_income(financial_state))
    payments = sum(p.get("amount", 0) for p in get_pending_payments(financial_state))
    recurring = sum(r.get("amount", 0) for r in get_recurring_expenses(financial_state))
    return start + confirmed_income - payments - recurring


def evaluate_payment_plan(amount: float, months: int = 3) -> list[dict]:
    if months <= 0:
        months = 1
    chunk = round(amount / months, 2)
    remaining = amount
    plan = []
    for i in range(months):
        pay = chunk if i < months - 1 else round(remaining, 2)
        plan.append({"date": (date.today() + timedelta(days=30 * (i + 1))).isoformat(), "amount": pay})
        remaining -= pay
    return plan


def check_minimum_balance(balance_after: float, minimum: float) -> bool:
    return balance_after >= minimum


def calculate_discretionary_budget(financial_state: dict) -> float:
    recent = get_recent_expenses(financial_state)
    essential = sum(e.get("amount", 0) for e in recent if e.get("necessity") in {"essential", "need"})
    monthly = financial_state.get("discretionary_budget", 5000)
    return max(0.0, monthly - max(0.0, essential * 0.0) - sum(e.get("amount", 0) for e in recent if e.get("necessity") != "essential"))


def suggest_spending_changes(financial_state: dict, needed: float) -> list[str]:
    by_category = defaultdict(float)
    for exp in get_recent_expenses(financial_state):
        if exp.get("necessity", "optional") != "essential":
            by_category[exp.get("category", "OTHER")] += exp.get("amount", 0)
    ranked = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    tips = []
    remaining = needed
    for cat, amt in ranked[:3]:
        cut = min(amt * 0.3, remaining)
        if cut > 0:
            tips.append(f"Reduce {cat.lower()} spending by about ₹{round(cut, 2)} this month")
            remaining -= cut
        if remaining <= 0:
            break
    if not tips:
        tips.append("Pause optional purchases until key bills are paid")
    return tips

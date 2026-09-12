from __future__ import annotations

from datetime import date, timedelta


def _as_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError("Unsupported date value")


def forecast_balance(financial_state: dict, purchase_plan: list[dict] | None = None, horizon_days: int = 90) -> list[dict]:
    purchase_plan = purchase_plan or []
    today = date.today()
    events = []

    events.extend((
        {"date": _as_date(i["date"]), "delta": float(i.get("amount", 0)), "label": f"income:{i.get('source', 'income')}"}
        for i in financial_state.get("confirmed_income", []) if i.get("confirmed", True)
    ))

    events.extend((
        {"date": _as_date(e["due_date"]), "delta": -float(e.get("amount", 0)), "label": f"pending:{e.get('name', 'payment')}"}
        for e in financial_state.get("pending_payments", [])
    ))

    events.extend((
        {"date": _as_date(e["due_date"]), "delta": -float(e.get("amount", 0)), "label": f"recurring:{e.get('name', 'expense')}"}
        for e in financial_state.get("recurring_expenses", [])
    ))

    events.extend((
        {"date": _as_date(p["date"]), "delta": -float(p.get("amount", 0)), "label": "purchase"}
        for p in purchase_plan
    ))

    end = today + timedelta(days=horizon_days)
    events = [e for e in events if today <= e["date"] <= end]
    events.sort(key=lambda e: e["date"])

    balance = float(financial_state.get("current_balance", 0))
    series = [{"date": today.isoformat(), "balance": round(balance, 2), "label": "start"}]
    for event in events:
        balance += event["delta"]
        series.append({"date": event["date"].isoformat(), "balance": round(balance, 2), "label": event["label"]})
    return series


def earliest_safe_full_payment_date(financial_state: dict, amount: float, minimum_balance: float, max_days: int = 180) -> str:
    today = date.today()
    for offset in range(0, max_days + 1):
        d = today + timedelta(days=offset)
        series = forecast_balance(financial_state, [{"date": d.isoformat(), "amount": amount}], horizon_days=max_days)
        min_projected = min(point["balance"] for point in series)
        if min_projected >= minimum_balance:
            return d.isoformat()
    return (today + timedelta(days=max_days)).isoformat()

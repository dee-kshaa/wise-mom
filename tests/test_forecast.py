from backend.agent.forecast import forecast_balance, earliest_safe_full_payment_date


def test_forecast_balance_applies_events():
    state = {
        "current_balance": 35000,
        "confirmed_income": [{"source": "salary", "amount": 30000, "date": "2099-01-10", "confirmed": True}],
        "pending_payments": [{"name": "rent", "amount": 15000, "due_date": "2099-01-05", "essential": True}],
        "recurring_expenses": [],
    }
    series = forecast_balance(state, [{"date": "2099-01-03", "amount": 5000}], horizon_days=40000)
    assert len(series) >= 2


def test_earliest_safe_date_returns_iso():
    state = {
        "current_balance": 10000,
        "confirmed_income": [{"source": "salary", "amount": 20000, "date": "2099-01-01", "confirmed": True}],
        "pending_payments": [],
        "recurring_expenses": [],
    }
    date_str = earliest_safe_full_payment_date(state, amount=5000, minimum_balance=3000, max_days=30)
    assert len(date_str) == 10

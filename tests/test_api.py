from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200


def test_add_expense_and_summary():
    payload = {
        "date": "2026-01-01",
        "merchant": "Cafeteria",
        "amount": 120,
        "category": "FOOD",
        "necessity": "optional",
        "payment_method": "upi",
        "notes": "coffee"
    }
    r1 = client.post("/expense", json=payload)
    assert r1.status_code == 200
    r2 = client.get("/financial-summary")
    assert r2.status_code == 200
    assert "monthly_total" in r2.json()


def test_analyze_purchase_schema():
    payload = {
        "purchase": {"name": "Headphones", "amount": 7999, "category": "electronics", "necessity": "optional"},
        "financial_state": {
            "current_balance": 35000,
            "preferred_minimum_balance": 10000,
            "confirmed_income": [],
            "recurring_expenses": [],
            "pending_payments": [{"name": "rent", "amount": 15000, "due_date": "2099-02-01", "essential": True}],
            "recent_expenses": []
        }
    }
    r = client.post("/analyze-purchase", json=payload)
    body = r.json()
    assert r.status_code == 200
    assert "affordability_status" in body
    assert "mom_mood" in body

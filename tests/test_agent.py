from backend.agent.decision_agent import WiseMomDecisionAgent
from backend.agent.financial_tools import calculate_cash_flow


def test_affordable_purchase():
    agent = WiseMomDecisionAgent()
    payload = {
        "purchase": {"name": "Notebook", "amount": 500, "category": "EDUCATION", "necessity": "essential"},
        "financial_state": {
            "current_balance": 30000,
            "preferred_minimum_balance": 10000,
            "confirmed_income": [],
            "recurring_expenses": [],
            "pending_payments": [],
            "recent_expenses": [],
            "discretionary_budget": 5000,
            "reward_cap": 2000,
        },
    }
    decision = agent.analyze_purchase(payload)
    assert decision["affordability_status"] in {"affordable_now", "affordable_with_plan"}


def test_unaffordable_purchase():
    agent = WiseMomDecisionAgent()
    payload = {
        "purchase": {"name": "Luxury Bag", "amount": 32000, "category": "SHOPPING", "necessity": "optional"},
        "financial_state": {
            "current_balance": 35000,
            "preferred_minimum_balance": 10000,
            "confirmed_income": [],
            "recurring_expenses": [],
            "pending_payments": [{"name": "rent", "amount": 15000, "due_date": "2099-01-02", "essential": True}],
            "recent_expenses": [],
            "discretionary_budget": 5000,
            "reward_cap": 2000,
        },
    }
    decision = agent.analyze_purchase(payload)
    assert decision["recommended_payment_method"] in {"installments", "do_not_proceed", "wait"}


def test_invalid_model_output_repaired_with_fallback(monkeypatch):
    agent = WiseMomDecisionAgent()
    payload = {
        "purchase": {"name": "Mouse", "amount": 999, "category": "SHOPPING", "necessity": "optional"},
        "financial_state": {
            "current_balance": 20000,
            "preferred_minimum_balance": 10000,
            "confirmed_income": [],
            "recurring_expenses": [],
            "pending_payments": [],
            "recent_expenses": [],
            "discretionary_budget": 5000,
            "reward_cap": 2000,
        },
    }

    monkeypatch.setattr(agent, "_model_decision", lambda *_: {"affordability_status": "broken"})
    decision = agent.analyze_purchase(payload)

    assert set([
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
        "mom_mood",
    ]).issubset(decision.keys())
    assert decision["affordability_status"] in {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}


def test_unconfirmed_income_not_counted_in_cash_flow():
    state = {
        "current_balance": 10000,
        "confirmed_income": [
            {"source": "salary", "amount": 5000, "date": "2099-01-01", "confirmed": True},
            {"source": "maybe bonus", "amount": 7000, "date": "2099-01-05", "confirmed": False},
        ],
        "pending_payments": [{"name": "rent", "amount": 3000, "due_date": "2099-01-02"}],
        "recurring_expenses": [],
    }
    assert calculate_cash_flow(state) == 12000


def test_small_reward_can_be_approved_when_safe():
    agent = WiseMomDecisionAgent()
    payload = {
        "purchase": {"name": "Dessert", "amount": 500, "category": "FOOD", "necessity": "reward"},
        "financial_state": {
            "current_balance": 30000,
            "preferred_minimum_balance": 10000,
            "confirmed_income": [],
            "recurring_expenses": [],
            "pending_payments": [],
            "recent_expenses": [{"amount": 200, "necessity": "optional", "date": "2099-01-01"}],
            "discretionary_budget": 5000,
            "reward_cap": 2000,
        },
    }
    decision = agent.analyze_purchase(payload)
    assert decision["affordability_status"] == "affordable_now"
    assert decision["mom_mood"] in {"celebrating", "approving", "proud"}

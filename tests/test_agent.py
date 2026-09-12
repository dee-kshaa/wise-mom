from backend.agent.decision_agent import WiseMomDecisionAgent


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

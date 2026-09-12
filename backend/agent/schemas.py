from __future__ import annotations

from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class Purchase(BaseModel):
    name: str
    amount: float = Field(ge=0)
    category: str = "OTHER"
    necessity: str = "optional"


class IncomeItem(BaseModel):
    source: str
    amount: float = Field(ge=0)
    date: date
    confirmed: bool = True


class ExpenseItem(BaseModel):
    name: str
    amount: float = Field(ge=0)
    due_date: date
    essential: bool = True


class FinancialState(BaseModel):
    current_balance: float = Field(ge=0)
    preferred_minimum_balance: float = Field(ge=0, default=10000)
    confirmed_income: list[IncomeItem] = []
    recurring_expenses: list[ExpenseItem] = []
    pending_payments: list[ExpenseItem] = []
    recent_expenses: list[dict] = []
    savings_goal: float = 0
    discretionary_budget: float = 5000
    reward_cap: float = 2000


class AnalyzePurchaseRequest(BaseModel):
    purchase: Purchase
    financial_state: FinancialState


class PaymentPlanItem(BaseModel):
    date: str
    amount: float


class DecisionResponse(BaseModel):
    amount_safe_to_pay: float
    affordability_status: Literal["affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"]
    recommended_payment_method: Literal["full_payment", "partial_payment", "installments", "wait", "do_not_proceed"]
    payment_plan: list[PaymentPlanItem]
    earliest_date_for_full_payment: str
    spending_changes_needed: list[str]
    decision_explanation: str
    mom_mood: Literal["idle", "thinking", "happy", "proud", "worried", "suspicious", "scolding", "angry", "approving", "celebrating"]
    trace: str | None = None


class ExpenseCreate(BaseModel):
    date: date
    merchant: str
    amount: float = Field(ge=0)
    category: str = "OTHER"
    necessity: str = "optional"
    payment_method: str = "upi"
    notes: str | None = None


class FinancialContextUpdate(BaseModel):
    preferred_minimum_balance: float | None = None
    monthly_income: float | None = None
    savings_goal: float | None = None
    discretionary_budget: float | None = None
    reward_cap: float | None = None


class ExtractPurchaseRequest(BaseModel):
    text: str | None = None
    media_path: str | None = None

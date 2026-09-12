from __future__ import annotations

from datetime import date
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.database import get_db
from backend.database import repository, models
from backend.agent.schemas import (
    AnalyzePurchaseRequest,
    ExpenseCreate,
    FinancialContextUpdate,
    ExtractPurchaseRequest,
)
from backend.agent.decision_agent import WiseMomDecisionAgent
from backend.agent.extraction import extract_information_from_message, extract_information_from_image

router = APIRouter()
agent = WiseMomDecisionAgent()


@router.get("/health")
def health():
    return {"status": "ok", "service": "wise-mom-backend"}


@router.post("/analyze-purchase")
def analyze_purchase(payload: AnalyzePurchaseRequest, db: Session = Depends(get_db)):
    req = repository.add_purchase_request(db, payload.purchase.model_dump())
    decision = agent.analyze_purchase(payload.model_dump(mode="json"))
    repository.store_decision(db, req.id, decision)
    return decision


@router.get("/financial-summary")
def financial_summary(db: Session = Depends(get_db)):
    return repository.get_financial_summary(db)


@router.post("/expense")
def add_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
    expense = repository.add_expense(db, payload.model_dump())
    return {"id": expense.id, **payload.model_dump(mode="json")}


@router.get("/expenses")
def get_expenses(days: int | None = None, db: Session = Depends(get_db)):
    records = repository.get_expenses(db, days=days)
    return [
        {
            "id": r.id,
            "date": r.date.isoformat(),
            "merchant": r.merchant,
            "amount": r.amount,
            "category": r.category,
            "necessity": r.necessity,
            "payment_method": r.payment_method,
            "notes": r.notes,
        }
        for r in records
    ]


@router.get("/budget")
def get_budget(db: Session = Depends(get_db)):
    pref = repository.get_preferences(db)
    return {
        "preferred_minimum_balance": pref.preferred_minimum_balance,
        "monthly_income": pref.monthly_income,
        "savings_goal": pref.savings_goal,
        "discretionary_budget": pref.discretionary_budget,
        "reward_cap": pref.reward_cap,
    }


@router.post("/financial-context")
def update_context(payload: FinancialContextUpdate, db: Session = Depends(get_db)):
    pref = repository.get_preferences(db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(pref, field, value)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return {
        "message": "updated",
        "budget": {
            "preferred_minimum_balance": pref.preferred_minimum_balance,
            "monthly_income": pref.monthly_income,
            "savings_goal": pref.savings_goal,
            "discretionary_budget": pref.discretionary_budget,
            "reward_cap": pref.reward_cap,
        },
    }


@router.post("/extract-purchase")
def extract_purchase(payload: ExtractPurchaseRequest):
    extracted = {}
    if payload.text:
        extracted = extract_information_from_message(payload.text)
    if payload.media_path:
        media = extract_information_from_image(payload.media_path)
        if media.get("text"):
            extracted = extract_information_from_message(media["text"])
        extracted["media_signals"] = media.get("signals", [])
    if not extracted:
        raise HTTPException(status_code=400, detail="Provide text or media_path")
    if "amount" not in extracted:
        extracted["amount"] = 0.0
    return extracted

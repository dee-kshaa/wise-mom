from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models


CATEGORIES = {
    "FOOD", "TRANSPORT", "EDUCATION", "HEALTH", "RENT", "UTILITIES", "SHOPPING",
    "ENTERTAINMENT", "SUBSCRIPTIONS", "TRAVEL", "OTHER"
}


def ensure_default_user(db: Session, user_id: int = 1) -> models.User:
    user = db.get(models.User, user_id)
    if user:
        return user
    user = models.User(id=user_id, name="beta")
    db.add(user)
    db.flush()
    pref = models.FinancialPreference(user_id=user_id)
    db.add(pref)
    db.commit()
    db.refresh(user)
    return user


def add_expense(db: Session, payload: dict, user_id: int = 1) -> models.Expense:
    ensure_default_user(db, user_id)
    category = payload.get("category", "OTHER").upper()
    if category not in CATEGORIES:
        category = "OTHER"
    expense = models.Expense(
        user_id=user_id,
        date=payload["date"],
        merchant=payload.get("merchant", "Unknown"),
        amount=float(payload["amount"]),
        category=category,
        necessity=payload.get("necessity", "optional"),
        payment_method=payload.get("payment_method", "upi"),
        notes=payload.get("notes"),
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def get_expenses(db: Session, user_id: int = 1, days: int | None = None):
    q = db.query(models.Expense).filter(models.Expense.user_id == user_id)
    if days:
        q = q.filter(models.Expense.date >= date.today() - timedelta(days=days))
    return q.order_by(models.Expense.date.desc()).all()


def get_financial_summary(db: Session, user_id: int = 1) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    daily_total = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
        models.Expense.user_id == user_id,
        models.Expense.date == today,
    ).scalar()
    weekly_total = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
        models.Expense.user_id == user_id,
        models.Expense.date >= week_start,
    ).scalar()
    monthly_total = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
        models.Expense.user_id == user_id,
        models.Expense.date >= month_start,
    ).scalar()

    category_rows = db.query(
        models.Expense.category,
        func.coalesce(func.sum(models.Expense.amount), 0.0),
    ).filter(
        models.Expense.user_id == user_id,
        models.Expense.date >= month_start,
    ).group_by(models.Expense.category).all()

    category_breakdown = {cat: total for cat, total in category_rows}
    essential_total = db.query(func.coalesce(func.sum(models.Expense.amount), 0.0)).filter(
        models.Expense.user_id == user_id,
        models.Expense.date >= month_start,
        models.Expense.necessity.in_(["essential", "need"]),
    ).scalar()
    discretionary_total = monthly_total - essential_total

    pref = db.query(models.FinancialPreference).filter_by(user_id=user_id).first()
    discretionary_budget = pref.discretionary_budget if pref else 5000
    remaining_budget = discretionary_budget - discretionary_total

    return {
        "daily_total": round(float(daily_total), 2),
        "weekly_total": round(float(weekly_total), 2),
        "monthly_total": round(float(monthly_total), 2),
        "category_breakdown": category_breakdown,
        "discretionary_spending": round(float(discretionary_total), 2),
        "essential_spending": round(float(essential_total), 2),
        "remaining_budget": round(float(remaining_budget), 2),
    }


def add_purchase_request(db: Session, payload: dict, user_id: int = 1) -> models.PurchaseRequest:
    req = models.PurchaseRequest(
        user_id=user_id,
        name=payload["name"],
        amount=float(payload["amount"]),
        category=payload.get("category", "OTHER"),
        necessity=payload.get("necessity", "optional"),
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def store_decision(db: Session, request_id: int | None, decision: dict) -> models.AgentDecision:
    record = models.AgentDecision(
        purchase_request_id=request_id,
        affordability_status=decision["affordability_status"],
        recommended_payment_method=decision["recommended_payment_method"],
        decision_explanation=decision["decision_explanation"],
        mom_mood=decision["mom_mood"],
        trace=decision.get("trace"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_preferences(db: Session, user_id: int = 1) -> models.FinancialPreference:
    ensure_default_user(db, user_id)
    pref = db.query(models.FinancialPreference).filter_by(user_id=user_id).first()
    if pref:
        return pref
    pref = models.FinancialPreference(user_id=user_id)
    db.add(pref)
    db.commit()
    db.refresh(pref)
    return pref

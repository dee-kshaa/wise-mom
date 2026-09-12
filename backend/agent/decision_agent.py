from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from pydantic import ValidationError

from .schemas import DecisionResponse
from .financial_tools import (
    calculate_cash_flow,
    calculate_discretionary_budget,
    check_minimum_balance,
    evaluate_payment_plan,
    suggest_spending_changes,
)
from .forecast import earliest_safe_full_payment_date, forecast_balance


SYSTEM_PROMPT = """You are Wise Mom financial decision model. Return strict JSON only with fields exactly:
amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment,
spending_changes_needed, decision_explanation, mom_mood.
Allowed affordability_status: affordable_now, affordable_with_plan, affordable_later, not_affordable.
Allowed recommended_payment_method: full_payment, partial_payment, installments, wait, do_not_proceed.
Allowed mom_mood: idle, thinking, happy, proud, worried, suspicious, scolding, angry, approving, celebrating.
Use provided tool outputs and never fabricate arithmetic.
"""


class WiseMomDecisionAgent:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "none").lower()
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.api_key = os.getenv("OPENAI_API_KEY", "")

    def _model_decision(self, payload: dict, tool_context: dict) -> dict | None:
        if self.provider != "openai" or not self.api_key:
            return None
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            user_prompt = json.dumps({"request": payload, "tool_context": tool_context}, default=str)
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception:
            return None

    def _deterministic_decision(self, payload: dict, tool_context: dict) -> dict:
        purchase = payload["purchase"]
        fs = payload["financial_state"]
        amount = float(purchase["amount"])
        minimum = float(fs.get("preferred_minimum_balance", 10000))
        forecast = forecast_balance(fs, [{"date": date.today().isoformat(), "amount": amount}])
        min_after_full = min(item["balance"] for item in forecast)
        discretionary = tool_context["discretionary_budget"]
        recent_discretionary = tool_context["recent_discretionary"]
        reward_cap = fs.get("reward_cap", float(os.getenv("WISE_MOM_REWARD_CAP", "2000")))

        affordable_now = min_after_full >= minimum
        small_reward = purchase.get("necessity", "optional") == "reward" or amount <= reward_cap

        if affordable_now and (purchase.get("necessity") in {"essential", "need"}):
            status = "affordable_now"
            method = "full_payment"
            mood = "proud"
            explanation = "Good choice beta. Essential needs stay safe even after this purchase."
            plan = [{"date": date.today().isoformat(), "amount": amount}]
        elif affordable_now and (small_reward and recent_discretionary < discretionary):
            status = "affordable_now"
            method = "full_payment"
            mood = "celebrating"
            explanation = "Fine. One little treat allowed since your spending is controlled."
            plan = [{"date": date.today().isoformat(), "amount": amount}]
        elif affordable_now:
            status = "affordable_now"
            method = "full_payment"
            mood = "approving"
            explanation = "Okay beta, this is within your safety buffer."
            plan = [{"date": date.today().isoformat(), "amount": amount}]
        else:
            installment_plan = evaluate_payment_plan(amount, 3)
            plan_forecast = forecast_balance(fs, installment_plan)
            min_after_plan = min(item["balance"] for item in plan_forecast)
            if min_after_plan >= minimum:
                status = "affordable_with_plan"
                method = "installments"
                mood = "worried"
                explanation = "Not safe as full payment now. Installments can work with caution."
                plan = installment_plan
            else:
                status = "not_affordable"
                method = "do_not_proceed"
                mood = "scolding"
                explanation = "NO. This can push you below your minimum buffer before bills."
                plan = []

        earliest = earliest_safe_full_payment_date(fs, amount, minimum)
        needed = max(0.0, minimum - min_after_full)
        changes = suggest_spending_changes(fs, needed) if needed > 0 else []

        return {
            "amount_safe_to_pay": max(0.0, round(min(fs.get("current_balance", 0) - minimum, amount), 2)),
            "affordability_status": status,
            "recommended_payment_method": method,
            "payment_plan": plan,
            "earliest_date_for_full_payment": earliest,
            "spending_changes_needed": changes,
            "decision_explanation": explanation,
            "mom_mood": mood,
        }

    def _validate_or_repair(self, candidate: dict, fallback: dict) -> dict:
        try:
            return DecisionResponse(**candidate).model_dump()
        except ValidationError:
            repaired = {**fallback, **{k: v for k, v in candidate.items() if k in fallback}}
            try:
                return DecisionResponse(**repaired).model_dump()
            except ValidationError:
                return DecisionResponse(**fallback).model_dump()

    def analyze_purchase(self, payload: dict[str, Any]) -> dict:
        fs = payload["financial_state"]
        tool_context = {
            "cash_flow_30d": calculate_cash_flow(fs, 30),
            "discretionary_budget": calculate_discretionary_budget(fs),
            "minimum_balance_ok_without_purchase": check_minimum_balance(fs.get("current_balance", 0), fs.get("preferred_minimum_balance", 10000)),
            "recent_discretionary": sum(
                e.get("amount", 0) for e in fs.get("recent_expenses", []) if e.get("necessity", "optional") != "essential"
            ),
        }

        fallback = self._deterministic_decision(payload, tool_context)
        model_candidate = self._model_decision(payload, tool_context)
        decision = self._validate_or_repair(model_candidate or fallback, fallback)
        decision["trace"] = json.dumps({
            "provider": self.provider,
            "tool_context": tool_context,
            "fallback_used": model_candidate is None,
        })
        return decision

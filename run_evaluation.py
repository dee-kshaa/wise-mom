from __future__ import annotations

import argparse
import csv
from pathlib import Path
import pandas as pd

from backend.agent.decision_agent import WiseMomDecisionAgent
from backend.agent.extraction import extract_information_from_message, extract_information_from_image

OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
    "mom_mood",
]


def parse_state(row: dict) -> dict:
    def f(key: str, default: float = 0.0):
        try:
            return float(row.get(key, default) or default)
        except Exception:
            return default

    return {
        "current_balance": f("current_balance"),
        "preferred_minimum_balance": f("preferred_minimum_balance", 10000),
        "confirmed_income": [],
        "recurring_expenses": [],
        "pending_payments": [],
        "recent_expenses": [],
        "savings_goal": f("savings_goal", 0),
        "discretionary_budget": f("discretionary_budget", 5000),
        "reward_cap": f("reward_cap", 2000),
    }


def resolve_purchase(row: dict, base_dir: Path) -> dict:
    if row.get("message"):
        parsed = extract_information_from_message(row["message"])
    else:
        parsed = {
            "name": row.get("purchase_name", "Unknown item"),
            "amount": float(row.get("purchase_amount", 0) or 0),
            "category": row.get("category", "OTHER"),
            "necessity": row.get("necessity", "optional"),
        }

    media_path = row.get("media_path")
    if media_path:
        resolved = (base_dir / media_path).resolve()
        media = extract_information_from_image(str(resolved))
        if media.get("text"):
            parsed = extract_information_from_message(media["text"])

    parsed.setdefault("amount", float(row.get("purchase_amount", 0) or 0))
    parsed.setdefault("name", row.get("purchase_name", "Unknown item"))
    parsed.setdefault("category", row.get("category", "OTHER"))
    parsed.setdefault("necessity", row.get("necessity", "optional"))
    return parsed


def run(input_csv: Path, output_csv: Path):
    df = pd.read_csv(input_csv)
    agent = WiseMomDecisionAgent()
    rows = []

    for _, series in df.iterrows():
        row = series.to_dict()
        purchase = resolve_purchase(row, input_csv.parent)
        state = parse_state(row)
        decision = agent.analyze_purchase({"purchase": purchase, "financial_state": state})
        rows.append({
            "request_id": row.get("request_id", ""),
            "amount_safe_to_pay": decision["amount_safe_to_pay"],
            "affordability_status": decision["affordability_status"],
            "recommended_payment_method": decision["recommended_payment_method"],
            "payment_plan": str(decision["payment_plan"]),
            "earliest_date_for_full_payment": decision["earliest_date_for_full_payment"],
            "spending_changes_needed": " | ".join(decision.get("spending_changes_needed", [])),
            "decision_explanation": decision["decision_explanation"],
            "mom_mood": decision["mom_mood"],
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run WISE MOM evaluation pipeline")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.input, args.output)

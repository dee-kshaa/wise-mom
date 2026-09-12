from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dataset"

OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]

ALLOWED_STATUS = {
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
}

ALLOWED_METHODS = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
}


def clean(x):
    if pd.isna(x):
        return None
    return x


def money(x):
    x = float(x)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def parse_bool(x):
    if isinstance(x, bool):
        return x
    return str(x).strip().lower() in {"true", "1", "yes", "y"}


def split_pipe(x):
    if x is None or pd.isna(x):
        return []
    return [p.strip() for p in str(x).split("|") if p.strip()]


def load_data():
    requests = pd.read_csv(DATA / "requests.csv")
    profiles = pd.read_csv(DATA / "financial_profiles.csv")
    events = pd.read_csv(DATA / "financial_events.csv")
    rates = pd.read_csv(DATA / "exchange_rates.csv")
    options = pd.read_csv(DATA / "request_payment_options.csv")
    messages = pd.read_csv(DATA / "messages.csv")
    images = pd.read_csv(DATA / "images.csv")

    for frame, cols in [
        (requests, ["request_id", "user_id", "request_date", "requested_amount"]),
        (profiles, ["user_id", "home_currency"]),
        (events, ["event_id", "user_id", "event_type", "direction", "event_date",
                   "status"]),
        (rates, ["rate_date", "from_currency", "to_currency", "rate"]),
        (options, ["request_id", "payment_method", "payment_amount",
                    "number_of_payments", "first_payment_date",
                    "payment_frequency_days", "financing_fee",
                    "total_payable_amount"]),
        (messages, ["request_id", "user_id", "message_text"]),
        (images, ["image_id", "user_id", "request_id", "related_event_id"]),
    ]:
        for c in cols:
            if c not in frame.columns:
                frame[c] = None

    requests["request_date"] = pd.to_datetime(requests["request_date"]).dt.date
    requests["desired_completion_date"] = pd.to_datetime(
        requests["desired_completion_date"], errors="coerce"
    ).dt.date

    events["event_date"] = pd.to_datetime(events["event_date"], errors="coerce").dt.date
    events["settlement_date"] = pd.to_datetime(
        events.get("settlement_date"), errors="coerce"
    ).dt.date

    rates["rate_date"] = pd.to_datetime(rates["rate_date"]).dt.date

    options["first_payment_date"] = pd.to_datetime(
        options["first_payment_date"], errors="coerce"
    ).dt.date

    return requests, profiles, events, rates, options, messages, images


def rate_for(rates, when, src, dst):
    if src == dst:
        return 1.0

    rows = rates[
        (rates["rate_date"] == when) &
        (rates["from_currency"] == src) &
        (rates["to_currency"] == dst)
    ]

    if not rows.empty:
        return float(rows.iloc[0]["rate"])

    # Some supplied datasets contain the inverse pair.
    rows = rates[
        (rates["rate_date"] == when) &
        (rates["from_currency"] == dst) &
        (rates["to_currency"] == src)
    ]

    if not rows.empty:
        r = float(rows.iloc[0]["rate"])
        if r:
            return 1.0 / r

    return None


def event_amount_home(event, home_currency, rates):
    amount = clean(event.get("amount"))
    if amount is None:
        return None

    amount = float(amount)
    currency = clean(event.get("currency")) or home_currency
    event_date = event.get("settlement_date") or event.get("event_date")

    if currency == home_currency:
        return amount

    if event_date is None:
        return None

    r = rate_for(rates, event_date, currency, home_currency)
    if r is None:
        return None

    return amount * r


def normalized_status(x):
    if x is None or pd.isna(x):
        return ""
    return str(x).strip().lower()


def event_is_ignored(event):
    status = normalized_status(event.get("status"))
    event_type = str(event.get("event_type", "")).lower()

    if status in {"failed", "cancelled", "canceled"}:
        return True

    if "unrealized" in status or "unrealized" in event_type:
        return True

    return False


def direction_sign(event):
    direction = str(event.get("direction", "")).strip().lower()

    if direction in {"credit", "income", "inflow"}:
        return 1.0

    if direction in {"debit", "expense", "outflow"}:
        return -1.0

    return 0.0


def build_profile(profile):
    return {
        "currency": str(profile.get("home_currency") or ""),
        "balance": float(clean(profile.get("current_available_balance")) or 0),
        "minimum": float(clean(profile.get("minimum_balance_to_keep")) or 0),
        "priorities": split_pipe(profile.get("financial_priorities")),
        "protected": set(split_pipe(profile.get("expense_categories_to_protect"))),
        "reduce": set(split_pipe(profile.get("expense_categories_user_is_willing_to_reduce"))),
        "stop": set(split_pipe(profile.get("expense_categories_user_is_willing_to_stop"))),
        "methods": set(split_pipe(profile.get("payment_methods_user_will_consider"))),
        "max_installment_months": (
            None
            if clean(profile.get("max_installment_months")) is None
            else int(float(profile.get("max_installment_months")))
        ),
    }


def request_accepts(request, messages_for_request):
    text = str(request.get("request_text") or "").lower()

    message_text = " ".join(
        str(x).lower()
        for x in messages_for_request["message_text"].tolist()
        if clean(x) is not None
    )

    combined = text + " " + message_text

    partial_words = [
        "partial",
        "part payment",
        "pay part",
        "pay some",
        "down payment",
        "deposit now",
        "rest later",
        "remaining later",
    ]

    full_words = [
        "full payment",
        "pay in full",
        "all at once",
    ]

    installment_words = [
        "installment",
        "instalment",
        "emi",
        "monthly payment",
    ]

    return {
        "partial": any(w in combined for w in partial_words),
        "full": any(w in combined for w in full_words),
        "installments": any(w in combined for w in installment_words),
    }


def future_expenses(events_user, request_date, horizon_end, profile, rates):
    rows = []

    for _, e in events_user.iterrows():
        if event_is_ignored(e):
            continue

        d = e.get("event_date")
        if d is None:
            continue

        if not (request_date < d <= horizon_end):
            continue

        sign = direction_sign(e)
        if sign >= 0:
            continue

        amount = event_amount_home(e, profile["currency"], rates)
        if amount is None:
            continue

        rows.append({
            "date": d,
            "amount": abs(amount),
            "category": str(clean(e.get("category")) or ""),
            "description": str(clean(e.get("description")) or ""),
            "event_id": str(e.get("event_id") or ""),
            "status": normalized_status(e.get("status")),
            "flexibility": str(clean(e.get("flexibility")) or "").lower(),
        })

    return rows


def future_income(events_user, request_date, horizon_end, profile, rates):
    rows = []

    for _, e in events_user.iterrows():
        if event_is_ignored(e):
            continue

        d = e.get("settlement_date") or e.get("event_date")
        if d is None:
            continue

        if not (request_date < d <= horizon_end):
            continue

        sign = direction_sign(e)
        if sign <= 0:
            continue

        status = normalized_status(e.get("status"))

        # Do not count pending future credits.
        if status == "pending":
            continue

        amount = event_amount_home(e, profile["currency"], rates)
        if amount is None:
            continue

        rows.append({
            "date": d,
            "amount": amount,
            "event_id": str(e.get("event_id") or ""),
        })

    return rows


def monthly_recurring_pattern(events_user, request_date, profile, rates):
    """
    Conservative recurring detection:
    require at least 3 prior occurrences with roughly monthly/weekly cadence.
    """
    history = []

    for _, e in events_user.iterrows():
        d = e.get("event_date")
        if d is None or d >= request_date:
            continue

        if event_is_ignored(e):
            continue

        if direction_sign(e) >= 0:
            continue

        amount = event_amount_home(e, profile["currency"], rates)
        if amount is None:
            continue

        category = str(clean(e.get("category")) or "")
        description = str(clean(e.get("description")) or "")
        flexibility = str(clean(e.get("flexibility")) or "").lower()

        key = (
            category.lower(),
            re.sub(r"\\d+", "", description.lower()).strip(),
        )

        history.append(
            (key, d, abs(amount), category, description, flexibility)
        )

    groups = defaultdict(list)
    for row in history:
        groups[row[0]].append(row)

    recurring = []

    for key, vals in groups.items():
        vals = sorted(vals, key=lambda z: z[1])

        if len(vals) < 3:
            continue

        dates = [v[1] for v in vals[-6:]]
        gaps = [
            (dates[i] - dates[i - 1]).days
            for i in range(1, len(dates))
        ]

        if not gaps:
            continue

        median_gap = sorted(gaps)[len(gaps) // 2]

        if not (
            6 <= median_gap <= 10
            or 25 <= median_gap <= 35
            or 80 <= median_gap <= 100
        ):
            continue

        last = vals[-1]

        recurring.append({
            "category": last[3],
            "description": last[4],
            "amount": last[2],
            "flexibility": last[5],
            "interval": median_gap,
            "last_date": last[1],
            "event_id": None,
        })

    return recurring


def build_cashflow(events_user, request_date, profile, rates):
    horizon_end = request_date + timedelta(days=90)

    expenses = future_expenses(
        events_user, request_date, horizon_end, profile, rates
    )

    income = future_income(
        events_user, request_date, horizon_end, profile, rates
    )

    known_expense_dates = {
        (
            x["category"].lower(),
            x["date"],
            round(x["amount"], 2),
        )
        for x in expenses
    }

    # Add conservative inferred recurring expenses only when a matching
    # explicit future event is not already supplied.
    for pattern in monthly_recurring_pattern(
        events_user, request_date, profile, rates
    ):
        d = pattern["last_date"]

        while True:
            d = d + timedelta(days=pattern["interval"])
            if d > horizon_end:
                break
            if d <= request_date:
                continue

            key = (
                pattern["category"].lower(),
                d,
                round(pattern["amount"], 2),
            )

            if key in known_expense_dates:
                continue

            expenses.append({
                "date": d,
                "amount": pattern["amount"],
                "category": pattern["category"],
                "description": pattern["description"],
                "event_id": "",
                "status": "inferred_recurring",
                "flexibility": pattern["flexibility"],
            })

    return sorted(expenses, key=lambda x: x["date"]), sorted(
        income, key=lambda x: x["date"]
    )


def forecast_min_balance(
    starting_balance,
    minimum,
    request_date,
    expenses,
    income,
    payment_plan,
):
    horizon_end = request_date + timedelta(days=90)

    by_day = defaultdict(float)

    for x in expenses:
        if request_date < x["date"] <= horizon_end:
            by_day[x["date"]] -= x["amount"]

    for x in income:
        if request_date < x["date"] <= horizon_end:
            by_day[x["date"]] += x["amount"]

    for d, amount in payment_plan:
        if request_date <= d <= horizon_end:
            by_day[d] -= amount

    balance = starting_balance
    minimum_seen = balance

    for d in sorted(by_day):
        balance += by_day[d]
        minimum_seen = min(minimum_seen, balance)

    return minimum_seen


def maximum_safe_today(
    profile,
    request_date,
    expenses,
    income,
    requested_amount,
):
    # Forecast without the requested purchase.
    no_purchase_min = forecast_min_balance(
        profile["balance"],
        profile["minimum"],
        request_date,
        expenses,
        income,
        [],
    )

    safe = no_purchase_min - profile["minimum"]
    safe = max(0.0, safe)
    return min(float(requested_amount), safe)


def spending_changes_for(
    profile,
    request_date,
    expenses,
    income,
    requested_amount,
):
    if maximum_safe_today(
        profile, request_date, expenses, income, requested_amount
    ) >= requested_amount:
        return []

    candidates = []

    for e in expenses:
        if request_date < e["date"] <= request_date + timedelta(days=90):
            cat = e["category"]

            if cat in profile["protected"]:
                continue

            flex = e["flexibility"]

            if "flexible" not in flex:
                continue

            if e["event_id"] and cat in profile["stop"]:
                candidates.append(
                    (
                        e["amount"],
                        f"stop:{e['event_id']}",
                        e["event_id"],
                    )
                )

            if e["event_id"] and cat in profile["reduce"]:
                reduced = 0.0
                candidates.append(
                    (
                        e["amount"] - reduced,
                        f"reduce_to:{e['event_id']}:0",
                        e["event_id"],
                    )
                )

    candidates.sort(reverse=True, key=lambda x: x[0])

    selected = []
    seen = set()
    extra = 0.0

    for saving, action, eid in candidates:
        if eid in seen:
            continue

        selected.append((saving, action))
        seen.add(eid)
        extra += saving

        if len(selected) >= 3:
            break

        # This is only a candidate list; final feasibility is checked
        # separately by the caller.

    return selected


def apply_changes(expenses, actions):
    changed = []

    action_map = {}
    for _, action in actions:
        if action.startswith("stop:"):
            action_map[action.split(":", 1)[1]] = 0.0
        elif action.startswith("reduce_to:"):
            parts = action.split(":")
            if len(parts) >= 3:
                action_map[parts[1]] = float(parts[2])

    for e in expenses:
        if e["event_id"] in action_map:
            new_amount = action_map[e["event_id"]]
            copy = dict(e)
            copy["amount"] = max(0.0, new_amount)
            changed.append(copy)
        else:
            changed.append(dict(e))

    return changed


def option_plan(option):
    first = option.get("first_payment_date")
    if first is None or pd.isna(first):
        return []

    amount = float(option.get("payment_amount") or 0)
    n = int(float(option.get("number_of_payments") or 1))
    freq = int(float(option.get("payment_frequency_days") or 0))

    if n <= 0 or amount <= 0:
        return []

    plan = []

    for i in range(n):
        plan.append(
            (
                first + timedelta(days=i * freq),
                amount,
            )
        )

    return plan


def plan_string(plan):
    if not plan:
        return "none"

    plan = sorted(plan, key=lambda x: x[0])

    return "|".join(
        f"{d.isoformat()}:{money(a)}"
        for d, a in plan
    )


def safe_plan(
    profile,
    request_date,
    expenses,
    income,
    plan,
):
    min_balance = forecast_min_balance(
        profile["balance"],
        profile["minimum"],
        request_date,
        expenses,
        income,
        plan,
    )

    return min_balance >= profile["minimum"] - 1e-9


def earliest_full_payment(
    profile,
    request_date,
    expenses,
    income,
    requested_amount,
):
    if safe_plan(
        profile,
        request_date,
        expenses,
        income,
        [(request_date, requested_amount)],
    ):
        return request_date

    for offset in range(1, 91):
        d = request_date + timedelta(days=offset)

        if safe_plan(
            profile,
            request_date,
            expenses,
            income,
            [(d, requested_amount)],
        ):
            return d

    return None


def solve_request(
    request,
    profile,
    events_user,
    options_request,
    messages_request,
    rates,
):
    request_date = request["request_date"]
    deadline = request["desired_completion_date"]
    requested = float(request["requested_amount"])

    expenses, income = build_cashflow(
        events_user,
        request_date,
        profile,
        rates,
    )

    safe_today = maximum_safe_today(
        profile,
        request_date,
        expenses,
        income,
        requested,
    )

    full_date = earliest_full_payment(
        profile,
        request_date,
        expenses,
        income,
        requested,
    )

    acceptance = request_accepts(
        request,
        messages_request,
    )

    # ----------------------------------------------------------
    # 1. Full payment today
    # ----------------------------------------------------------
    if (
        safe_today + 1e-9 >= requested
        and "full_payment" in profile["methods"]
    ):
        plan = [(request_date, requested)]

        return {
            "amount_safe_to_pay": requested,
            "affordability_status": "affordable_now",
            "recommended_payment_method": "full_payment",
            "payment_plan": plan_string(plan),
            "earliest_date_for_full_payment": request_date.isoformat(),
            "spending_changes_needed": "none",
            "decision_explanation": (
                f"Paying {money(requested)} on {request_date.isoformat()} "
                f"keeps the projected balance above the user's "
                f"minimum balance of {money(profile['minimum'])} "
                f"through the 90-day safety forecast."
            ),
        }

    # ----------------------------------------------------------
    # 2. Exact installment options
    # ----------------------------------------------------------
    candidates = []

    for _, option in options_request.iterrows():
        method = str(option.get("payment_method") or "").lower()

        if method != "installments":
            continue

        if "installments" not in profile["methods"]:
            continue

        max_months = profile["max_installment_months"]
        n = int(float(option.get("number_of_payments") or 0))

        if max_months is not None and n > max_months:
            continue

        plan = option_plan(option)

        if not plan:
            continue

        if plan[-1][0] > deadline:
            continue

        if safe_plan(
            profile,
            request_date,
            expenses,
            income,
            plan,
        ):
            total = float(option.get("total_payable_amount") or 0)
            option_id = str(option.get("payment_option_id") or "")

            candidates.append(
                (
                    total,
                    plan[0][0],
                    len(plan),
                    option_id,
                    plan,
                )
            )

    if candidates:
        candidates.sort(
            key=lambda x: (
                x[2] > 0,
                x[0],
                x[1],
                x[2],
                x[3],
            )
        )

        chosen = candidates[0]

        return {
            "amount_safe_to_pay": safe_today,
            "affordability_status": "affordable_with_plan",
            "recommended_payment_method": "installments",
            "payment_plan": plan_string(chosen[4]),
            "earliest_date_for_full_payment": (
                full_date.isoformat() if full_date else ""
            ),
            "spending_changes_needed": "none",
            "decision_explanation": (
                "An available installment option is safe under the "
                "90-day balance forecast, remains within the user's "
                "payment preferences, and completes by the requested deadline."
            ),
        }

    # ----------------------------------------------------------
    # 3. Partial payment
    # ----------------------------------------------------------
    if (
        parse_bool(request["allows_partial_payment"])
        and acceptance["partial"]
        and "partial_payment" in profile["methods"]
        and safe_today > 0
        and safe_today < requested
        and full_date is not None
        and full_date <= deadline
    ):
        second_amount = requested - safe_today
        plan = [
            (request_date, safe_today),
            (full_date, second_amount),
        ]

        if safe_plan(
            profile,
            request_date,
            expenses,
            income,
            plan,
        ):
            return {
                "amount_safe_to_pay": safe_today,
                "affordability_status": "affordable_with_plan",
                "recommended_payment_method": "partial_payment",
                "payment_plan": plan_string(plan),
                "earliest_date_for_full_payment": full_date.isoformat(),
                "spending_changes_needed": "none",
                "decision_explanation": (
                    f"Only {money(safe_today)} is safely payable on the "
                    f"request date. The remaining {money(second_amount)} "
                    f"can be paid on {full_date.isoformat()} while preserving "
                    f"the user's minimum balance."
                ),
            }

    # ----------------------------------------------------------
    # 4. Spending changes
    # ----------------------------------------------------------
    changes = spending_changes_for(
        profile,
        request_date,
        expenses,
        income,
        requested,
    )

    if changes:
        changed_expenses = apply_changes(expenses, changes)

        if safe_plan(
            profile,
            request_date,
            changed_expenses,
            income,
            [(request_date, requested)],
        ):
            actions = [x[1] for x in changes]

            return {
                "amount_safe_to_pay": safe_today,
                "affordability_status": "affordable_with_plan",
                "recommended_payment_method": "full_payment",
                "payment_plan": plan_string(
                    [(request_date, requested)]
                ),
                "earliest_date_for_full_payment": request_date.isoformat(),
                "spending_changes_needed": "|".join(actions),
                "decision_explanation": (
                    "The request becomes safe when permitted flexible "
                    "spending is reduced or stopped. Protected categories "
                    "and the user's minimum balance are preserved."
                ),
            }

    # ----------------------------------------------------------
    # 5. Wait
    # ----------------------------------------------------------
    if (
        full_date is not None
        and full_date <= deadline
        and "full_payment" in profile["methods"]
        and (acceptance["full"] or not acceptance["partial"])
    ):
        return {
            "amount_safe_to_pay": safe_today,
            "affordability_status": "affordable_later",
            "recommended_payment_method": "wait",
            "payment_plan": "none",
            "earliest_date_for_full_payment": full_date.isoformat(),
            "spending_changes_needed": "none",
            "decision_explanation": (
                f"The full amount is not safe today, but the forecast "
                f"shows it becoming safe on {full_date.isoformat()} without "
                f"reducing protected spending."
            ),
        }

    # ----------------------------------------------------------
    # 6. Not recommended
    # ----------------------------------------------------------
    return {
        "amount_safe_to_pay": max(
            0.0,
            min(safe_today, requested),
        ),
        "affordability_status": "not_affordable",
        "recommended_payment_method": "not_recommended",
        "payment_plan": "none",
        "earliest_date_for_full_payment": (
            full_date.isoformat() if full_date else ""
        ),
        "spending_changes_needed": "none",
        "decision_explanation": (
            "No eligible payment plan completes the request safely within "
            "the required forecast period while maintaining the user's "
            "minimum balance and stated payment preferences."
        ),
    }


def mood_for(result):
    status = result["affordability_status"]
    method = result["recommended_payment_method"]

    if status == "affordable_now":
        return "approving"

    if method == "installments":
        return "thinking"

    if method == "partial_payment":
        return "worried"

    if method == "wait":
        return "suspicious"

    if method == "not_recommended":
        return "scolding"

    return "thinking"


def validate_output(df, requests):
    if list(df.columns) != OUTPUT_COLUMNS:
        raise RuntimeError(
            "Invalid output columns: "
            + str(list(df.columns))
        )

    if len(df) != len(requests):
        raise RuntimeError(
            f"Expected {len(requests)} rows, got {len(df)}"
        )

    if set(df["request_id"]) != set(requests["request_id"]):
        raise RuntimeError("Output request IDs do not match requests.csv")

    values = pd.to_numeric(
        df["amount_safe_to_pay"],
        errors="coerce",
    )

    requested_lookup = requests.set_index(
        "request_id"
    )["requested_amount"]

    for request_id, amount in zip(df["request_id"], values):
        requested = float(requested_lookup[request_id])

        if pd.isna(amount):
            raise RuntimeError(
                f"{request_id}: invalid amount_safe_to_pay"
            )

        if amount < -1e-9 or amount > requested + 1e-9:
            raise RuntimeError(
                f"{request_id}: amount_safe_to_pay outside [0, requested]"
            )

    if not df["affordability_status"].isin(ALLOWED_STATUS).all():
        raise RuntimeError("Invalid affordability_status value")

    if not df["recommended_payment_method"].isin(ALLOWED_METHODS).all():
        raise RuntimeError("Invalid recommended_payment_method value")


def main():
    (
        requests,
        profiles,
        events,
        rates,
        options,
        messages,
        images,
    ) = load_data()

    profile_map = {
        row["user_id"]: build_profile(row)
        for _, row in profiles.iterrows()
    }

    results = []
    moods = []

    for _, request in requests.iterrows():
        user_id = request["user_id"]
        request_id = request["request_id"]

        profile = profile_map[user_id]

        events_user = events[
            events["user_id"] == user_id
        ].copy()

        options_request = options[
            options["request_id"] == request_id
        ].copy()

        messages_request = messages[
            messages["request_id"] == request_id
        ].copy()

        result = solve_request(
            request,
            profile,
            events_user,
            options_request,
            messages_request,
            rates,
        )

        result["request_id"] = request_id
        results.append(result)

        moods.append({
            "request_id": request_id,
            "mom_mood": mood_for(result),
        })

    output = pd.DataFrame(results)[OUTPUT_COLUMNS]

    validate_output(output, requests)

    # Official submission output.
    output.to_csv(ROOT / "output.csv", index=False)

    # WISE MOM creative feature kept separately.
    pd.DataFrame(
        moods,
        columns=["request_id", "mom_mood"],
    ).to_csv(ROOT / "mom_mood.csv", index=False)

    print("=" * 60)
    print("WISE MOM FINAL RUN")
    print("=" * 60)
    print(f"Requests processed : {len(output)}")
    print(f"Output rows        : {len(output)}")
    print(f"Output path        : {ROOT / 'output.csv'}")
    print(f"Mood path          : {ROOT / 'mom_mood.csv'}")
    print("")
    print("Affordability:")
    print(output["affordability_status"].value_counts().to_string())
    print("")
    print("Payment method:")
    print(output["recommended_payment_method"].value_counts().to_string())
    print("=" * 60)


if __name__ == "__main__":
    main()

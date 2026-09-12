# WISE MOM

WISE MOM is an AI-powered financial guardian that runs as a **Chrome Manifest V3 browser companion** and a **Python backend agent**.

## Features

- Persistent Wise Mom overlay on webpages (content script + Shadow DOM)
- Draggable, minimizable character with mood states and speech bubble
- Purchase detection on shopping-like pages (conservative signals)
- Financial decision agent with strict structured JSON output
- SQLite-backed ledger for expenses, preferences, decisions, and history
- Popup + options + dashboard extension pages
- HackerRank-compatible CLI evaluation pipeline
- Deterministic fallback when no LLM API key is available

## Project structure

- `backend/` FastAPI app, agent, forecasting tools, SQLite models/repository
- `extension/` Manifest V3 extension (background/content/character/popup/options/dashboard)
- `run_evaluation.py` CSV in/out evaluation pipeline
- `tests/` pytest test suite

## Setup

```bash
cd /home/runner/work/wise-mom/wise-mom
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Configure environment

Edit `.env`:

```env
LLM_PROVIDER=none
OPENAI_API_KEY=
MODEL_NAME=gpt-4o-mini
DATABASE_URL=sqlite:///./data/wise_mom.db
WISE_MOM_REWARD_CAP=2000
```

- Use `LLM_PROVIDER=openai` + `OPENAI_API_KEY` for model decisions.
- With `LLM_PROVIDER=none`, deterministic fallback is used.

## Run backend

```bash
uvicorn backend.main:app --reload --port 8000
```

## Load extension (Chrome/Chromium)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select `/home/runner/work/wise-mom/wise-mom/extension`
5. Keep backend running on `http://127.0.0.1:8000`

## Demo flow

1. Open any shopping page (or a product-like page with buy signals + INR price).
2. Wise Mom appears bottom-right and comments on purchases.
3. Unsafe decision triggers intervention panel.
4. Popup shows status and quick actions.
5. Dashboard opens with summary and category data.

## API endpoints

- `POST /analyze-purchase`
- `GET /financial-summary`
- `POST /expense`
- `GET /expenses`
- `GET /budget`
- `POST /financial-context`
- `POST /extract-purchase`

## HackerRank evaluation pipeline

Run:

```bash
python run_evaluation.py --input dataset/requests.csv --output output.csv
```

Expected output columns in `output.csv`:

- `request_id`
- `amount_safe_to_pay`
- `affordability_status`
- `recommended_payment_method`
- `payment_plan`
- `earliest_date_for_full_payment`
- `spending_changes_needed`
- `decision_explanation`
- `mom_mood`

## Tests

```bash
pytest -q
```

## Security choices

- No password/card scraping logic
- Only minimal purchase context extraction from page signals
- Local SQLite persistence
- Strict output schema validation with repair + fallback path


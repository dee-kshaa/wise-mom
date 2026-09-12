const DEFAULT_STATE = {
  enabled: true,
  mood: "idle",
  warningCount: 0,
  rewardEligible: false,
  lastDecision: null,
  position: { x: null, y: null },
  minimized: false,
  hidden: false,
  todaysSpending: 0,
  monthlySpending: 0,
  remainingBudget: 5000,
  financialState: {
    current_balance: 35000,
    preferred_minimum_balance: 10000,
    confirmed_income: [],
    recurring_expenses: [],
    pending_payments: [],
    recent_expenses: [],
    discretionary_budget: 5000,
    reward_cap: 2000
  },
  backendUrl: "http://127.0.0.1:8000"
};

async function getState() {
  const stored = await chrome.storage.local.get(DEFAULT_STATE);
  return { ...DEFAULT_STATE, ...stored };
}

async function setState(patch) {
  const current = await getState();
  const next = { ...current, ...patch };
  await chrome.storage.local.set(next);
  return next;
}

function localDecision(purchase, fs) {
  const min = fs.preferred_minimum_balance || 10000;
  const after = (fs.current_balance || 0) - (purchase.amount || 0);
  const affordable = after >= min;
  const status = affordable ? "affordable_now" : "not_affordable";
  const method = affordable ? "full_payment" : "do_not_proceed";
  const mood = affordable ? (purchase.necessity === "essential" ? "proud" : "approving") : "scolding";
  return {
    amount_safe_to_pay: Math.max(0, Math.min((fs.current_balance || 0) - min, purchase.amount || 0)),
    affordability_status: status,
    recommended_payment_method: method,
    payment_plan: affordable ? [{ date: new Date().toISOString().slice(0, 10), amount: purchase.amount || 0 }] : [],
    earliest_date_for_full_payment: new Date().toISOString().slice(0, 10),
    spending_changes_needed: affordable ? [] : ["Reduce optional shopping until bills are covered"],
    decision_explanation: affordable ? "Okay beta, this one is within budget." : "NO. This purchase is unsafe before upcoming obligations.",
    mom_mood: mood
  };
}

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set(DEFAULT_STATE);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    const state = await getState();

    if (message.type === "GET_STATE") {
      sendResponse(state);
      return;
    }

    if (message.type === "SET_STATE") {
      const updated = await setState(message.patch || {});
      sendResponse({ ok: true, state: updated });
      return;
    }

    if (message.type === "OPEN_DASHBOARD") {
      chrome.tabs.create({ url: chrome.runtime.getURL("dashboard/dashboard.html") });
      sendResponse({ ok: true });
      return;
    }

    if (message.type === "ADD_EXPENSE") {
      const backend = state.backendUrl || "http://127.0.0.1:8000";
      try {
        const res = await fetch(`${backend}/expense`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(message.payload)
        });
        const data = await res.json();
        sendResponse({ ok: res.ok, data });
      } catch (e) {
        sendResponse({ ok: false, error: String(e) });
      }
      return;
    }

    if (message.type === "ANALYZE_PURCHASE") {
      const backend = state.backendUrl || "http://127.0.0.1:8000";
      let decision = null;
      try {
        const res = await fetch(`${backend}/analyze-purchase`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            purchase: message.purchase,
            financial_state: state.financialState
          })
        });
        if (res.ok) {
          decision = await res.json();
        }
      } catch (_) {}

      if (!decision) {
        decision = localDecision(message.purchase, state.financialState);
      }

      const warningCount = decision.affordability_status === "not_affordable" ? state.warningCount + 1 : state.warningCount;
      const updated = await setState({
        mood: decision.mom_mood,
        warningCount,
        lastDecision: decision,
        rewardEligible: decision.mom_mood === "celebrating" || decision.affordability_status === "affordable_now"
      });

      if (sender.tab?.id) {
        chrome.tabs.sendMessage(sender.tab.id, { type: "DECISION_UPDATE", decision });
      }

      sendResponse({ ok: true, decision, state: updated });
      return;
    }

    sendResponse({ ok: false, error: "Unhandled message" });
  })();
  return true;
});

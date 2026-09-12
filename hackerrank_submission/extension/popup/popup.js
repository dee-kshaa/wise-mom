async function msg(message) {
  return await chrome.runtime.sendMessage(message);
}

async function load() {
  const state = await msg({ type: "GET_STATE" });
  document.getElementById("enabled").checked = !!state.enabled;
  document.getElementById("today").textContent = `₹${Math.round(state.todaysSpending || 0)}`;
  document.getElementById("month").textContent = `₹${Math.round(state.monthlySpending || 0)}`;
  document.getElementById("remain").textContent = `₹${Math.round(state.remainingBudget || 0)}`;
  document.getElementById("warning").textContent = state.lastDecision?.decision_explanation || "None";
  document.getElementById("reward").textContent = state.rewardEligible ? "Yes" : "No";
}

document.getElementById("enabled").addEventListener("change", async (e) => {
  await msg({ type: "SET_STATE", patch: { enabled: e.target.checked, hidden: !e.target.checked } });
});

document.getElementById("dashboard").addEventListener("click", async () => {
  await msg({ type: "OPEN_DASHBOARD" });
});

document.getElementById("settings").addEventListener("click", () => chrome.runtime.openOptionsPage());

document.getElementById("addExpense").addEventListener("click", async () => {
  const amount = Number(prompt("Amount in INR", "200"));
  const merchant = prompt("Merchant", "Manual entry");
  if (!amount || !merchant) return;
  const payload = {
    date: new Date().toISOString().slice(0, 10),
    merchant,
    amount,
    category: "OTHER",
    necessity: "optional",
    payment_method: "upi",
    notes: "added from popup"
  };
  await msg({ type: "ADD_EXPENSE", payload });
  alert("Expense added.");
});

document.getElementById("askMom").addEventListener("click", async () => {
  const name = prompt("What are you buying?", "Coffee");
  const amount = Number(prompt("Amount in INR", "250"));
  if (!name || !amount) return;
  const res = await msg({
    type: "ANALYZE_PURCHASE",
    purchase: { name, amount, category: "OTHER", necessity: "optional" }
  });
  alert(res.decision?.decision_explanation || "Mom is thinking...");
});

load();

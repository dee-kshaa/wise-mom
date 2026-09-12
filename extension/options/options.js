async function load() {
  const state = await chrome.storage.local.get(["backendUrl", "financialState"]);
  const fs = state.financialState || {};
  document.getElementById("backendUrl").value = state.backendUrl || "http://127.0.0.1:8000";
  document.getElementById("minBalance").value = fs.preferred_minimum_balance || 10000;
  document.getElementById("discretionaryBudget").value = fs.discretionary_budget || 5000;
  document.getElementById("rewardCap").value = fs.reward_cap || 2000;
}

document.getElementById("save").addEventListener("click", async () => {
  const backendUrl = document.getElementById("backendUrl").value.trim();
  const preferred_minimum_balance = Number(document.getElementById("minBalance").value || 10000);
  const discretionary_budget = Number(document.getElementById("discretionaryBudget").value || 5000);
  const reward_cap = Number(document.getElementById("rewardCap").value || 2000);

  const existing = await chrome.storage.local.get(["financialState"]);
  await chrome.storage.local.set({
    backendUrl,
    financialState: {
      ...(existing.financialState || {}),
      preferred_minimum_balance,
      discretionary_budget,
      reward_cap
    }
  });

  alert("Saved settings.");
});

load();

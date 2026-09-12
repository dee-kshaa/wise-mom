async function loadSummary() {
  const state = await chrome.storage.local.get(["backendUrl"]);
  const backend = state.backendUrl || "http://127.0.0.1:8000";
  try {
    const res = await fetch(`${backend}/financial-summary`);
    const data = await res.json();
    document.getElementById("daily").textContent = `₹${Math.round(data.daily_total || 0)}`;
    document.getElementById("weekly").textContent = `₹${Math.round(data.weekly_total || 0)}`;
    document.getElementById("monthly").textContent = `₹${Math.round(data.monthly_total || 0)}`;
    document.getElementById("remaining").textContent = `₹${Math.round(data.remaining_budget || 0)}`;

    const list = document.getElementById("categories");
    list.innerHTML = "";
    Object.entries(data.category_breakdown || {}).forEach(([k, v]) => {
      const li = document.createElement("li");
      li.textContent = `${k}: ₹${Math.round(v)}`;
      list.appendChild(li);
    });
  } catch {
    document.getElementById("insight").textContent = "Backend not reachable. Start backend and refresh.";
  }
}

loadSummary();

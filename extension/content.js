(() => {
  const BLOCKLIST = ["bank", "paytm", "gpay", "government", "health", "hospital"]; // never block these
  let momApi = null;
  let state = null;

  function isEligiblePage() {
    const url = location.href.toLowerCase();
    return !url.startsWith("chrome://") && !url.startsWith("edge://") && !url.startsWith("about:");
  }

  function shouldAvoidIntervention() {
    const url = location.href.toLowerCase();
    return BLOCKLIST.some((k) => url.includes(k));
  }

  function detectPurchaseContext() {
    const text = document.body?.innerText?.slice(0, 5000) || "";
    const priceMatch = text.match(/(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)/i);
    const hasBuySignal = /add to cart|buy now|checkout|place order/i.test(text);
    if (!priceMatch || !hasBuySignal) return null;

    const amount = Number(priceMatch[1].replace(/,/g, ""));
    if (!Number.isFinite(amount) || amount <= 0) return null;

    const titleEl = document.querySelector("h1, [data-testid*='title'], .product-title, #productTitle");
    return {
      name: (titleEl?.textContent || document.title || "Product").trim().slice(0, 120),
      amount,
      category: "SHOPPING",
      necessity: "optional",
      merchant: location.hostname
    };
  }

  async function askBackground(msg) {
    return await chrome.runtime.sendMessage(msg);
  }

  function ensureHost(position) {
    let host = document.getElementById("wise-mom-shadow-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "wise-mom-shadow-host";
      document.documentElement.appendChild(host);
      host.attachShadow({ mode: "open" });
    }
    host.style.pointerEvents = "auto";
    host.style.left = `${position?.x ?? window.innerWidth - 260}px`;
    host.style.top = `${position?.y ?? window.innerHeight - 290}px`;
    return host;
  }

  async function mount() {
    if (!isEligiblePage()) return;
    state = await askBackground({ type: "GET_STATE" });
    if (!state?.enabled || state.hidden) return;

    const host = ensureHost(state.position);
    const root = host.shadowRoot;
    const [htmlText] = await Promise.all([
      fetch(chrome.runtime.getURL("character/wise-mom.html")).then((r) => r.text())
    ]);

    root.innerHTML = "";
    const style = document.createElement("link");
    style.rel = "stylesheet";
    style.href = chrome.runtime.getURL("character/wise-mom.css");
    root.appendChild(style);

    const wrapper = document.createElement("div");
    wrapper.innerHTML = htmlText;
    root.appendChild(wrapper);

    await import(chrome.runtime.getURL("character/wise-mom.js"));
    momApi = window.initWiseMomCharacter(root, state, {
      onStatePatch: (patch) => askBackground({ type: "SET_STATE", patch }),
      onAskMom: async (message) => {
        const purchase = detectPurchaseContext() || { name: message || "Unknown", amount: 0, category: "OTHER", necessity: "optional" };
        const res = await askBackground({ type: "ANALYZE_PURCHASE", purchase });
        return res.decision;
      }
    });

    if (state.lastDecision) {
      momApi.applyDecision(state.lastDecision);
    }

    const maybePurchase = detectPurchaseContext();
    if (maybePurchase) {
      const result = await askBackground({ type: "ANALYZE_PURCHASE", purchase: maybePurchase });
      momApi.applyDecision(result.decision);
      if (["not_affordable"].includes(result.decision.affordability_status) && !shouldAvoidIntervention()) {
        momApi.showBlocker(result.decision);
      }
    }
  }

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "DECISION_UPDATE" && momApi) {
      momApi.applyDecision(msg.decision);
      if (msg.decision.affordability_status === "not_affordable" && !shouldAvoidIntervention()) {
        momApi.showBlocker(msg.decision);
      }
    }
  });

  mount();
})();

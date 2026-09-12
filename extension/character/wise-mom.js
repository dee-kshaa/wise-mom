window.initWiseMomCharacter = function initWiseMomCharacter(root, state, callbacks) {
  const shell = root.querySelector(".wm-shell");
  const bubble = root.querySelector(".wm-bubble");
  const character = root.querySelector("#wm-character");
  const panel = root.querySelector("#wm-panel");
  const blocker = root.querySelector("#wm-blocker");
  const blockerText = root.querySelector("#wm-blocker-text");
  const summary = root.querySelector("#wm-summary");
  const spending = root.querySelector("#wm-spending");

  spending.textContent = Math.round(state.todaysSpending || 0);

  const moodMap = {
    idle: "Beta... I'm watching your wallet.",
    thinking: "Hmm, let me check rent and bills.",
    happy: "Nice sensible spending today!",
    proud: "Good choice beta. I am proud.",
    worried: "Careful. This might stretch finances.",
    suspicious: "Do you NEED this?",
    scolding: "Absolutely not. Put it back.",
    angry: "THAT'S ENOUGH. Close cart.",
    approving: "Okay, this one is actually sensible.",
    celebrating: "Fine. One little treat allowed.",
    sleeping: "No shopping drama? Good."
  };

  function setMood(mood) {
    character.className = `wm-character state-${mood || "idle"}`;
    bubble.textContent = moodMap[mood] || moodMap.idle;
  }

  setMood(state.mood || "idle");

  let dragging = false;
  let offsetX = 0;
  let offsetY = 0;

  character.addEventListener("pointerdown", (e) => {
    dragging = true;
    offsetX = e.clientX - shell.getBoundingClientRect().left;
    offsetY = e.clientY - shell.getBoundingClientRect().top;
    character.style.cursor = "grabbing";
  });

  root.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const nextX = Math.max(0, e.clientX - offsetX);
    const nextY = Math.max(0, e.clientY - offsetY);
    const host = root.host;
    host.style.left = `${nextX}px`;
    host.style.top = `${nextY}px`;
  });

  root.addEventListener("pointerup", async () => {
    if (!dragging) return;
    dragging = false;
    character.style.cursor = "grab";
    await callbacks.onStatePatch({
      position: {
        x: parseInt(root.host.style.left || "0", 10),
        y: parseInt(root.host.style.top || "0", 10)
      }
    });
  });

  shell.addEventListener("click", async (e) => {
    const action = e.target?.dataset?.action;
    if (!action) {
      panel.classList.toggle("hidden");
      return;
    }

    if (action === "hide") {
      await callbacks.onStatePatch({ hidden: true });
      root.host.remove();
    }
    if (action === "minimize") {
      const mini = shell.classList.toggle("wm-mini");
      root.querySelector(".wm-bubble").style.display = mini ? "none" : "block";
      character.style.display = mini ? "none" : "block";
      await callbacks.onStatePatch({ minimized: mini });
    }
    if (action === "analyze") {
      const decision = await callbacks.onAskMom("Should I buy this?");
      applyDecision(decision);
      panel.classList.remove("hidden");
    }
    if (action === "dismiss" || action === "dismiss-blocker" || action === "wait") {
      blocker.classList.add("hidden");
      panel.classList.add("hidden");
    }
  });

  function applyDecision(decision) {
    if (!decision) return;
    setMood(decision.mom_mood || "thinking");
    bubble.textContent = decision.decision_explanation || bubble.textContent;
    summary.textContent = decision.decision_explanation || "You're doing okay today.";
    spending.textContent = Math.round(state.todaysSpending || 0);
  }

  function showBlocker(decision) {
    blocker.classList.remove("hidden");
    blockerText.textContent = decision.decision_explanation || "NOPE.";
    setMood("scolding");
  }

  return { applyDecision, showBlocker };
};

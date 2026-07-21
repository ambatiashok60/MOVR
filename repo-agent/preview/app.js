/* RepoAgent static preview — drives the real backend over REST + SSE.
   This is a local stand-in for the Angular app; it exercises the same contract. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const api = (p) => p; // same-origin

  const state = {
    mode: "agent",
    runId: null,
    lastSequence: 0,
    counters: { reads: 0, tools: 0, mods: 0 },
    batches: new Map(), // batch_id -> {index,type,title,markdown,el}
    actions: [],
    files: new Set(),
    lastHeartbeat: Date.now(),
    es: null,
  };

  // ---------------------------------------------------------------- helpers
  const escapeHtml = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  function renderMarkdown(md) {
    // Split on fenced code blocks, render each safely.
    const parts = md.split(/(```[\s\S]*?```)/g);
    return parts.map((part) => {
      const fence = part.match(/^```(\w*)\n?([\s\S]*?)```$/);
      if (fence) {
        const lang = fence[1] || "";
        const code = fence[2].replace(/\n$/, "");
        if (lang === "diff") {
          const colored = escapeHtml(code).split("\n").map((l) =>
            l.startsWith("+") ? `<span class="add">${l}</span>` :
            l.startsWith("-") ? `<span class="del">${l}</span>` : l).join("\n");
          return `<pre class="diff">${colored}</pre>`;
        }
        return `<pre>${escapeHtml(code)}</pre>`;
      }
      let html = escapeHtml(part)
        .replace(/`([^`]+)`/g, '<code class="inline">$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/### (.*)/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br/>");
      return html;
    }).join("");
  }

  const STAGES = [
    ["understand", "Understand"], ["plan", "Plan"], ["inspect", "Inspect Repository"],
    ["modify", "Modify Code"], ["validate", "Validate"], ["complete", "Complete"],
  ];

  function stageIndexForStatus(status) {
    return { queued: 1, planning: 1, running: 2, validating: 4, completing: 5,
             completed: 6, failed: 6, cancelled: 6, waiting_for_auth: 2 }[status] ?? 0;
  }

  // ---------------------------------------------------------------- rendering
  function renderStages(status) {
    const reached = stageIndexForStatus(status);
    const el = document.createElement("div");
    el.className = "stages";
    STAGES.forEach(([key, label], i) => {
      const done = i < reached, active = i === reached && status !== "completed";
      el.insertAdjacentHTML("beforeend",
        `<div class="stage ${done ? "done" : ""} ${active ? "active" : ""}">
           <div class="ring">${done ? "✓" : active ? "●" : ""}</div><div class="line">${label}</div></div>`);
      if (i < STAGES.length - 1) el.insertAdjacentHTML("beforeend", '<div class="sep"></div>');
    });
    return el;
  }

  function renderPlan(plan) {
    const panel = $("planPanel");
    if (!plan || !plan.steps) { panel.innerHTML = '<div class="empty">No active run.</div>'; return; }
    panel.innerHTML = plan.steps.map((s) => {
      const mk = s.status === "completed" ? "✓" : s.status === "in_progress" ? "●" : "";
      return `<div class="plan-step ${s.status}"><span class="mk">${mk}</span>${escapeHtml(s.title)}</div>`;
    }).join("");
  }

  function renderFiles() {
    const panel = $("filesPanel");
    if (!state.files.size) { panel.innerHTML = '<div class="empty">—</div>'; return; }
    panel.innerHTML = [...state.files].slice(-12).map((f) =>
      `<div class="file"><span class="fi">📄</span>${escapeHtml(f)}</div>`).join("");
  }

  function renderCounters() {
    $("mRead").textContent = state.counters.reads;
    $("mTools").textContent = state.counters.tools;
    $("mMods").textContent = state.counters.mods;
  }

  function pushAction(label) {
    const t = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    state.actions.unshift({ label, t });
    state.actions = state.actions.slice(0, 8);
    $("actionsPanel").innerHTML = state.actions.map((a) =>
      `<div class="action"><span>✓ ${escapeHtml(a.label)}</span><span class="t">${a.t}</span></div>`).join("");
  }

  function renderValidation(results) {
    const panel = $("validationPanel");
    if (!results || !results.length) { panel.innerHTML = '<div class="empty">—</div>'; return; }
    panel.innerHTML = results.map((r) => {
      const cls = r.status === "passed" ? "pass" : r.status === "failed" ? "fail" : "skip";
      const icon = r.status === "passed" ? "✓" : r.status === "failed" ? "✕" : "○";
      return `<div class="validation-row"><span class="${cls}">${icon} ${escapeHtml(r.name)}</span></div>`;
    }).join("");
  }

  function assistantContainer() {
    let box = $("assistantBox");
    if (!box) {
      const wrap = document.createElement("div");
      wrap.className = "msg";
      wrap.innerHTML = `<div class="who assistant"><span class="av">◇</span> RepoAgent</div>`;
      const stages = renderStages("planning"); stages.id = "stagesRow"; wrap.appendChild(stages);
      box = document.createElement("div"); box.id = "assistantBox"; wrap.appendChild(box);
      $("chat").appendChild(wrap);
    }
    return box;
  }

  function ensureBatchEl(batch) {
    const box = assistantContainer();
    let entry = state.batches.get(batch.batch_id);
    if (!entry) {
      const section = document.createElement("div");
      section.className = "section";
      section.innerHTML = `<h4>${escapeHtml(batch.title || batch.type)}</h4><div class="body"></div>`;
      box.appendChild(section);
      entry = { ...batch, markdown: "", el: section.querySelector(".body") };
      state.batches.set(batch.batch_id, entry);
    }
    return entry;
  }

  function setStatusStages(status) {
    const row = $("stagesRow");
    if (row) row.replaceWith(Object.assign(renderStages(status), { id: "stagesRow" }));
  }

  // ---------------------------------------------------------------- SSE reducer
  function handleEvent(type, data) {
    if (typeof data.sequence === "number") {
      if (data.sequence <= state.lastSequence) return; // dedup by sequence
      state.lastSequence = data.sequence;
    }
    switch (type) {
      case "heartbeat": state.lastHeartbeat = Date.now(); setConn(true); break;
      case "run_started": pushAction("Run started"); setStatusStages("running"); break;
      case "plan_created": renderPlan(data.plan); pushAction("Plan created"); break;
      case "plan_updated": renderPlan(data.plan); break;
      case "tool_started": pushAction("Started " + data.tool_name); break;
      case "tool_completed":
      case "tool_failed": {
        state.counters.tools += 1;
        pushAction((data.success ? "" : "Failed ") + (data.summary || data.tool_name));
        renderCounters();
        break;
      }
      case "observation_created": break;
      case "validation_started": setStatusStages("validating"); pushAction("Validation started"); break;
      case "validation_completed": renderValidation(data.results); pushAction("Validation completed"); break;
      case "aws_reauthentication_required":
        showBanner("AWS session expired. Complete the sign-in in your browser. The run will resume automatically.");
        setConn(false); break;
      case "aws_reauthenticated": hideBanner(); setConn(true); break;
      case "conversation_compacted": pushAction("Older context compacted"); break;
      case "response_batch_started": ensureBatchEl(data); break;
      case "response_delta": {
        const entry = [...state.batches.values()].find((b) => b.batch_id === data.batch_id);
        if (entry) { entry.markdown += data.delta; entry.el.innerHTML = renderMarkdown(entry.markdown); scrollChat(); }
        break;
      }
      case "response_batch_completed": break;
      case "run_completed":
        setStatusStages("completed");
        state.counters.reads = data.files_read ?? state.counters.reads;
        state.counters.tools = data.tool_calls ?? state.counters.tools;
        state.counters.mods = data.files_modified ?? state.counters.mods;
        renderCounters(); pushAction("Run completed"); refreshFilesFromServer(); finishRun(); break;
      case "run_failed": setStatusStages("failed"); showBanner("Run failed: " + (data.error?.message || "")); finishRun(); break;
      case "run_cancelled": pushAction("Run cancelled"); finishRun(); break;
    }
  }

  async function refreshFilesFromServer() {
    if (!state.runId) return;
    try {
      const res = await fetch(api(`/api/agent-runs/${state.runId}/changes`));
      const changes = await res.json();
      changes.forEach((c) => state.files.add(c.path));
      renderFiles();
    } catch (_) {}
  }

  // ---------------------------------------------------------------- stream mgmt
  function connect(runId, afterSequence = 0) {
    if (state.es) state.es.close();
    const es = new EventSource(api(`/api/agent-runs/${runId}/events?after_sequence=${afterSequence}`));
    state.es = es;
    const types = ["run_started", "plan_created", "plan_updated", "tool_started", "tool_completed",
      "tool_failed", "observation_created", "response_batch_started", "response_delta",
      "response_batch_completed", "validation_started", "validation_completed", "conversation_compacted",
      "aws_reauthentication_required", "aws_reauthenticated", "run_completed", "run_failed",
      "run_cancelled", "heartbeat"];
    types.forEach((t) => es.addEventListener(t, (e) => {
      try { handleEvent(t, JSON.parse(e.data)); } catch (_) {}
    }));
    es.onerror = () => { setConn(false); /* EventSource auto-reconnects; on reconnect it resends from lastEventId */ };
  }

  function finishRun() {
    if (state.es) { state.es.close(); state.es = null; }
    $("send").disabled = false;
  }

  // watchdog: if no heartbeat/events for a while, flag the connection.
  setInterval(() => {
    if (!state.runId) return;
    const idle = Date.now() - state.lastHeartbeat;
    if (idle > 45000) setConn(false);
  }, 5000);

  // ---------------------------------------------------------------- UI wiring
  function setConn(ok) {
    const el = $("conn");
    el.classList.toggle("bad", !ok);
    el.lastChild.textContent = ok ? " Connected" : " Reconnecting…";
  }
  function showBanner(text) {
    let b = $("banner");
    if (!b) { b = document.createElement("div"); b.id = "banner"; b.className = "banner"; $("chat").prepend(b); }
    b.textContent = text; b.style.display = "block";
  }
  function hideBanner() { const b = $("banner"); if (b) b.style.display = "none"; }
  function scrollChat() { const c = $("chat"); c.scrollTop = c.scrollHeight; }

  function addUserMessage(text) {
    const es = $("emptyState"); if (es) es.remove();
    const wrap = document.createElement("div");
    wrap.className = "msg";
    wrap.innerHTML = `<div class="who user"><span class="av">You</span> You</div>
      <div class="bubble user">${escapeHtml(text)}</div>`;
    $("chat").appendChild(wrap); scrollChat();
  }

  function resetRunView() {
    const old = $("assistantBox")?.closest(".msg"); if (old) old.remove();
    state.batches.clear(); state.actions = []; state.files.clear();
    state.counters = { reads: 0, tools: 0, mods: 0 }; state.lastSequence = 0;
    renderCounters(); renderFiles(); renderValidation([]);
    $("actionsPanel").innerHTML = '<div class="empty">—</div>';
  }

  async function send() {
    const message = $("prompt").value.trim();
    const workspace = $("workspace").value.trim();
    if (!message || !workspace) { showBanner("Enter a workspace path and a message."); return; }
    hideBanner();
    $("send").disabled = true;
    resetRunView();
    addUserMessage(message);
    state.lastHeartbeat = Date.now(); setConn(true);

    const clientRequestId = (crypto.randomUUID && crypto.randomUUID()) || String(Date.now());
    try {
      const res = await fetch(api("/api/agent-runs"), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_path: workspace, mode: state.mode, message,
          client_request_id: clientRequestId }),
      });
      if (!res.ok) { showBanner("Failed to start run (" + res.status + ")"); $("send").disabled = false; return; }
      const data = await res.json();
      state.runId = data.run_id;
      connect(data.run_id, 0);
    } catch (err) {
      showBanner("Network error starting run."); $("send").disabled = false;
    }
  }

  $("send").addEventListener("click", send);
  $("prompt").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
  $("modes").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-mode]"); if (!b) return;
    state.mode = b.dataset.mode;
    [...$("modes").children].forEach((c) => c.classList.toggle("on", c === b));
  });
  $("newChat").addEventListener("click", () => { resetRunView(); const es = $("emptyState"); if (!es) location.reload(); });

  // seed a fake sidebar + default workspace from the backend
  async function boot() {
    const seed = ["Fix API scenario generation status", "Refactor task manager service",
      "Add pagination to scenarios API", "Improve logging in API layer", "Explain authentication flow"];
    $("convList").innerHTML = seed.map((t, i) =>
      `<div class="conv ${i === 0 ? "active" : ""}"><span class="dot">✓</span>
        <span class="title">${t}</span><span class="time">${i === 0 ? "now" : i + "d"}</span></div>`).join("");
    try {
      const h = await fetch(api("/api/health")).then((r) => r.json());
      if (h.default_workspace && !$("workspace").value) $("workspace").value = h.default_workspace;
      setConn(true);
    } catch (_) { setConn(false); }
  }
  boot();
})();

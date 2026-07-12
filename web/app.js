// Malatang static replay showcase — no server, no live runner.
// Loads committed evidence from /data/replay.json once and replays it client-side.

const COLORS = {
  grid: "#232c3b",
  muted: "#9aa4b8",
  accent: "#ff6a2a",
  holdout: "#6f7dff",
  text: "#f3f5f8",
};

const els = {
  evidencePill: document.getElementById("evidence-pill"),
  sumBaseline: document.getElementById("sum-baseline"),
  sumFinal: document.getElementById("sum-final"),
  sumHoldout: document.getElementById("sum-holdout"),
  replayStatus: document.getElementById("replay-status"),
  replayMessage: document.getElementById("replay-message"),
  playBtn: document.getElementById("play-btn"),
  stepBtn: document.getElementById("step-btn"),
  resetBtn: document.getElementById("reset-btn"),
  speedSelect: document.getElementById("speed-select"),
  scrubber: document.getElementById("scrubber"),
  scrubTicks: document.getElementById("scrub-ticks"),
  finalBanner: document.getElementById("final-banner"),
  finalText: document.getElementById("final-text"),
  activeStatus: document.getElementById("active-status"),
  activeIteration: document.getElementById("active-iteration"),
  activePlaybook: document.getElementById("active-playbook"),
  activeRate: document.getElementById("active-rate"),
  activeProgressText: document.getElementById("active-progress-text"),
  activeProgressFill: document.getElementById("active-progress-fill"),
  activeDetail: document.getElementById("active-detail"),
  passChart: document.getElementById("pass-chart"),
  loopRun: document.getElementById("loop-run"),
  loopVerify: document.getElementById("loop-verify"),
  loopReflect: document.getElementById("loop-reflect"),
  loopRewrite: document.getElementById("loop-rewrite"),
  pipelineSteps: document.getElementById("pipeline-steps"),
  conditionsScore: document.getElementById("conditions-score"),
  metricsBody: document.getElementById("metrics-body"),
  holdoutBadge: document.getElementById("holdout-badge"),
  holdoutPanel: document.getElementById("holdout-panel"),
  benchNote: document.getElementById("bench-note"),
  benchClasses: document.getElementById("bench-classes"),
  bugGrid: document.getElementById("bug-grid"),
  benchFoot: document.getElementById("bench-foot"),
  playbookChips: document.getElementById("playbook-chips"),
  playbookBody: document.getElementById("playbook-body"),
  pbStats: document.getElementById("pb-stats"),
  modeDiff: document.getElementById("mode-diff"),
  modeFull: document.getElementById("mode-full"),
  footerNote: document.getElementById("footer-note"),
};

let data = null;
let steps = []; // ordered replay steps
let current = 0; // 0 = nothing revealed; steps[current-1] is the last revealed
let playTimer = null;
let loopTimer = null;
let pbMode = "diff";
let currentPbVersion = null;

function pct(rate) {
  if (rate == null || Number.isNaN(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
}

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function stepNote(step) {
  if (!step || !data.annotations) return "";
  const key = step.kind === "holdout" ? "holdout" : String(step.iteration);
  return data.annotations[key] || "";
}

// ---- data → replay steps ------------------------------------------------
function buildSteps(payload) {
  const out = payload.metrics.map((m) => ({
    kind: "iteration",
    iteration: m.iteration,
    playbook: m.playbook_version || `v${m.iteration}`,
    passed: m.bugs_passed,
    total: m.bugs_total,
    rate: m.pass_rate,
    llm: m.total_llm_calls,
  }));
  if (payload.holdout) {
    const h = payload.holdout;
    out.push({
      kind: "holdout",
      iteration: h.iteration,
      playbook: h.playbook_version,
      passed: h.bugs_passed,
      total: h.bugs_total,
      rate: h.pass_rate,
      llm: h.total_llm_calls,
    });
  }
  return out;
}

// ---- chart --------------------------------------------------------------
function drawChart(revealCount) {
  const canvas = els.passChart;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const pad = { top: 26, right: 28, bottom: 46, left: 52 };
  const plotW = W - pad.left - pad.right;
  const plotH = H - pad.top - pad.bottom;

  const positions = steps.length; // fixed domain so points land in place
  const xFor = (i) => pad.left + (i / Math.max(positions - 1, 1)) * plotW;
  const yFor = (rate) => pad.top + plotH - rate * plotH;

  // gridlines
  ctx.strokeStyle = COLORS.grid;
  ctx.lineWidth = 1;
  ctx.font = "12px 'Segoe UI', sans-serif";
  for (let t = 0; t <= 4; t += 1) {
    const y = pad.top + (t / 4) * plotH;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(W - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = COLORS.muted;
    ctx.fillText(`${100 - t * 25}%`, 12, y + 4);
  }

  // x labels
  ctx.fillStyle = COLORS.muted;
  steps.forEach((s, i) => {
    const label = s.kind === "holdout" ? "hold-out" : `iter ${s.iteration}`;
    ctx.fillText(label, xFor(i) - 22, H - 16);
  });

  const shown = steps.slice(0, revealCount);
  if (!shown.length) {
    ctx.fillStyle = COLORS.muted;
    ctx.fillText("Press Play to reveal the curve.", pad.left + 8, H / 2);
    return;
  }

  // line (training points only connected; holdout stands alone)
  const trainShown = shown.filter((s) => s.kind === "iteration");
  ctx.strokeStyle = COLORS.accent;
  ctx.lineWidth = 3;
  ctx.beginPath();
  trainShown.forEach((s, idx) => {
    const x = xFor(steps.indexOf(s));
    const y = yFor(s.rate);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // points + labels
  shown.forEach((s) => {
    const i = steps.indexOf(s);
    const x = xFor(i);
    const y = yFor(s.rate);
    ctx.fillStyle = s.kind === "holdout" ? COLORS.holdout : COLORS.accent;
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = COLORS.text;
    ctx.font = "13px 'Segoe UI', sans-serif";
    ctx.fillText(pct(s.rate), x - 14, y - 13);
  });
}

// ---- self-improvement loop diagram ---------------------------------------
function setLoopStages(active) {
  const map = {
    run: els.loopRun,
    verify: els.loopVerify,
    reflect: els.loopReflect,
    rewrite: els.loopRewrite,
  };
  Object.entries(map).forEach(([key, el]) => {
    el.classList.toggle("active", active.includes(key));
  });
}

function animateLoop(step, { flash = true } = {}) {
  clearTimeout(loopTimer);
  loopTimer = null;
  if (!step) {
    setLoopStages([]);
    return;
  }
  setLoopStages(["run", "verify"]);
  const idx = steps.indexOf(step);
  const next = steps[idx + 1];
  // Between training iterations the harness reflects and rewrites the playbook.
  if (flash && step.kind === "iteration" && next && next.kind === "iteration") {
    const interval = Number(els.speedSelect.value);
    loopTimer = setTimeout(() => {
      setLoopStages(["reflect", "rewrite"]);
      highlightPlaybook(next.playbook); // show the freshly rewritten playbook
    }, Math.min(interval * 0.55, 900));
  }
}

// ---- render revealed state ---------------------------------------------
function renderActive(step) {
  if (!step) {
    els.activeStatus.textContent = "idle";
    els.activeStatus.className = "badge idle";
    els.activeIteration.textContent = "—";
    els.activePlaybook.textContent = "—";
    els.activeRate.textContent = "—";
    els.activeProgressText.textContent = `0 / ${data.benchmark.training_total}`;
    els.activeProgressFill.style.width = "0%";
    els.activeDetail.textContent = "Start the replay to see each iteration.";
    return;
  }
  const isHold = step.kind === "holdout";
  els.activeStatus.textContent = isHold ? "hold-out" : "complete";
  els.activeStatus.className = `badge ${isHold ? "running" : "complete"}`;
  els.activeIteration.textContent = isHold ? `${step.iteration} · H` : String(step.iteration);
  els.activePlaybook.textContent = step.playbook;
  els.activeRate.textContent = pct(step.rate);
  els.activeProgressText.textContent = `${step.passed} / ${step.total}`;
  els.activeProgressFill.style.width = `${(step.passed / step.total) * 100}%`;
  els.activeDetail.textContent = isHold
    ? `Hold-out set (never entered training): ${step.passed}/${step.total} verified with playbook ${step.playbook}.`
    : `${step.passed}/${step.total} bugs verified by build + tests · ${step.llm ?? "—"} LLM calls · playbook ${step.playbook}.`;
}

function renderPipeline(revealCount) {
  els.pipelineSteps.innerHTML = "";
  const iters = steps.filter((s) => s.kind === "iteration");
  iters.forEach((s) => {
    const idx = steps.indexOf(s);
    const done = idx < revealCount;
    const active = idx === revealCount - 1;
    const node = document.createElement("div");
    node.className = `pipeline-step ${active ? "running" : done ? "complete" : ""}`;
    node.innerHTML = `
      <h3>Iteration ${s.iteration}</h3>
      <p>Playbook ${s.playbook}</p>
      <p>${done ? `Pass rate ${pct(s.rate)}` : "pending"}</p>
    `;
    els.pipelineSteps.appendChild(node);
  });
}

function setCondition(id, met, detail) {
  const el = document.getElementById(id);
  el.classList.toggle("met", met);
  if (detail) el.querySelector(".cond-detail").textContent = detail;
}

function renderConditions() {
  const iterSteps = steps.filter((s) => s.kind === "iteration");
  const revealedIters = steps.slice(0, current).filter((s) => s.kind === "iteration");

  const allRevealed = iterSteps.length > 0 && revealedIters.length === iterSteps.length;
  const base = data.summary.baseline_pass_rate;
  const fin = data.summary.final_pass_rate;
  const improved = allRevealed && fin > base;
  setCondition(
    "cond-3",
    improved,
    improved
      ? `final ${pct(fin)} > baseline ${pct(base)} — dips at iter 2, committed as measured`
      : `replay the iterations to reveal the curve… (${revealedIters.length}/${iterSteps.length})`
  );

  const versions = [...new Set(revealedIters.map((s) => s.playbook))];
  const modified = versions.length >= 2;
  setCondition(
    "cond-4",
    modified,
    modified
      ? `playbook rewritten ${versions.length - 1}× so far (${versions[0]} → ${versions[versions.length - 1]})`
      : "waiting for the first reflection…"
  );

  els.conditionsScore.textContent = `${2 + (improved ? 1 : 0) + (modified ? 1 : 0)} / 4`;
  els.conditionsScore.className = `badge ${improved && modified ? "complete" : "neutral"}`;
}

function renderTable(revealCount) {
  const rows = steps.slice(0, revealCount).filter((s) => s.kind === "iteration");
  if (!rows.length) {
    els.metricsBody.innerHTML = '<tr><td colspan="5" class="muted">Replay to populate.</td></tr>';
    return;
  }
  els.metricsBody.innerHTML = rows
    .map(
      (s) => `
      <tr>
        <td>${s.iteration}</td>
        <td>${s.playbook}</td>
        <td>${s.passed} / ${s.total}</td>
        <td>${pct(s.rate)}</td>
        <td>${s.llm ?? "—"}</td>
      </tr>`
    )
    .join("");
}

function renderHoldout(revealed) {
  if (!revealed || !data.holdout) {
    els.holdoutBadge.textContent = "not run";
    els.holdoutBadge.className = "badge neutral";
    els.holdoutPanel.innerHTML = '<p class="muted">Revealed once at the end with the final playbook.</p>';
    return;
  }
  const h = data.holdout;
  els.holdoutBadge.textContent = "complete";
  els.holdoutBadge.className = "badge complete";
  els.holdoutPanel.innerHTML = `
    <p class="value">${pct(h.pass_rate)}</p>
    <p class="muted">${h.bugs_passed} / ${h.bugs_total} hold-out bugs verified</p>
    <p class="muted">Playbook ${h.playbook_version} · ${h.total_llm_calls ?? 0} LLM calls · never seen in training</p>
  `;
}

let gridMode = "training";
let lastGridPassed = 0;
function renderBugGrid(step) {
  const isHold = step && step.kind === "holdout";
  const wantMode = isHold ? "holdout" : "training";
  const bugs = isHold ? data.benchmark.holdout_bugs : data.benchmark.training_bugs;
  if (wantMode !== gridMode || !els.bugGrid.childElementCount) {
    els.bugGrid.innerHTML = "";
    bugs.forEach((b) => {
      const cell = document.createElement("div");
      cell.className = "bug-cell";
      cell.title = `${b.id} · ${b.class}\n${b.description}`;
      els.bugGrid.appendChild(cell);
    });
    gridMode = wantMode;
    lastGridPassed = 0;
    els.benchNote.textContent = isHold
      ? `${bugs.length} hold-out bugs`
      : `${bugs.length} training bugs`;
  }
  const passed = step ? step.passed : 0;
  Array.from(els.bugGrid.children).forEach((cell, i) => {
    const on = i < passed;
    // Cascade newly-passing cells; clearing or rewinding is instant.
    if (on && !cell.classList.contains("passed") && i >= lastGridPassed) {
      cell.style.transitionDelay = `${(i - lastGridPassed) * 45}ms`;
    } else {
      cell.style.transitionDelay = "0ms";
    }
    cell.classList.toggle("passed", on);
  });
  lastGridPassed = passed;
}

function renderScrubTicks() {
  els.scrubTicks.innerHTML = steps
    .map((s) => `<span>${s.kind === "holdout" ? "H" : s.iteration}</span>`)
    .join("");
}

// ---- playbook panel (chips + diff) ---------------------------------------
function lineDiff(aText, bText) {
  const a = aText.split("\n");
  const b = bText.split("\n");
  const n = a.length;
  const m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      out.push({ t: " ", s: a[i] });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ t: "-", s: a[i] });
      i += 1;
    } else {
      out.push({ t: "+", s: b[j] });
      j += 1;
    }
  }
  while (i < n) out.push({ t: "-", s: a[i++] });
  while (j < m) out.push({ t: "+", s: b[j++] });
  return out;
}

function renderDiffHtml(diff) {
  const line = (d) => {
    const cls = d.t === "+" ? "dl-add" : d.t === "-" ? "dl-del" : "dl-ctx";
    const prefix = d.t === " " ? "  " : `${d.t} `;
    return `<span class="dl ${cls}">${esc(prefix + d.s)}</span>`;
  };
  const out = [];
  let i = 0;
  while (i < diff.length) {
    if (diff[i].t !== " ") {
      out.push(line(diff[i]));
      i += 1;
      continue;
    }
    let j = i;
    while (j < diff.length && diff[j].t === " ") j += 1;
    const run = j - i;
    if (run > 6) {
      out.push(line(diff[i]), line(diff[i + 1]));
      out.push(`<span class="dl dl-gap">··· ${run - 4} unchanged lines ···</span>`);
      out.push(line(diff[j - 2]), line(diff[j - 1]));
    } else {
      for (let k = i; k < j; k += 1) out.push(line(diff[k]));
    }
    i = j;
  }
  return out.join("");
}

function renderPlaybookBody(version) {
  const idx = data.playbooks.findIndex((p) => p.version === version);
  const pb = data.playbooks[idx];
  if (!pb) {
    els.playbookBody.textContent = "Select a playbook version.";
    els.pbStats.textContent = "";
    return;
  }
  if (pbMode === "full") {
    els.playbookBody.textContent = pb.body;
    els.pbStats.textContent = `${(pb.chars / 1000).toFixed(1)}k chars`;
    return;
  }
  const prev = data.playbooks[idx - 1];
  if (!prev) {
    els.playbookBody.textContent = pb.body;
    els.pbStats.textContent = `${version} is the seed playbook — no predecessor`;
    return;
  }
  const diff = lineDiff(prev.body, pb.body);
  const adds = diff.filter((d) => d.t === "+").length;
  const dels = diff.filter((d) => d.t === "-").length;
  els.pbStats.textContent = `${prev.version} → ${version}: +${adds} / −${dels} lines`;
  els.playbookBody.innerHTML = renderDiffHtml(diff);
}

function highlightPlaybook(version) {
  currentPbVersion = version;
  Array.from(els.playbookChips.children).forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.version === version);
  });
  renderPlaybookBody(version);
}

function setPbMode(mode) {
  pbMode = mode;
  els.modeDiff.classList.toggle("active", mode === "diff");
  els.modeFull.classList.toggle("active", mode === "full");
  if (currentPbVersion) renderPlaybookBody(currentPbVersion);
}

// ---- top-level render -----------------------------------------------------
function render() {
  const step = current > 0 ? steps[current - 1] : null;
  renderActive(step);
  renderPipeline(current);
  renderConditions();
  renderTable(current);
  drawChart(current);
  renderBugGrid(step);
  const holdoutRevealed = step && step.kind === "holdout";
  renderHoldout(holdoutRevealed);
  if (step) highlightPlaybook(step.playbook);
  els.scrubber.value = String(current);

  const atEnd = current >= steps.length;
  els.finalBanner.classList.toggle("show", atEnd);
  els.replayStatus.textContent = current === 0 ? "ready" : atEnd ? "done" : "replaying";
  els.replayStatus.className = `badge ${current === 0 ? "neutral" : atEnd ? "complete" : "running"}`;
  if (current === 0) {
    els.replayMessage.textContent =
      "Press Play to watch the harness improve across iterations, or Step through one at a time.";
  } else if (atEnd) {
    els.replayMessage.textContent = `Done — training ${pct(data.summary.baseline_pass_rate)} → ${pct(
      data.summary.final_pass_rate
    )}, hold-out ${pct(data.summary.holdout_pass_rate)}.`;
  } else if (step) {
    const label = step.kind === "holdout" ? "Hold-out eval" : `Iteration ${step.iteration}`;
    const note = stepNote(step);
    els.replayMessage.textContent = `${label} · playbook ${step.playbook}.${note ? ` ${note}` : ""}`;
  }
}

// ---- controls -----------------------------------------------------------
function stepForward({ flash = true } = {}) {
  if (current >= steps.length) {
    stopPlay();
    return;
  }
  current += 1;
  render();
  animateLoop(steps[current - 1], { flash });
  if (current >= steps.length) stopPlay();
}

function stepBack() {
  stopPlay();
  if (current === 0) return;
  current -= 1;
  render();
  animateLoop(current > 0 ? steps[current - 1] : null, { flash: false });
}

function startPlay() {
  if (current >= steps.length) {
    current = 0;
    render();
    animateLoop(null);
  }
  els.playBtn.textContent = "⏸ Pause";
  const speed = Number(els.speedSelect.value);
  stepForward();
  playTimer = setInterval(stepForward, speed);
}

function stopPlay() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
  els.playBtn.textContent = current >= steps.length ? "↺ Replay" : "▶ Play";
}

function togglePlay() {
  if (playTimer) stopPlay();
  else startPlay();
}

function reset() {
  stopPlay();
  current = 0;
  els.playBtn.textContent = "▶ Play";
  render();
  animateLoop(null);
}

// ---- init ---------------------------------------------------------------
function renderStatic() {
  const base = data.summary.baseline_pass_rate;
  const fin = data.summary.final_pass_rate;
  const hold = data.summary.holdout_pass_rate;
  els.sumBaseline.textContent = pct(base);
  els.sumFinal.textContent = pct(fin);
  els.sumHoldout.textContent = pct(hold);
  els.evidencePill.textContent = `${data.summary.iterations} iterations · real evidence`;

  const deltaPts = Math.round((fin - base) * 100);
  const rewrites = Math.max(data.playbooks.length - 1, 0);
  els.finalText.textContent =
    `Training ${pct(base)} → ${pct(fin)} (${deltaPts >= 0 ? "+" : ""}${deltaPts} pts) · ` +
    `hold-out ${pct(hold)} · playbook rewritten ${rewrites}× (v0 → ${data.playbooks.at(-1)?.version}) · ` +
    "every pass verified by build + tests in a sandbox.";

  const cc = data.benchmark.class_counts || {};
  els.benchClasses.innerHTML = Object.entries(cc)
    .map(([k, v]) => `<span class="class-chip">${k} <b>×${v}</b></span>`)
    .join("");
  els.benchFoot.textContent = data.note;

  // playbook chips
  const usedVersions = new Set(data.metrics.map((m) => m.playbook_version));
  els.playbookChips.innerHTML = "";
  data.playbooks.forEach((p) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `pb-chip ${usedVersions.has(p.version) ? "used" : ""}`;
    chip.dataset.version = p.version;
    chip.textContent = `${p.version} · ${(p.chars / 1000).toFixed(1)}k`;
    chip.addEventListener("click", () => highlightPlaybook(p.version));
    els.playbookChips.appendChild(chip);
  });

  els.footerNote.textContent = data.generated_from
    ? "Static evidence replay · generated from committed results/ + benchmark/ + playbook/"
    : "Static evidence replay";
}

async function init() {
  try {
    const res = await fetch("/data/replay.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = await res.json();
  } catch (err) {
    els.evidencePill.textContent = "Evidence unavailable";
    els.replayMessage.textContent = `Could not load /data/replay.json: ${err.message}. Run: python -m scripts.build_replay_data`;
    return;
  }
  steps = buildSteps(data);
  els.scrubber.max = String(steps.length);
  renderStatic();
  renderScrubTicks();
  highlightPlaybook(data.playbooks.at(-1)?.version);
  render();

  els.playBtn.addEventListener("click", togglePlay);
  els.stepBtn.addEventListener("click", () => {
    stopPlay();
    stepForward();
  });
  els.resetBtn.addEventListener("click", reset);
  els.scrubber.addEventListener("input", (e) => {
    stopPlay();
    current = Number(e.target.value);
    render();
    animateLoop(current > 0 ? steps[current - 1] : null, { flash: false });
  });
  els.speedSelect.addEventListener("change", () => {
    if (playTimer) {
      stopPlay();
      startPlay();
    }
  });
  els.modeDiff.addEventListener("click", () => setPbMode("diff"));
  els.modeFull.addEventListener("click", () => setPbMode("full"));

  document.addEventListener("keydown", (e) => {
    if (e.target instanceof Element && e.target.closest("input, select, textarea")) return;
    if (e.code === "Space") {
      e.preventDefault();
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
      togglePlay();
    } else if (e.code === "ArrowRight") {
      stopPlay();
      stepForward();
    } else if (e.code === "ArrowLeft") {
      stepBack();
    } else if (e.code === "KeyR") {
      reset();
    }
  });
}

init();

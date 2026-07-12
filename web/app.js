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
  activeStatus: document.getElementById("active-status"),
  activeIteration: document.getElementById("active-iteration"),
  activePlaybook: document.getElementById("active-playbook"),
  activeRate: document.getElementById("active-rate"),
  activeProgressText: document.getElementById("active-progress-text"),
  activeProgressFill: document.getElementById("active-progress-fill"),
  activeDetail: document.getElementById("active-detail"),
  passChart: document.getElementById("pass-chart"),
  pipelineSteps: document.getElementById("pipeline-steps"),
  metricsBody: document.getElementById("metrics-body"),
  holdoutBadge: document.getElementById("holdout-badge"),
  holdoutPanel: document.getElementById("holdout-panel"),
  benchNote: document.getElementById("bench-note"),
  benchClasses: document.getElementById("bench-classes"),
  bugGrid: document.getElementById("bug-grid"),
  benchFoot: document.getElementById("bench-foot"),
  playbookChips: document.getElementById("playbook-chips"),
  playbookBody: document.getElementById("playbook-body"),
  footerNote: document.getElementById("footer-note"),
};

let data = null;
let steps = []; // ordered replay steps
let current = 0; // 0 = nothing revealed; steps[i-1] is the last revealed
let playTimer = null;

function pct(rate) {
  if (rate == null || Number.isNaN(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
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
    els.benchNote.textContent = isHold
      ? `${bugs.length} hold-out bugs`
      : `${bugs.length} training bugs`;
  }
  const passed = step ? step.passed : 0;
  Array.from(els.bugGrid.children).forEach((cell, i) => {
    cell.classList.toggle("passed", i < passed);
  });
}

function renderScrubTicks() {
  els.scrubTicks.innerHTML = steps
    .map((s) => `<span>${s.kind === "holdout" ? "H" : s.iteration}</span>`)
    .join("");
}

function highlightPlaybook(version) {
  Array.from(els.playbookChips.children).forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.version === version);
  });
  const pb = data.playbooks.find((p) => p.version === version);
  els.playbookBody.textContent = pb ? pb.body : "Select a playbook version.";
}

function render() {
  const step = current > 0 ? steps[current - 1] : null;
  renderActive(step);
  renderPipeline(current);
  renderTable(current);
  drawChart(current);
  renderBugGrid(step);
  const holdoutRevealed = step && step.kind === "holdout";
  renderHoldout(holdoutRevealed);
  if (step) highlightPlaybook(step.playbook);
  els.scrubber.value = String(current);

  const atEnd = current >= steps.length;
  els.replayStatus.textContent = current === 0 ? "ready" : atEnd ? "done" : "replaying";
  els.replayStatus.className = `badge ${current === 0 ? "neutral" : atEnd ? "complete" : "running"}`;
  if (current === 0) {
    els.replayMessage.textContent =
      "Press Play to watch the harness improve across iterations, or Step through one at a time.";
  } else if (atEnd) {
    els.replayMessage.textContent = `Done — training ${pct(data.summary.baseline_pass_rate)} → ${pct(
      data.summary.final_pass_rate
    )}, hold-out ${pct(data.summary.holdout_pass_rate)}.`;
  } else {
    els.replayMessage.textContent = step
      ? `${step.kind === "holdout" ? "Hold-out eval" : `Iteration ${step.iteration}`} · playbook ${step.playbook}.`
      : "";
  }
}

// ---- controls -----------------------------------------------------------
function stepForward() {
  if (current >= steps.length) {
    stopPlay();
    return;
  }
  current += 1;
  render();
  if (current >= steps.length) stopPlay();
}

function startPlay() {
  if (current >= steps.length) current = 0;
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
}

// ---- init ---------------------------------------------------------------
function renderStatic() {
  els.sumBaseline.textContent = pct(data.summary.baseline_pass_rate);
  els.sumFinal.textContent = pct(data.summary.final_pass_rate);
  els.sumHoldout.textContent = pct(data.summary.holdout_pass_rate);
  els.evidencePill.textContent = `${data.summary.iterations} iterations · real evidence`;

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
  });
  els.speedSelect.addEventListener("change", () => {
    if (playTimer) {
      stopPlay();
      startPlay();
    }
  });
}

init();

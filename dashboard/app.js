const POLL_MS = 2000;

const els = {
  connectionStatus: document.getElementById("connection-status"),
  activeStatus: document.getElementById("active-status"),
  activeIteration: document.getElementById("active-iteration"),
  activePlaybook: document.getElementById("active-playbook"),
  activePassed: document.getElementById("active-passed"),
  activeProgressText: document.getElementById("active-progress-text"),
  activeProgressFill: document.getElementById("active-progress-fill"),
  activeDetail: document.getElementById("active-detail"),
  chartUpdated: document.getElementById("chart-updated"),
  passChart: document.getElementById("pass-chart"),
  chartFallback: document.getElementById("chart-fallback"),
  pipelineSteps: document.getElementById("pipeline-steps"),
  metricsBody: document.getElementById("metrics-body"),
  holdoutBadge: document.getElementById("holdout-badge"),
  holdoutPanel: document.getElementById("holdout-panel"),
  attemptFeed: document.getElementById("attempt-feed"),
  attemptsCount: document.getElementById("attempts-count"),
  lastUpdated: document.getElementById("last-updated"),
  runForm: document.getElementById("run-form"),
  runButton: document.getElementById("run-button"),
  runStartIteration: document.getElementById("run-start-iteration"),
  runIterations: document.getElementById("run-iterations"),
  runCreator: document.getElementById("run-creator"),
  runNoChart: document.getElementById("run-no-chart"),
  runJobStatus: document.getElementById("run-job-status"),
  runMessage: document.getElementById("run-message"),
  runLog: document.getElementById("run-log"),
};

let runFormTouched = false;
let submittingRun = false;

function pct(rate) {
  if (rate == null || Number.isNaN(rate)) return "—";
  return `${Math.round(rate * 100)}%`;
}

function statusClass(status) {
  return status || "idle";
}

function renderActive(active) {
  if (!active) {
    els.activeStatus.textContent = "idle";
    els.activeStatus.className = "badge idle";
    els.activeIteration.textContent = "—";
    els.activePlaybook.textContent = "—";
    els.activePassed.textContent = "—";
    els.activeProgressText.textContent = "0 / 25 bugs attempted";
    els.activeProgressFill.style.width = "0%";
    els.activeDetail.textContent = "Start the runner to see live progress.";
    return;
  }

  const bugsTotal = active.bugs_total || 25;
  const attempted = active.bugs_attempted || 0;
  const passed = active.bugs_passed || 0;
  const progress = Math.min(100, (attempted / bugsTotal) * 100);

  els.activeStatus.textContent = active.status;
  els.activeStatus.className = `badge ${statusClass(active.status)}`;
  els.activeIteration.textContent = String(active.iteration);
  els.activePlaybook.textContent = active.playbook_version || `v${active.iteration}`;
  els.activePassed.textContent = `${passed} / ${bugsTotal}`;
  els.activeProgressText.textContent = `${attempted} / ${bugsTotal} bugs attempted`;
  els.activeProgressFill.style.width = `${progress}%`;

  const passText =
    active.pass_rate != null
      ? `Recorded pass rate ${pct(active.pass_rate)}.`
      : `Live pass count ${passed} with ${active.attempts_total || 0} total attempts.`;
  els.activeDetail.textContent = passText;
}

function drawChart(metrics, holdout) {
  const canvas = els.passChart;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  const padding = { top: 24, right: 24, bottom: 42, left: 48 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const points = [...metrics].sort((a, b) => a.iteration - b.iteration);
  if (holdout) {
    points.push({
      iteration: (points.at(-1)?.iteration ?? -1) + 1,
      pass_rate: holdout.pass_rate,
      label: "holdout",
    });
  }

  if (!points.length) {
    ctx.fillStyle = "#9aa4b8";
    ctx.font = "14px Segoe UI, sans-serif";
    ctx.fillText("No metrics yet — run the benchmark.", padding.left, height / 2);
    return;
  }

  const xMax = Math.max(...points.map((row) => row.iteration), 0);
  const yMax = 1;

  const xFor = (iteration) =>
    padding.left + (iteration / Math.max(xMax, 1)) * plotW;
  const yFor = (rate) => padding.top + plotH - rate * plotH;

  ctx.strokeStyle = "#2a3140";
  ctx.lineWidth = 1;
  for (let tick = 0; tick <= 4; tick += 1) {
    const y = padding.top + (tick / 4) * plotH;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillStyle = "#9aa4b8";
    ctx.font = "12px Segoe UI, sans-serif";
    ctx.fillText(`${100 - tick * 25}%`, 8, y + 4);
  }

  ctx.strokeStyle = "#ff6a2a";
  ctx.lineWidth = 3;
  ctx.beginPath();
  points.forEach((row, index) => {
    const x = xFor(row.iteration);
    const y = yFor(row.pass_rate ?? 0);
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  points.forEach((row) => {
    const x = xFor(row.iteration);
    const y = yFor(row.pass_rate ?? 0);
    ctx.fillStyle = row.label === "holdout" ? "#6f7dff" : "#ff6a2a";
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#f3f5f8";
    ctx.font = "12px Segoe UI, sans-serif";
    const label =
      row.label === "holdout" ? "holdout" : `iter ${row.iteration}`;
    ctx.fillText(label, x - 16, height - 14);
    ctx.fillText(pct(row.pass_rate), x - 14, y - 12);
  });
}

function renderPipeline(steps) {
  els.pipelineSteps.innerHTML = "";
  if (!steps?.length) {
    els.pipelineSteps.innerHTML = '<p class="muted">No pipeline steps yet.</p>';
    return;
  }

  for (const step of steps) {
    const node = document.createElement("div");
    node.className = `pipeline-step ${statusClass(step.status)}`;
    node.innerHTML = `
      <h3>Iteration ${step.iteration}</h3>
      <p>Playbook ${step.playbook_version || `v${step.iteration}`}</p>
      <p>Status: ${step.status}</p>
      <p>Pass rate: ${pct(step.pass_rate)}</p>
    `;
    els.pipelineSteps.appendChild(node);
  }
}

function renderMetrics(metrics) {
  els.metricsBody.innerHTML = "";
  if (!metrics?.length) {
    els.metricsBody.innerHTML =
      '<tr><td colspan="5" class="muted">No completed iterations in metrics.jsonl yet.</td></tr>';
    return;
  }

  for (const row of metrics) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.iteration}</td>
      <td>${row.playbook_version}</td>
      <td>${row.bugs_passed} / ${row.bugs_total}</td>
      <td>${pct(row.pass_rate)}</td>
      <td>${row.total_llm_calls ?? "—"}</td>
    `;
    els.metricsBody.appendChild(tr);
  }
}

function renderHoldout(holdout) {
  if (!holdout) {
    els.holdoutBadge.textContent = "not run";
    els.holdoutBadge.className = "badge neutral";
    els.holdoutPanel.innerHTML =
      '<p class="muted">Run once at the end with playbook v3.</p>';
    return;
  }

  els.holdoutBadge.textContent = "complete";
  els.holdoutBadge.className = "badge complete";
  els.holdoutPanel.innerHTML = `
    <p class="value">${pct(holdout.pass_rate)}</p>
    <p class="muted">${holdout.bugs_passed} / ${holdout.bugs_total} hold-out bugs passed</p>
    <p class="muted">Playbook ${holdout.playbook_version} · ${holdout.total_llm_calls ?? 0} LLM calls</p>
  `;
}

function renderAttempts(active) {
  const attempts = active?.recent_attempts || [];
  els.attemptsCount.textContent = `${attempts.length} events`;
  els.attemptFeed.innerHTML = "";

  if (!attempts.length) {
    els.attemptFeed.innerHTML =
      '<p class="muted">No trajectory files yet for the active iteration.</p>';
    return;
  }

  for (const row of attempts) {
    const div = document.createElement("div");
    div.className = `attempt-row ${row.accepted ? "accepted" : "rejected"}`;
    div.innerHTML = `
      <div class="attempt-bug">${row.bug_id}</div>
      <div class="attempt-notes">${row.notes || "No verdict notes"}</div>
      <div>${row.accepted ? "PASS" : "FAIL"} · attempt ${row.attempt}</div>
    `;
    els.attemptFeed.appendChild(div);
  }
}

function renderRunJob(state) {
  const job = state.run_job || { status: "idle" };
  const pipelineRunning = state.active_iteration?.status === "running";
  const running = job.status === "running" || pipelineRunning;

  els.runJobStatus.textContent = running ? "running" : job.status;
  els.runJobStatus.className = `badge ${running ? "running" : statusClass(job.status)}`;
  els.runButton.disabled = running || submittingRun;

  if (!runFormTouched && state.suggested_start_iteration != null) {
    els.runStartIteration.value = String(state.suggested_start_iteration);
  }

  if (job.command?.length) {
    const cmd = job.command.join(" ");
    if (job.status === "running") {
      els.runMessage.textContent = `Running: ${cmd}`;
    } else if (job.status === "completed") {
      els.runMessage.textContent = `Finished (exit ${job.exit_code}): ${cmd}`;
    } else if (job.status === "failed") {
      els.runMessage.textContent = `Failed (exit ${job.exit_code}): ${cmd}`;
    }
  }

  const tail = job.log_tail || [];
  els.runLog.textContent = tail.length ? tail.join("\n") : "Runner output will appear here.";
}

function renderState(state) {
  renderActive(state.active_iteration);
  renderPipeline(state.pipeline_steps);
  renderMetrics(state.metrics);
  renderHoldout(state.holdout);
  renderAttempts(state.active_iteration);
  renderRunJob(state);
  drawChart(state.metrics, state.holdout);

  if (state.chart_available && state.chart_path) {
    els.chartFallback.src = `/${state.chart_path}?t=${Date.now()}`;
    els.chartFallback.classList.remove("hidden");
    els.chartUpdated.textContent = "Static chart available";
  } else {
    els.chartFallback.classList.add("hidden");
    els.chartUpdated.textContent = "Live canvas chart";
  }

  els.lastUpdated.textContent = `Last updated ${new Date(state.updated_at).toLocaleTimeString()}`;
}

async function poll() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const state = await response.json();
    els.connectionStatus.textContent = "Live";
    els.connectionStatus.style.color = "var(--good)";
    renderState(state);
  } catch (error) {
    els.connectionStatus.textContent = "Offline";
    els.connectionStatus.style.color = "var(--bad)";
    els.activeDetail.textContent = `Dashboard API unreachable: ${error.message}`;
  }
}

poll();
setInterval(poll, POLL_MS);

els.runStartIteration.addEventListener("input", () => {
  runFormTouched = true;
});

els.runForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  submittingRun = true;
  els.runButton.disabled = true;
  els.runMessage.textContent = "Starting benchmark run…";

  const payload = {
    start_iteration: Number(els.runStartIteration.value),
    iterations: Number(els.runIterations.value),
    creator: els.runCreator.value,
    no_chart: els.runNoChart.checked,
  };

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok || !result.ok) {
      throw new Error(result.error || `HTTP ${response.status}`);
    }
    els.runMessage.textContent = "Benchmark started. Watching trajectories…";
    await poll();
  } catch (error) {
    els.runMessage.textContent = `Could not start run: ${error.message}`;
  } finally {
    submittingRun = false;
    els.runButton.disabled = false;
  }
});

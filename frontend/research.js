const API = "/api/v1/research";

const state = {
  overview: null,
  advanced: null,
  branches: [],
  knowledge: [],
  pollination: [],
  graph: null,
  council: [],
  evolution: null,
  schedulerRuns: [],
};

function e(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

async function request(path, init = {}) {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body));
  }
  return response.json();
}

function toast(message, error = false) {
  const node = document.querySelector("#toast");
  node.textContent = message;
  node.className = error ? "show error" : "show";
  window.setTimeout(() => { node.className = ""; }, 2600);
}

function statusLabel(value) {
  return {
    proposed: "Proposed", active: "Active", blocked: "Blocked", under_review: "Under review",
    verified: "Verified", rejected: "Rejected", archived: "Archived",
  }[value] ?? value;
}

function metric(label, value, note) {
  return `<article><span>${e(label)}</span><strong>${e(value)}</strong><small>${e(note)}</small></article>`;
}

function renderOverview() {
  const data = state.overview ?? {};
  document.querySelector("#overview").innerHTML = [
    metric("Research branches", data.branches_total ?? 0, `${data.active ?? 0} active`),
    metric("Blocked", data.blocked ?? 0, "negative results preserved"),
    metric("Under review", data.under_review ?? 0, "critic / verifier gate"),
    metric("Verified", data.verified ?? 0, "passed full gate"),
    metric("Accepted knowledge", data.accepted_knowledge ?? 0, "versioned provenance"),
    metric("Cross-pollination", data.cross_pollination_events ?? 0, "research transfers"),
  ].join("");
}

function renderAdvanced() {
  const data = state.advanced ?? {};
  document.querySelector("#advanced-overview").innerHTML = [
    metric("DAG nodes", data.graph_nodes ?? 0, `${data.graph_edges ?? 0} explicit edges`),
    metric("Council sessions", data.council_sessions ?? 0, `${data.council_passed ?? 0} passed`),
    metric("Challenged", data.knowledge_challenged ?? 0, "accepted knowledge under attack"),
    metric("Revised", data.knowledge_revised ?? 0, "historical version retained"),
    metric("Revoked", data.knowledge_revoked ?? 0, "knowledge withdrawn"),
    metric("Scheduler", data.scheduler_runs ?? 0, `${data.scheduler_actions ?? 0} decisions`),
  ].join("");
  document.querySelector("#graph-count").textContent = `${data.graph_nodes ?? 0} nodes / ${data.graph_edges ?? 0} edges`;
}

function compactList(items, empty, renderItem) {
  if (!items?.length) return `<span class="empty-inline">${e(empty)}</span>`;
  return items.slice(-3).map(renderItem).join("");
}

function branchCard(branch) {
  const unresolved = branch.counterexamples.filter(item => !item.resolved).length;
  const passedExperiments = branch.experiments.filter(item => item.status === "passed").length;
  return `<article class="branch-card">
    <header><div><span class="status status--${e(branch.status)}">${e(statusLabel(branch.status))}</span><small>${e(branch.id)}</small></div><button data-gate="${e(branch.id)}">Run gate →</button></header>
    <h3>${e(branch.title)}</h3>
    <dl>
      <div><dt>Question</dt><dd>${e(branch.question)}</dd></div>
      <div><dt>Hypothesis</dt><dd>${e(branch.hypothesis)}</dd></div>
      <div><dt>Evidence</dt><dd>${compactList(branch.evidence, "No evidence yet", item => `<span class="token">${e(item.kind)} · ${e(item.title)}</span>`)}</dd></div>
      <div><dt>Counterexample</dt><dd>${branch.counterexamples.length ? `<b class="${unresolved ? "danger-text" : "good-text"}">${unresolved} unresolved / ${branch.counterexamples.length} total</b>` : '<span class="empty-inline">No counterexample recorded</span>'}</dd></div>
      <div><dt>Experiment</dt><dd>${branch.experiments.length ? `${passedExperiments} passed / ${branch.experiments.length} total` : '<span class="empty-inline">No experiment recorded</span>'}</dd></div>
      <div><dt>Result</dt><dd>${branch.result ? e(branch.result) : '<span class="empty-inline">Pending</span>'}</dd></div>
      <div><dt>Status</dt><dd>${e(statusLabel(branch.status))}</dd></div>
    </dl>
    <footer><span>${branch.tags.map(tag => `#${e(tag)}`).join(" ") || "untagged"}</span><small>updated ${new Date(branch.updated_at).toLocaleString("zh-CN")}</small></footer>
  </article>`;
}

function renderBranches() {
  const root = document.querySelector("#branches");
  root.innerHTML = state.branches.length
    ? state.branches.map(branchCard).join("")
    : '<div class="empty-state">尚无 research branch。至少这次空白是诚实的。</div>';
  document.querySelectorAll("[data-gate]").forEach(button => button.addEventListener("click", () => openGate(button.dataset.gate)));
}

function renderPollination() {
  document.querySelector("#pollination-count").textContent = `${state.pollination.length} events`;
  document.querySelector("#pollination-feed").innerHTML = state.pollination.length ? state.pollination.slice(0, 8).map(item => `
    <section class="feed-item">
      <header><b>${e(item.source_branch_id)}</b><small>${new Date(item.generated_at).toLocaleString("zh-CN")}</small></header>
      ${item.best_lemma ? `<p><span>Best lemma</span>${e(item.best_lemma)}</p>` : ""}
      ${item.best_negative_result ? `<p><span>Best negative result</span>${e(item.best_negative_result)}</p>` : ""}
      ${item.unresolved_obstacle ? `<p><span>Unresolved obstacle</span>${e(item.unresolved_obstacle)}</p>` : ""}
      ${item.useful_tool ? `<p><span>Useful tool</span>${e(item.useful_tool)}</p>` : ""}
      <footer>→ ${item.target_branch_ids.map(e).join(", ")}</footer>
    </section>`).join("") : '<div class="empty-state small">还没有 cross-pollination event。</div>';
}

function renderKnowledge() {
  document.querySelector("#knowledge-count").textContent = `${state.knowledge.length} accepted`;
  document.querySelector("#knowledge-ledger").innerHTML = state.knowledge.length ? state.knowledge.map(item => `
    <section class="feed-item accepted-item">
      <header><b>${e(item.title)}</b><small>${new Date(item.accepted_at).toLocaleString("zh-CN")}</small></header>
      <p>${e(item.statement)}</p>
      <dl><div><dt>Evidence</dt><dd>${item.evidence_ids.map(e).join(", ")}</dd></div><div><dt>Critic</dt><dd>${e(item.critic_review_id)}</dd></div><div><dt>Verifier</dt><dd>${e(item.verifier_review_id)}</dd></div></dl>
    </section>`).join("") : '<div class="empty-state small">暂无 Accepted Knowledge。Gate 没通过就不装作通过，这点已经超过不少仪表盘了。</div>';
}

function renderCouncil() {
  const sessions = state.council ?? [];
  const scheduler = state.schedulerRuns?.[0];
  const councilHtml = sessions.slice(0, 5).map(item => `
    <section class="feed-item">
      <header><b>${e(item.branch_id)}</b><small>${e(item.status)}</small></header>
      <p><span>Council</span>${item.contributions.length}/5 roles · ${e(item.final_reason || "review in progress")}</p>
    </section>`).join("");
  const schedulerHtml = scheduler ? `
    <section class="feed-item">
      <header><b>Latest scheduler tick</b><small>${new Date(scheduler.created_at).toLocaleString("zh-CN")}</small></header>
      ${scheduler.decisions.map(item => `<p><span>${e(item.action)}</span>${e(item.reason)}${item.target_branch_id ? ` → ${e(item.target_branch_id)}` : ""}</p>`).join("")}
    </section>` : "";
  document.querySelector("#council-feed").innerHTML = councilHtml + schedulerHtml || '<div class="empty-state small">暂无 Council / Scheduler 记录。</div>';
}

function renderEvolution() {
  const snapshot = state.evolution ?? { versions: [], challenges: [], events: [] };
  document.querySelector("#evolution-count").textContent = `${snapshot.versions.length} versions / ${snapshot.challenges.length} challenges`;
  document.querySelector("#evolution-feed").innerHTML = snapshot.versions.length ? snapshot.versions.slice().reverse().slice(0, 8).map(item => `
    <section class="feed-item ${item.state === "accepted" ? "accepted-item" : ""}">
      <header><b>${e(item.title)} · v${e(item.version)}</b><small>${e(item.state)}</small></header>
      <p>${e(item.statement)}</p>
      <footer>${e(item.id)}${item.successor_id ? ` → ${e(item.successor_id)}` : ""}</footer>
    </section>`).join("") : '<div class="empty-state small">还没有知识版本链。</div>';
}

async function openGate(branchId) {
  try {
    const report = await request(`/branches/${encodeURIComponent(branchId)}/gate`);
    const branch = state.branches.find(item => item.id === branchId);
    document.querySelector("#gate-title").textContent = branch?.title ?? branchId;
    document.querySelector("#gate-content").innerHTML = `
      <div class="gate-summary ${report.accepted ? "pass" : "fail"}"><span>${report.accepted ? "ACCEPTABLE" : "BLOCKED"}</span><b>Stage: ${e(report.stage)}</b><small>${report.blockers.length ? `${report.blockers.length} blocker(s)` : "All deterministic checks passed"}</small></div>
      <div class="gate-checks">${report.checks.map(check => `<div class="gate-check ${check.passed ? "pass" : "fail"}"><span>${check.passed ? "✓" : "×"}</span><div><b>${e(check.name)}</b><small>${e(check.detail)}</small></div></div>`).join("")}</div>`;
    document.querySelector("#gate-dialog").showModal();
  } catch (error) {
    toast(error.message, true);
  }
}

async function load() {
  try {
    const [overview, advanced, branches, knowledge, pollination, graph, council, evolution, schedulerRuns] = await Promise.all([
      request("/overview"),
      request("/system-overview"),
      request("/branches"),
      request("/accepted-knowledge"),
      request("/cross-pollination"),
      request("/evidence-graph"),
      request("/council"),
      request("/knowledge-evolution"),
      request("/scheduler/runs"),
    ]);
    Object.assign(state, { overview, advanced, branches, knowledge, pollination, graph, council, evolution, schedulerRuns });
    renderOverview();
    renderAdvanced();
    renderBranches();
    renderPollination();
    renderKnowledge();
    renderCouncil();
    renderEvolution();
  } catch (error) {
    toast(`Research API unavailable: ${error.message}`, true);
  }
}

document.querySelector("#run-scheduler").addEventListener("click", async () => {
  try {
    const run = await request("/scheduler/tick", { method: "POST", body: JSON.stringify({ dry_run: false }) });
    const actions = run.decisions.map(item => item.action).join(", ");
    toast(`Scheduler completed: ${actions}`);
    await load();
  } catch (error) {
    toast(error.message, true);
  }
});
document.querySelector("#new-branch-button").addEventListener("click", () => document.querySelector("#branch-form").classList.remove("hidden"));
document.querySelector("#cancel-branch").addEventListener("click", () => document.querySelector("#branch-form").classList.add("hidden"));
document.querySelector("#close-gate").addEventListener("click", () => document.querySelector("#gate-dialog").close());
document.querySelector("#create-branch-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    await request("/branches", {
      method: "POST",
      body: JSON.stringify({
        title: String(form.get("title")),
        question: String(form.get("question")),
        hypothesis: String(form.get("hypothesis")),
        owner: String(form.get("owner") || "researcher"),
        tags: [],
      }),
    });
    event.currentTarget.reset();
    document.querySelector("#branch-form").classList.add("hidden");
    toast("Research branch created.");
    await load();
  } catch (error) {
    toast(error.message, true);
  }
});

load();

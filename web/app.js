/* PulseGrid dashboard — vanilla JS, no build step. */
const $ = (s) => document.querySelector(s);
let token = localStorage.getItem("pg_token") || "";
let mode = "simple";
let recommendedPreset = null;

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(opts.headers || {}) },
  });
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2500); }
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

function showApp() { $("#loginView").hidden = true; $("#appView").hidden = false; refresh(); }
function showLogin() { $("#loginView").hidden = false; $("#appView").hidden = true; }

async function refresh() {
  try {
    const d = await api("/api/dashboard");
    mode = d.mode || "simple";
    $("#modeLabel").textContent = mode === "expert" ? "Expert Mode" : "Simple Mode";
    $("#modeToggle").textContent = mode === "expert" ? "Simple Mode" : "Expert Mode";
    $("#expertPanel").hidden = mode !== "expert";
    const s = d.summary;
    $("#summaryCards").innerHTML = [
      ["Nodes", s.total_nodes], ["Healthy", s.healthy_nodes],
      ["Users", s.total_users], ["Active", s.active_users],
      ["Traffic", s.total_traffic_human], ["Preset", d.active_preset],
    ].map(([l, n]) => `<div class="card"><div class="num">${esc(n)}</div><div class="lbl">${esc(l)}</div></div>`).join("");
    renderNodes(d.nodes); renderUsers(d.users); renderTraffic(d.traffic, d.alerts);
    renderPresets(d.active_preset);
  } catch (e) { toast(e.message); }
}

async function renderPresets(active) {
  const list = await api("/api/presets");
  $("#presetGrid").innerHTML = list.map((p) => `
    <div class="preset ${p.id === active ? "active" : ""}" data-id="${esc(p.id)}">
      <h3>${esc(p.name)}</h3><p>${esc(p.description)}</p>
      <span class="tag">${esc(p.tagline)}</span><br>
      <button class="btn small primary" style="margin-top:8px">Apply</button>
    </div>`).join("");
  document.querySelectorAll(".preset").forEach((el) => {
    el.addEventListener("click", async () => {
      const r = await api("/api/presets/apply", { method: "POST", body: JSON.stringify({ preset: el.dataset.id }) });
      toast(`Applied: ${r.name}`); refresh();
    });
  });
}

function renderNodes(nodes) {
  $("#nodeList").innerHTML = nodes.length ? nodes.map((n) => `
    <div class="item"><div><b>${esc(n.name)}</b> <span class="badge ${esc(n.verdict)}">${esc(n.verdict)} ${n.health_score}</span>
      <div class="meta">${esc(n.host)}:${esc(n.port)} · ${esc(n.protocol)}/${esc(n.transport)} · ${n.latency_ms}ms · loss ${n.loss_pct}%</div></div>
      <div class="actions"><button class="btn small" data-del-node="${esc(n.id)}">Delete</button></div></div>`).join("")
    : '<p class="muted">No nodes yet. Add one above.</p>';
  document.querySelectorAll("[data-del-node]").forEach((b) => b.addEventListener("click", async () => { await api(`/api/nodes/${b.dataset.delNode}`, { method: "DELETE" }); refresh(); }));
}

function renderUsers(users) {
  $("#userList").innerHTML = users.length ? users.map((u) => `
    <div class="item"><div><b>${esc(u.name)}</b> <span class="badge ${u.status === "active" ? "healthy" : "unhealthy"}">${esc(u.status)}</span>
      <div class="meta">used ${esc(u.used_human)} / ${esc(u.quota_human)} · ${u.days_left == null ? "no expiry" : u.days_left + "d left"}</div>
      <div class="meta" style="word-break:break-all">sub: /api/subscription/${esc(u.uuid)}?format=base64</div></div>
      <div class="actions">
        <button class="btn small" data-copy-sub="${esc(u.uuid)}">Copy sub</button>
        <button class="btn small" data-del-user="${esc(u.id)}">Delete</button></div></div>`).join("")
    : '<p class="muted">No users yet. Add one above — copy the subscription link and you are done.</p>';
  document.querySelectorAll("[data-copy-sub]").forEach((b) => b.addEventListener("click", async () => {
    const url = `${location.origin}/api/subscription/${b.dataset.copySub}?format=base64`;
    try {
      if (!navigator.clipboard) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(url); toast("Subscription link copied");
    } catch {
      window.prompt("Copy your private subscription URL:", url);
    }
  }));
  document.querySelectorAll("[data-del-user]").forEach((b) => b.addEventListener("click", async () => { await api(`/api/users/${b.dataset.delUser}`, { method: "DELETE" }); refresh(); }));
}

function renderTraffic(t, alerts) {
  $("#trafficBox").innerHTML = `<p>Up <b>${esc(t.up_bytes)}</b> B · Down <b>${esc(t.down_bytes)}</b> B · Total <b>${esc(t.total_bytes)}</b> B · Events ${esc(t.events)}</p>`;
  $("#alertList").innerHTML = alerts.length ? alerts.map((a) => `<div class="item"><span>[${esc(a.level)}] ${esc(a.message)}</span></div>`).join("") : '<p class="muted">No alerts.</p>';
}

async function runDoctor() {
  const host = $("#docHost").value.trim() || "127.0.0.1";
  const port = parseInt($("#docPort").value || "443", 10);
  $("#doctorPanel").hidden = false;
  $("#doctorSummary").textContent = "Running diagnostics…";
  const r = await api("/api/doctor/run", { method: "POST", body: JSON.stringify({ host, port }) });
  recommendedPreset = r.recommended_preset;
  $("#doctorVerdict").textContent = `${r.verdict} · ${r.score}/100`;
  $("#doctorVerdict").className = `badge ${r.verdict}`;
  $("#doctorSummary").textContent = r.summary;
  $("#doctorFindings").innerHTML = r.findings.map((f) => `<li>${esc(f)}</li>`).join("");
  $("#doctorMeter").style.width = `${r.score}%`;
  $("#doctorScore").textContent = r.score;
  $("#applyRecBtn").hidden = false;
  $("#applyRecBtn").textContent = `Apply recommended: ${recommendedPreset}`;
}

// Events
$("#loginBtn").addEventListener("click", async () => {
  token = $("#tokenInput").value.trim();
  try { await api("/api/dashboard"); localStorage.setItem("pg_token", token); showApp(); } catch { toast("Invalid token"); }
});
$("#logoutBtn").addEventListener("click", () => { localStorage.removeItem("pg_token"); token = ""; showLogin(); });
$("#doctorBtn").addEventListener("click", () => { $("#doctorPanel").hidden = false; runDoctor(); });
$("#runDoctorBtn").addEventListener("click", runDoctor);
$("#applyRecBtn").addEventListener("click", async () => {
  if (!recommendedPreset) return;
  await api("/api/presets/apply", { method: "POST", body: JSON.stringify({ preset: recommendedPreset }) });
  toast("Recommended preset applied"); refresh();
});
$("#modeToggle").addEventListener("click", async () => {
  const next = mode === "expert" ? "simple" : "expert";
  await api("/api/presets/apply", { method: "POST", body: JSON.stringify({ preset: "balanced", mode: next }) });
  refresh();
});
$("#applyExpertBtn").addEventListener("click", async () => {
  await api("/api/presets/apply", { method: "POST", body: JSON.stringify({
    preset: "balanced",
    overrides: { transport: $("#expTransport").value, security: $("#expSecurity").value, mux: { concurrency: parseInt($("#expMux").value, 10) } },
  }) });
  toast("Expert overrides applied"); refresh();
});
$("#addNodeBtn").addEventListener("click", async () => {
  await api("/api/nodes", { method: "POST", body: JSON.stringify({ name: $("#nodeName").value || "node", host: $("#nodeHost").value || "127.0.0.1", port: parseInt($("#nodePort").value || "443", 10) }) });
  toast("Node added"); refresh();
});
$("#checkAllBtn").addEventListener("click", async () => { toast("Checking…"); await api("/api/doctor/check-all", { method: "POST", body: "{}" }); toast("Health check complete"); refresh(); });
$("#addUserBtn").addEventListener("click", async () => {
  await api("/api/users", { method: "POST", body: JSON.stringify({ name: $("#userName").value || "user", quota_gb: parseFloat($("#userQuota").value || "0"), days: parseFloat($("#userDays").value || "0") }) });
  toast("User added — copy the subscription link"); refresh();
});

if (token) { api("/api/dashboard").then(showApp).catch(showLogin); } else { showLogin(); }

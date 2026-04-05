"""Dedicated dashboard page — full memory graph, conflict management, fact browser."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route


def _render_dashboard() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard — Engram</title>
  <meta name="description" content="View and manage your team's shared memory — facts, conflicts, agents, and lineage.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.29.2/cytoscape.min.js"></script>
  <style>
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
    :root {
      --bg: #050a0e; --bg2: #0a1118; --bg-card: rgba(13,23,33,0.7);
      --border: rgba(52,211,153,0.08); --border-glow: rgba(52,211,153,0.2);
      --em4: #34d399; --em5: #10b981; --em6: #059669; --em7: #047857;
      --t1: #f0fdf4; --t2: rgba(209,250,229,0.6); --tm: rgba(167,243,208,0.35);
    }
    html { scroll-behavior: smooth; }
    body {
      font-family: 'Inter', -apple-system, sans-serif;
      line-height: 1.6; color: var(--t1); background: var(--bg);
      min-height: 100vh; -webkit-font-smoothing: antialiased;
    }
    .container { max-width: 1100px; margin: 0 auto; padding: 0 28px; }

    /* Header */
    header {
      padding: 16px 0; background: rgba(5,10,14,0.8);
      backdrop-filter: blur(20px); border-bottom: 1px solid var(--border);
      position: sticky; top: 0; z-index: 100;
    }
    .header-content { display: flex; justify-content: space-between; align-items: center; }
    .logo {
      font-size: 20px; font-weight: 700; color: var(--em4);
      text-decoration: none; letter-spacing: -0.03em;
      display: flex; align-items: center; gap: 8px;
    }
    .logo-dot {
      width: 6px; height: 6px; border-radius: 50%; background: var(--em4);
      box-shadow: 0 0 10px var(--em4);
    }
    .back-link { color: var(--t2); text-decoration: none; font-size: 13px; font-weight: 500; transition: color 0.2s; }
    .back-link:hover { color: var(--em4); }

    /* Auth bar */
    .auth-bar {
      padding: 32px 0; border-bottom: 1px solid var(--border);
    }
    .auth-form { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .auth-input {
      flex: 1; min-width: 200px; padding: 12px 16px;
      background: rgba(0,0,0,0.3); border: 1px solid var(--border);
      border-radius: 10px; font-size: 14px; font-family: inherit;
      color: var(--t1); transition: border-color 0.2s;
    }
    .auth-input:focus { outline: none; border-color: var(--em5); box-shadow: 0 0 0 3px rgba(52,211,153,0.1); }
    .auth-input::placeholder { color: var(--tm); }
    .auth-btn {
      padding: 12px 24px; background: linear-gradient(135deg, var(--em6), var(--em7));
      color: white; border: none; border-radius: 10px; font-size: 14px;
      font-weight: 600; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s;
      box-shadow: 0 2px 12px rgba(5,150,105,0.25);
    }
    .auth-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(5,150,105,0.35); }
    .auth-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
    .auth-error { color: #f87171; font-size: 13px; margin-top: 10px; display: none; }
    .auth-loading { color: var(--em4); font-size: 13px; margin-top: 10px; display: none; }

    /* Dashboard content — hidden until authenticated */
    #dashboard { display: none; }

    /* Stats row */
    .stats-row { display: flex; gap: 16px; padding: 28px 0; flex-wrap: wrap; }
    .stat-card {
      flex: 1; min-width: 140px; padding: 20px 24px;
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 14px; text-align: center;
    }
    .stat-num { font-size: 36px; font-weight: 800; color: var(--em4); }
    .stat-label { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--tm); margin-top: 4px; }

    /* Tabs */
    .tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--border); margin-bottom: 0; }
    .tab-btn {
      padding: 12px 24px; background: none; border: none; border-bottom: 2px solid transparent;
      color: var(--tm); font-size: 14px; font-weight: 600; cursor: pointer;
      font-family: inherit; transition: color 0.2s, border-color 0.2s;
    }
    .tab-btn.active { color: var(--em4); border-bottom-color: var(--em4); }
    .tab-btn:hover:not(.active) { color: var(--t2); }
    .tab-panel { display: none; padding: 24px 0; }
    .tab-panel.active { display: block; }

    /* Graph tab */
    .graph-controls { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
    .graph-filter {
      flex: 1; padding: 10px 14px; background: rgba(0,0,0,0.3);
      border: 1px solid var(--border); border-radius: 10px;
      font-size: 13px; font-family: inherit; color: var(--t1);
    }
    .graph-filter:focus { outline: none; border-color: var(--em5); }
    .graph-filter::placeholder { color: var(--tm); }
    #cy { width: 100%; height: 560px; border-radius: 16px; border: 1px solid var(--border); background: rgba(0,0,0,0.2); }
    .graph-legend { display: flex; gap: 20px; margin-top: 12px; flex-wrap: wrap; }
    .legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--t2); }
    .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
    .node-detail {
      display: none; margin-top: 16px; padding: 20px; background: rgba(0,0,0,0.3);
      border-radius: 14px; border-left: 3px solid var(--em5);
    }
    .node-detail h4 { font-size: 13px; font-weight: 600; color: var(--em4); margin-bottom: 6px; }
    .node-detail p { font-size: 14px; color: var(--t2); line-height: 1.6; margin: 0; }
    .node-detail .meta { font-size: 12px; color: var(--tm); margin-top: 8px; }

    /* Conflicts tab */
    .conflict-list { display: flex; flex-direction: column; gap: 12px; }
    .conflict-card {
      padding: 20px 24px; background: var(--bg-card);
      border: 1px solid var(--border); border-radius: 14px;
      transition: border-color 0.3s;
    }
    .conflict-card:hover { border-color: var(--border-glow); }
    .conflict-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .conflict-severity {
      font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
      padding: 3px 10px; border-radius: 6px;
    }
    .severity-high { background: rgba(239,68,68,0.15); color: #f87171; }
    .severity-medium { background: rgba(245,158,11,0.15); color: #fbbf24; }
    .severity-low { background: rgba(52,211,153,0.15); color: var(--em4); }
    .conflict-status {
      font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
      padding: 3px 10px; border-radius: 6px;
    }
    .status-open { background: rgba(239,68,68,0.1); color: #f87171; }
    .status-resolved { background: rgba(52,211,153,0.1); color: var(--em4); }
    .conflict-explanation { font-size: 14px; color: var(--t2); line-height: 1.6; margin-bottom: 12px; }
    .conflict-facts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .conflict-fact {
      padding: 14px; background: rgba(0,0,0,0.25); border-radius: 10px;
      font-size: 13px; color: var(--t2); line-height: 1.5;
    }
    .conflict-fact-label { font-size: 11px; font-weight: 600; color: var(--tm); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.06em; }
    .conflict-date { font-size: 12px; color: var(--tm); margin-top: 8px; }
    .empty-state { text-align: center; padding: 60px 20px; color: var(--tm); font-size: 15px; }

    /* Facts tab */
    .facts-toolbar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
    .facts-search {
      flex: 1; min-width: 200px; padding: 10px 14px;
      background: rgba(0,0,0,0.3); border: 1px solid var(--border);
      border-radius: 10px; font-size: 13px; font-family: inherit; color: var(--t1);
    }
    .facts-search:focus { outline: none; border-color: var(--em5); }
    .facts-search::placeholder { color: var(--tm); }
    .filter-btn {
      padding: 8px 16px; background: rgba(255,255,255,0.04);
      border: 1px solid var(--border); border-radius: 8px;
      color: var(--tm); font-size: 12px; font-weight: 600; cursor: pointer;
      font-family: inherit; transition: all 0.2s;
    }
    .filter-btn.active { background: rgba(52,211,153,0.1); border-color: var(--border-glow); color: var(--em4); }
    .filter-btn:hover:not(.active) { color: var(--t2); border-color: var(--border-glow); }

    .fact-table { width: 100%; }
    .fact-row {
      display: grid; grid-template-columns: 1fr 120px 80px 100px;
      gap: 16px; padding: 14px 0; border-bottom: 1px solid var(--border);
      align-items: center; font-size: 13px;
    }
    .fact-row:last-child { border-bottom: none; }
    .fact-row-header { color: var(--tm); font-weight: 600; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; }
    .fact-content { color: var(--t2); line-height: 1.5; }
    .fact-scope {
      font-family: 'JetBrains Mono', monospace; font-size: 12px;
      color: var(--em4); background: rgba(52,211,153,0.08);
      padding: 2px 8px; border-radius: 4px; display: inline-block;
    }
    .fact-type { color: var(--tm); font-size: 12px; }
    .fact-date { color: var(--tm); font-size: 12px; }
    .fact-retired { opacity: 0.4; }

    /* Agents tab */
    .agents-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
    .agent-card {
      padding: 24px; background: var(--bg-card);
      border: 1px solid var(--border); border-radius: 14px;
    }
    .agent-id {
      font-family: 'JetBrains Mono', monospace; font-size: 13px;
      color: var(--em4); margin-bottom: 8px;
    }
    .agent-engineer { font-size: 14px; color: var(--t2); margin-bottom: 12px; }
    .agent-stats { display: flex; gap: 16px; }
    .agent-stat-label { font-size: 11px; color: var(--tm); text-transform: uppercase; letter-spacing: 0.05em; }
    .agent-stat-val { font-size: 18px; font-weight: 700; color: var(--t1); }

    @media (max-width: 768px) {
      .auth-form { flex-direction: column; }
      .stats-row { flex-direction: column; }
      .conflict-facts { grid-template-columns: 1fr; }
      .fact-row { grid-template-columns: 1fr; gap: 4px; }
      .fact-row-header { display: none; }
      #cy { height: 380px; }
    }
  </style>
</head>
<body>

<header>
  <div class="container">
    <div class="header-content">
      <a href="/" class="logo"><span class="logo-dot"></span>engram</a>
      <a href="/" class="back-link">&larr; Back to home</a>
    </div>
  </div>
</header>

<div class="container">
  <!-- Auth -->
  <div class="auth-bar">
    <div class="auth-form">
      <input class="auth-input" id="engram-id" placeholder="Workspace ID (ENG-XXXX-XXXX)" autocomplete="off" spellcheck="false" />
      <input class="auth-input" id="invite-key" placeholder="Invite key (ek_live_...)" autocomplete="off" spellcheck="false" type="password" />
      <button class="auth-btn" id="connect-btn" onclick="connect()">Connect</button>
    </div>
    <div class="auth-error" id="auth-error"></div>
    <div class="auth-loading" id="auth-loading">Connecting to workspace…</div>
  </div>

  <!-- Dashboard -->
  <div id="dashboard">
    <div class="stats-row" id="stats-row"></div>

    <div class="tabs">
      <button class="tab-btn active" onclick="switchTab('graph')">Graph</button>
      <button class="tab-btn" onclick="switchTab('conflicts')">Conflicts <span id="conflict-badge"></span></button>
      <button class="tab-btn" onclick="switchTab('facts')">Facts</button>
      <button class="tab-btn" onclick="switchTab('agents')">Agents</button>
    </div>

    <!-- Graph -->
    <div class="tab-panel active" id="panel-graph">
      <div class="graph-controls">
        <input class="graph-filter" id="graph-filter" placeholder="Filter by scope or content…" oninput="filterGraph(this.value)" />
      </div>
      <div id="cy"></div>
      <div class="graph-legend">
        <span class="legend-item"><span class="legend-dot" style="background:var(--em5)"></span>Active</span>
        <span class="legend-item"><span class="legend-dot" style="background:#64748b"></span>Retired</span>
        <span class="legend-item"><span class="legend-dot" style="background:#f59e0b"></span>Conflict</span>
      </div>
      <div class="node-detail" id="node-detail">
        <h4 id="nd-scope"></h4>
        <p id="nd-content"></p>
        <div class="meta" id="nd-meta"></div>
      </div>
    </div>

    <!-- Conflicts -->
    <div class="tab-panel" id="panel-conflicts">
      <div class="conflict-list" id="conflict-list"></div>
    </div>

    <!-- Facts -->
    <div class="tab-panel" id="panel-facts">
      <div class="facts-toolbar">
        <input class="facts-search" id="facts-search" placeholder="Search facts…" oninput="filterFacts()" />
        <button class="filter-btn active" onclick="setFactFilter('all', this)">All</button>
        <button class="filter-btn" onclick="setFactFilter('active', this)">Active</button>
        <button class="filter-btn" onclick="setFactFilter('retired', this)">Retired</button>
      </div>
      <div class="fact-table">
        <div class="fact-row fact-row-header">
          <div>Content</div><div>Scope</div><div>Type</div><div>Date</div>
        </div>
        <div id="facts-list"></div>
      </div>
    </div>

    <!-- Agents -->
    <div class="tab-panel" id="panel-agents">
      <div class="agents-grid" id="agents-grid"></div>
    </div>
  </div>
</div>

<script>
let cy = null, DATA = null, factFilter = 'all';

// ── Connect ────────────────────────────────────────────────────────
async function connect() {
  const eid = document.getElementById('engram-id').value.trim();
  const key = document.getElementById('invite-key').value.trim();
  const err = document.getElementById('auth-error');
  const load = document.getElementById('auth-loading');
  const btn = document.getElementById('connect-btn');
  err.style.display = 'none';
  load.style.display = 'block';
  btn.disabled = true;
  try {
    const r = await fetch('/workspace/search', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({engram_id: eid, invite_key: key}),
    });
    const d = await r.json();
    if (!r.ok) { err.textContent = d.error || 'Auth failed'; err.style.display = 'block'; return; }
    DATA = d;
    render();
    document.getElementById('dashboard').style.display = 'block';
  } catch(e) {
    err.textContent = 'Connection error'; err.style.display = 'block';
  } finally { load.style.display = 'none'; btn.disabled = false; }
}

// ── Render all ─────────────────────────────────────────────────────
function render() {
  const {facts, conflicts, agents} = DATA;
  const active = facts.filter(f => !f.valid_until).length;
  const retired = facts.filter(f => f.valid_until).length;
  const openC = conflicts.filter(c => c.status === 'open').length;

  document.getElementById('stats-row').innerHTML = `
    <div class="stat-card"><div class="stat-num">${active}</div><div class="stat-label">Active facts</div></div>
    <div class="stat-card"><div class="stat-num">${retired}</div><div class="stat-label">Retired</div></div>
    <div class="stat-card"><div class="stat-num">${openC}</div><div class="stat-label">Open conflicts</div></div>
    <div class="stat-card"><div class="stat-num">${agents.length}</div><div class="stat-label">Agents</div></div>
  `;
  const badge = document.getElementById('conflict-badge');
  if (openC > 0) badge.textContent = '(' + openC + ')';

  renderGraph();
  renderConflicts();
  renderFacts();
  renderAgents();
}

// ── Graph ──────────────────────────────────────────────────────────
function renderGraph() {
  const {facts, conflicts} = DATA;
  const els = [];
  const sc = {}, PAL = ['#10b981','#06b6d4','#8b5cf6','#ec4899','#f59e0b','#22c55e','#3b82f6'];
  let pi = 0;
  const sColor = s => { if (!sc[s]) sc[s] = PAL[pi++ % PAL.length]; return sc[s]; };

  facts.forEach(f => {
    const ret = !!f.valid_until;
    els.push({data:{id:f.id, label:f.scope||'general', content:f.content, scope:f.scope,
      fact_type:f.fact_type, committed_at:f.committed_at, durability:f.durability, retired:ret,
      color: ret ? '#64748b' : sColor(f.scope||'general'),
      size: ret ? 18 : (f.confidence||0.9)*36+12}});
  });
  facts.filter(f=>f.supersedes_fact_id).forEach(f => {
    els.push({data:{id:'l-'+f.id, source:f.supersedes_fact_id, target:f.id, kind:'lineage'}});
  });
  conflicts.filter(c=>c.status==='open').forEach(c => {
    els.push({data:{id:'c-'+c.id, source:c.fact_a_id, target:c.fact_b_id, kind:'conflict'}});
  });

  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById('cy'), elements: els,
    style: [
      {selector:'node', style:{'background-color':'data(color)','label':'data(label)',
        'font-size':'10px','color':'#94a3b8','text-valign':'bottom','text-margin-y':'5px',
        'width':'data(size)','height':'data(size)','border-width':1.5,'border-color':'rgba(255,255,255,0.1)'}},
      {selector:'node[retired = true]', style:{'opacity':0.35,'border-style':'dashed'}},
      {selector:'edge[kind="lineage"]', style:{'line-color':'#10b981','target-arrow-color':'#10b981',
        'target-arrow-shape':'triangle','curve-style':'bezier','width':1,'opacity':0.4}},
      {selector:'edge[kind="conflict"]', style:{'line-color':'#ef4444','line-style':'dashed',
        'width':2,'opacity':0.7,'curve-style':'bezier'}},
      {selector:':selected', style:{'border-color':'#34d399','border-width':2.5}},
    ],
    layout:{name:DATA.facts.length<30?'cose':'random', animate:DATA.facts.length<80,
      randomize:false, nodeRepulsion:8000, idealEdgeLength:120, padding:24},
  });

  cy.on('tap','node', e => {
    const d = e.target.data();
    document.getElementById('nd-scope').textContent = (d.scope||'general')+' · '+(d.fact_type||'observation');
    document.getElementById('nd-content').textContent = d.content||'';
    const ts = d.committed_at ? new Date(d.committed_at).toLocaleString() : '';
    document.getElementById('nd-meta').textContent = (d.retired?'Retired':'Active')+' · '+(d.durability||'durable')+' · '+ts;
    document.getElementById('node-detail').style.display = 'block';
  });
  cy.on('tap', e => { if(e.target===cy) document.getElementById('node-detail').style.display='none'; });
}

function filterGraph(q) {
  if (!cy) return;
  q = q.toLowerCase();
  if (!q) { cy.elements().style('opacity',1); return; }
  cy.nodes().forEach(n => {
    const m = (n.data('content')||'').toLowerCase().includes(q)||(n.data('scope')||'').toLowerCase().includes(q);
    n.style('opacity', m?1:0.08);
  });
  cy.edges().style('opacity',0.03);
}

// ── Conflicts ──────────────────────────────────────────────────────
function renderConflicts() {
  const {conflicts, facts} = DATA;
  const el = document.getElementById('conflict-list');
  if (!conflicts.length) { el.innerHTML = '<div class="empty-state">No conflicts detected</div>'; return; }

  const factMap = {};
  facts.forEach(f => factMap[f.id] = f);

  // Sort: open first, then by date desc
  const sorted = [...conflicts].sort((a,b) => {
    if (a.status === 'open' && b.status !== 'open') return -1;
    if (a.status !== 'open' && b.status === 'open') return 1;
    return new Date(b.detected_at) - new Date(a.detected_at);
  });

  el.innerHTML = sorted.map(c => {
    const fa = factMap[c.fact_a_id], fb = factMap[c.fact_b_id];
    const sevClass = c.severity === 'high' ? 'severity-high' : c.severity === 'low' ? 'severity-low' : 'severity-medium';
    const statusClass = c.status === 'open' ? 'status-open' : 'status-resolved';
    return `<div class="conflict-card">
      <div class="conflict-header">
        <span class="conflict-severity ${sevClass}">${c.severity||'medium'}</span>
        <span class="conflict-status ${statusClass}">${c.status}</span>
      </div>
      ${c.explanation ? `<div class="conflict-explanation">${esc(c.explanation)}</div>` : ''}
      <div class="conflict-facts">
        <div class="conflict-fact">
          <div class="conflict-fact-label">Fact A · ${fa?esc(fa.scope):'unknown'}</div>
          ${fa ? esc(fa.content) : 'Fact not found'}
        </div>
        <div class="conflict-fact">
          <div class="conflict-fact-label">Fact B · ${fb?esc(fb.scope):'unknown'}</div>
          ${fb ? esc(fb.content) : 'Fact not found'}
        </div>
      </div>
      <div class="conflict-date">Detected ${c.detected_at ? new Date(c.detected_at).toLocaleString() : ''}</div>
    </div>`;
  }).join('');
}

// ── Facts ──────────────────────────────────────────────────────────
function renderFacts() {
  const el = document.getElementById('facts-list');
  const q = (document.getElementById('facts-search').value||'').toLowerCase();
  let list = DATA.facts;
  if (factFilter === 'active') list = list.filter(f => !f.valid_until);
  if (factFilter === 'retired') list = list.filter(f => f.valid_until);
  if (q) list = list.filter(f => (f.content||'').toLowerCase().includes(q)||(f.scope||'').toLowerCase().includes(q));

  if (!list.length) { el.innerHTML = '<div class="empty-state" style="padding:40px">No facts found</div>'; return; }
  el.innerHTML = list.map(f => {
    const ret = f.valid_until ? ' fact-retired' : '';
    const dt = f.committed_at ? new Date(f.committed_at).toLocaleDateString() : '';
    return `<div class="fact-row${ret}">
      <div class="fact-content">${esc(f.content)}</div>
      <div><span class="fact-scope">${esc(f.scope||'general')}</span></div>
      <div class="fact-type">${f.fact_type||'obs'}</div>
      <div class="fact-date">${dt}</div>
    </div>`;
  }).join('');
}

function filterFacts() { renderFacts(); }
function setFactFilter(f, btn) {
  factFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderFacts();
}

// ── Agents ─────────────────────────────────────────────────────────
function renderAgents() {
  const el = document.getElementById('agents-grid');
  if (!DATA.agents.length) { el.innerHTML = '<div class="empty-state">No agents registered</div>'; return; }
  el.innerHTML = DATA.agents.map(a => {
    const seen = a.last_seen ? new Date(a.last_seen).toLocaleDateString() : 'never';
    return `<div class="agent-card">
      <div class="agent-id">${esc(a.agent_id)}</div>
      <div class="agent-engineer">${a.engineer ? esc(a.engineer) : 'Anonymous'}</div>
      <div class="agent-stats">
        <div><div class="agent-stat-val">${a.total_commits||0}</div><div class="agent-stat-label">Commits</div></div>
        <div><div class="agent-stat-val" style="font-size:14px;">${seen}</div><div class="agent-stat-label">Last seen</div></div>
      </div>
    </div>`;
  }).join('');
}

// ── Tabs ───────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
  if (name === 'graph' && cy) cy.resize();
}

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// Enter key support
document.addEventListener('DOMContentLoaded', () => {
  ['engram-id','invite-key'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => { if(e.key==='Enter') connect(); });
  });
  // Check URL params
  const p = new URLSearchParams(window.location.search);
  if (p.get('id')) document.getElementById('engram-id').value = p.get('id');
  if (p.get('key')) { document.getElementById('invite-key').value = p.get('key'); connect(); }
});
</script>
</body>
</html>"""


async def dashboard(request: Request) -> HTMLResponse:
    return HTMLResponse(_render_dashboard())


app = Starlette(routes=[Route("/{path:path}", dashboard, methods=["GET"])])

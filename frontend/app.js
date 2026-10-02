/**
 * SentinelAI frontend
 * -------------------
 * Talks to the real API only. There is NO local simulation: if the API is unreachable the UI says so.
 * All server-provided text is HTML-escaped before it is rendered (party names are attacker-controlled).
 */

const CFG = window.SENTINEL_CONFIG || {};
const API_BASE = (CFG.apiBase || '').replace(/\/$/, '');

const state = {
    scenarios: [],
    request: null,        // full request of the selected scenario (history, network edges...)
    dirty: false,         // form edited after loading a scenario => custom request
    last: null,
    loading: false,
    jurisdictions: null,
};
const elements = {};
const $ = (id) => document.getElementById(id);

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
const flag = (cc) => (cc && cc.length === 2) ? String.fromCodePoint(...[...cc.toUpperCase()].map((c) => 127397 + c.charCodeAt(0))) : '';

const CATEGORY_COLORS = {
    SANCTIONS: '#ef4444', PEP: '#f97316', GEOGRAPHIC: '#eab308', BEHAVIORAL: '#3b82f6', NETWORK: '#a855f7',
    CRYPTO: '#14b8a6', TRADE: '#ec4899', CUSTOMER: '#64748b', INTEGRITY: '#f43f5e', AI_RESEARCH: '#22d3ee',
};

document.addEventListener('DOMContentLoaded', init);

async function init() {
    ['analyzeBtn', 'btnLoader', 'resultsPanel', 'mobileMenuBtn', 'mobileMenu', 'scenarioGrid', 'scenarioInfo'].forEach((id) => (elements[id] = $(id)));
    elements.navbar = document.querySelector('.navbar');
    document.querySelectorAll('[data-api-link]').forEach((a) => (a.href = `${API_BASE}${a.dataset.apiLink}` || a.dataset.apiLink));
    initNavigation();
    initForm();
    $('apiKey').value = safeStorage('get', 'sentinel_api_key') || '';
    await Promise.all([checkHealth(), loadReference()]);
}

function safeStorage(op, key, value) {
    try { return op === 'set' ? sessionStorage.setItem(key, value) : sessionStorage.getItem(key); } catch { return null; }
}

// ============================================
// API access
// ============================================
function headers(extra = {}) {
    const h = { 'Content-Type': 'application/json', Accept: 'application/json', ...extra };
    const key = $('apiKey').value.trim();
    if (key) h['X-API-Key'] = key;
    return h;
}

async function api(path, { method = 'GET', body, timeout = 30000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
        const res = await fetch(`${API_BASE}${path}`, { method, headers: headers(), body: body ? JSON.stringify(body) : undefined, signal: controller.signal });
        const text = await res.text();
        let data = null;
        try { data = text ? JSON.parse(text) : null; } catch { /* non-JSON error body */ }
        if (!res.ok) {
            const detail = data && (data.message || data.detail);
            const err = new Error(typeof detail === 'string' ? detail : `HTTP ${res.status}`);
            err.status = res.status;
            throw err;
        }
        return data;
    } finally { clearTimeout(timer); }
}

async function checkHealth() {
    const dot = document.querySelector('.status-dot'), text = document.querySelector('.status-text');
    try {
        const h = await api('/health', { timeout: 20000 });
        const d = h.dependencies || {};
        const list = d.sanctions_list || {};
        dot.className = 'status-dot online';
        text.textContent = `Online · ${list.synthetic_demo_data ? 'demo sanctions list' : list.source} · AI ${d.llm && d.llm.configured ? 'ready' : 'off'}${h.status === 'degraded' ? ' · database unavailable' : ''}`;
        $('enableAI').disabled = !(d.llm && d.llm.configured);
        $('enableAI').parentElement.title = $('enableAI').disabled ? 'No LLM API key configured on the server' : '';
    } catch (e) {
        dot.className = 'status-dot offline';
        text.textContent = 'Unreachable';
    }
}

async function loadReference() {
    try {
        const [j, scenarios] = await Promise.all([api('/api/v1/reference/jurisdictions'), api('/api/v1/reference/scenarios')]);
        state.jurisdictions = j;
        fillCountrySelect($('originCountry'), j.names, 'US');
        fillCountrySelect($('destCountry'), j.names, 'KY');
        state.scenarios = scenarios;
        renderScenarioButtons();
        const first = scenarios.find((s) => s.id === 'offshore-routing') || scenarios[0];
        if (first) applyScenario(first, false);
    } catch (e) {
        elements.scenarioGrid.innerHTML = `<span class="muted-note">Could not load reference data from the API (${esc(e.message)}).</span>`;
    }
}

function fillCountrySelect(sel, names, selected) {
    const entries = Object.entries(names).sort((a, b) => a[1].localeCompare(b[1]));
    sel.innerHTML = '<option value="">- none -</option>' + entries.map(([cc, n]) => `<option value="${esc(cc)}">${flag(cc)} ${esc(n)}</option>`).join('');
    sel.value = selected;
}

// ============================================
// Scenarios & form
// ============================================
function renderScenarioButtons() {
    elements.scenarioGrid.innerHTML = state.scenarios.map((s) => `
        <button class="scenario-btn" data-id="${esc(s.id)}" title="${esc(s.description)}">
            <span class="name">${esc(s.title)}</span>
            <span class="tag">${esc((s.regime || 'US_BSA').replace('_', ' · '))}</span>
        </button>`).join('');
    elements.scenarioGrid.querySelectorAll('.scenario-btn').forEach((btn) => btn.addEventListener('click', () => {
        const sc = state.scenarios.find((s) => s.id === btn.dataset.id);
        applyScenario(sc, true);
    }));
}

function applyScenario(sc, run) {
    state.request = JSON.parse(JSON.stringify(sc.request));
    state.dirty = false;
    const tx = sc.request.transaction, c = sc.request.customer;
    $('amount').value = tx.amount;
    $('currency').value = tx.currency || 'USD';
    $('originCountry').value = tx.origin_country || '';
    $('destCountry').value = tx.destination_country || '';
    $('transactionType').value = tx.transaction_type || 'WIRE_TRANSFER';
    $('regime').value = sc.request.regime || 'US_BSA';
    $('parties').value = (tx.parties || []).join(', ');
    $('customerName').value = c.name || '';
    $('customerType').value = c.customer_type || 'INDIVIDUAL';
    $('accountAge').value = c.account_age_days ?? '';
    $('hasDocs').checked = (tx.documents || []).length > 0;
    const hist = (c.transaction_history || []).length, net = (sc.request.network_transactions || []).length;
    elements.scenarioInfo.innerHTML = `<strong>${esc(sc.title)}</strong> - ${esc(sc.description)}` +
        `<div class="muted-note">${hist} prior transactions${net ? `, ${net} linked-network transfers` : ''} included. Editing a field switches to a custom request without them.</div>`;
    document.querySelectorAll('.scenario-btn').forEach((b) => b.classList.toggle('active', b.dataset.id === sc.id));
    if (run) analyze();
}

function initForm() {
    elements.analyzeBtn.addEventListener('click', analyze);
    ['amount', 'currency', 'originCountry', 'destCountry', 'transactionType', 'parties', 'customerName', 'customerType', 'accountAge', 'hasDocs'].forEach((id) =>
        $(id).addEventListener('input', () => {
            if (!state.dirty && state.request) {
                state.dirty = true;
                elements.scenarioInfo.innerHTML = '<strong>Custom transaction</strong><div class="muted-note">History and network details from the scenario are not included.</div>';
                document.querySelectorAll('.scenario-btn.active').forEach((b) => b.classList.remove('active'));
            }
        }));
    $('apiKey').addEventListener('change', () => { safeStorage('set', 'sentinel_api_key', $('apiKey').value.trim()); checkHealth(); });
}

function buildRequest() {
    let req;
    if (state.request && !state.dirty) {
        req = JSON.parse(JSON.stringify(state.request));
    } else {
        const parties = $('parties').value.split(',').map((p) => p.trim()).filter(Boolean);
        const age = $('accountAge').value;
        req = {
            transaction: {
                amount: parseFloat($('amount').value), currency: $('currency').value, transaction_type: $('transactionType').value,
                origin_country: $('originCountry').value || null, destination_country: $('destCountry').value || null,
                parties, documents: $('hasDocs').checked ? ['Supporting documents'] : [],
            },
            customer: { name: $('customerName').value.trim(), customer_type: $('customerType').value, account_age_days: age === '' ? null : parseInt(age, 10) },
        };
    }
    req.regime = $('regime').value;
    req.enable_llm_analysis = $('enableAI').checked && !$('enableAI').disabled;
    req.restrict_external_lookup = $('confidential').checked;
    return req;
}

// ============================================
// Analysis (SSE with plain-POST fallback)
// ============================================
async function analyze() {
    if (state.loading) return;
    const req = buildRequest();
    if (!(req.transaction.amount > 0) || !req.customer.name) { showNotification('Enter a positive amount and a customer name.', 'warning'); return; }
    setLoading(true);
    showProgress([]);
    try {
        let result;
        try {
            result = await streamAnalysis(req);
        } catch (e) {
            if (e.fatal) throw e;                      // server answered with an error - do not retry blindly
            result = await api('/api/v1/analyze', { method: 'POST', body: req, timeout: 120000 });
        }
        state.last = result;
        renderResult(result);
    } catch (e) {
        renderError(e);
    } finally { setLoading(false); }
}

async function streamAnalysis(req) {
    const res = await fetch(`${API_BASE}/api/v1/analyze/stream`, { method: 'POST', headers: headers({ Accept: 'text/event-stream' }), body: JSON.stringify(req) });
    if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const j = await res.json(); msg = j.message || j.detail || msg; } catch { /* ignore */ }
        const err = new Error(msg); err.fatal = true; err.status = res.status; throw err;
    }
    if (!res.body || !res.body.getReader) throw new Error('streaming unsupported');
    const reader = res.body.getReader(), decoder = new TextDecoder();
    let buffer = '', steps = [];
    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
            const chunk = buffer.slice(0, idx); buffer = buffer.slice(idx + 2);
            const line = chunk.split('\n').find((l) => l.startsWith('data: '));
            if (!line) continue;
            const evt = JSON.parse(line.slice(6));
            if (evt.type === 'progress') { steps.push(evt.step); showProgress(steps); }
            else if (evt.type === 'result') return evt.result;
            else if (evt.type === 'error') { const err = new Error(`${evt.message} (error id ${evt.error_id})`); err.fatal = true; throw err; }
        }
    }
    throw new Error('stream ended without a result');
}

function setLoading(on) {
    state.loading = on;
    elements.analyzeBtn.classList.toggle('loading', on);
    elements.analyzeBtn.disabled = on;
}

function showProgress(steps) {
    elements.resultsPanel.innerHTML = `<div class="progress-steps">
        <div class="progress-title">Analyzing…</div>
        ${steps.map((s, i) => `<div class="progress-step ${i === steps.length - 1 ? 'current' : 'done'}">${esc(s)}</div>`).join('')}
    </div>`;
}

function renderError(e) {
    const hint = e.status === 401 ? 'This deployment requires an API key - open "API key" in the form.'
        : e.status === 403 ? 'Your key/role is not allowed to do this.'
        : e.status === 429 ? 'Rate limit reached - wait a moment and retry.'
        : e.name === 'AbortError' ? 'The request timed out.' : 'The API may be starting up (free-tier hosts sleep) - retry in a few seconds.';
    elements.resultsPanel.innerHTML = `<div class="error-card">
        <h4>Analysis failed</h4><p>${esc(e.message || 'Unknown error')}</p><p class="muted-note">${esc(hint)}</p>
        <button class="btn btn-ghost btn-sm" id="retryBtn">Retry</button></div>`;
    $('retryBtn').addEventListener('click', analyze);
}

// ============================================
// Navigation
// ============================================
function initNavigation() {
    const btn = elements.mobileMenuBtn, menu = elements.mobileMenu;
    if (btn && menu) {
        btn.addEventListener('click', () => menu.classList.toggle('active'));
        menu.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => menu.classList.remove('active')));
    }
}

// ============================================
// Rendering
// ============================================
const lvl = (l) => String(l || '').toLowerCase();

function chip(text, kind = 'info', title = '') {
    return `<span class="chip chip-${kind}"${title ? ` title="${esc(title)}"` : ''}>${esc(text)}</span>`;
}

function renderResult(r) {
    const ra = r.risk_assessment, ex = r.explanation || { contributions: [], counterfactuals: [], category_scores: {} };
    const modeChip = r.mode === 'hybrid' ? chip('Hybrid: engine + AI', 'info', 'AI findings were fused (capped, advisory)') : chip('Deterministic engine', 'good');
    const llmKind = { ok: 'good', disabled: 'muted', partial: 'warn', failed: 'bad', no_api_key: 'warn' }[r.llm_status] || 'muted';
    const actionKind = { BLOCK: 'bad', ESCALATE: 'warn', REVIEW: 'warn', APPROVE: 'good' }[r.recommended_action] || 'info';
    const reportName = (r.report && r.report.report_type) || (r.regime && r.regime.suspicious_report) || 'SAR';

    const html = `<div class="analysis-result">
      <div class="result-head">
        <div class="score"><span class="score-num ${lvl(ra.risk_level)}">${ra.risk_score}</span><span class="score-of">/ 100</span></div>
        <div class="head-meta">
          <span class="pill pill-${lvl(ra.risk_level)}">${esc(ra.risk_level)}</span>
          <div class="chip-row">
            ${chip(r.recommended_action, actionKind)} ${r.sar_required ? chip(`${reportName} required`, 'bad') : chip('No filing required', 'good')}
            ${modeChip} ${chip(`AI: ${r.llm_status}`, llmKind)} ${chip((r.regime && r.regime.code) || '', 'muted')} ${chip(`${r.processing_time_ms} ms`, 'muted')}
          </div>
        </div>
      </div>
      ${(r.warnings || []).map((w) => `<div class="warning-box">${esc(w)}</div>`).join('')}
      ${sectionWaterfall(r, ex)}
      ${sectionTypologies(r)}
      ${sectionScreening(r)}
      ${sectionGraph(r)}
      ${sectionFindings(r)}
      ${sectionAlerts(r)}
      ${sectionSteps(r)}
      ${sectionReport(r)}
      ${sectionAudit(r)}
      <details class="raw"><summary>Raw API response</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details>
    </div>`;
    elements.resultsPanel.innerHTML = html;
    wireResultActions(r);
}

function sectionWaterfall(r, ex) {
    const total = ex.contributions.reduce((s, c) => s + c.points, 0) || 1;
    const color = (c) => CATEGORY_COLORS[c.category] || '#94a3b8';
    const bar = ex.contributions.map((c) => `<div class="wf-seg" style="width:${(100 * c.points / total).toFixed(2)}%;background:${color(c)}" title="${esc(c.description)} (+${c.points})"></div>`).join('');
    const rows = ex.contributions.slice(0, 8).map((c) => `
        <div class="wf-row"><span class="wf-dot" style="background:${color(c)}"></span>
        <span class="wf-text">${esc(c.description)}</span><span class="wf-points">+${c.points}</span></div>`).join('');
    const cf = (ex.counterfactuals || []).map((c) => `
        <div class="cf-item">Without <code>${esc(c.without)}</code> the score would be <strong>${c.score_without}</strong> (${esc(c.level_without)})${c.changes_level ? ' - <em>changes the risk level</em>' : ''}.</div>`).join('');
    const legend = Object.entries(ex.category_scores || {}).map(([k, v]) => `<span class="legend-item"><span class="wf-dot" style="background:${CATEGORY_COLORS[k] || '#94a3b8'}"></span>${esc(k.toLowerCase())} ${v}</span>`).join('');
    return `<div class="result-section"><h4>Why this score <span class="muted-note">contributions sum to ${r.risk_assessment.risk_score}</span></h4>
        <div class="wf-bar">${bar || '<div class="wf-seg" style="width:100%;background:#334155"></div>'}</div>
        <div class="wf-legend">${legend}</div>${rows}${ex.floor_applied ? `<div class="wf-row policy">Mandatory policy floor applied: <code>${esc(ex.floor_applied)}</code></div>` : ''}
        ${cf ? `<div class="cf-box"><div class="muted-note">What would change this?</div>${cf}</div>` : ''}
        <div class="muted-note">AI evidence can add at most ${ex.ai_uplift_cap} points and can never lower the score.</div></div>`;
}

function sectionTypologies(r) {
    if (!(r.typologies || []).length) return '';
    return `<div class="result-section"><h4>Typologies</h4>
      ${r.typologies.map((t) => `<details class="typology"><summary>${chip(t.name, 'info')} <span class="muted-note">${t.signals.length} signal${t.signals.length > 1 ? 's' : ''}</span></summary>
         <p>${esc(t.summary)}</p><p class="muted-note">Reference: ${esc(t.reference)}</p><p class="muted-note">Signals: ${t.signals.map((s) => `<code>${esc(s)}</code>`).join(' ')}</p></details>`).join('')}</div>`;
}

function sectionScreening(r) {
    const s = r.screening || {}, sx = (s.sanctions || {}), list = sx.list || {}, matches = sx.matches || [], pep = s.pep || {};
    const rows = matches.map((m) => `<tr><td>${esc(m.role)}</td><td>${esc(m.queried_name)}</td><td>${esc(m.listed_name)}${m.via_alias ? ` <span class="muted-note">(alias: ${esc(m.matched_name)})</span>` : ''}</td>
        <td>${(m.score * 100).toFixed(0)}%</td><td>${chip(m.level.replace(/_/g, ' '), m.level === 'MATCH' ? 'bad' : 'warn')}</td><td>${esc((m.programs || []).join(', '))}${(m.corroborated_by || []).length ? `<br><span class="muted-note">corroborated: ${esc(m.corroborated_by.join(', '))}</span>` : ''}</td></tr>`).join('');
    const pepRows = [...(pep.list_matches || []).map((m) => `<li>List match: <strong>${esc(m.listed_name)}</strong> - ${esc(m.position || '')} (${esc(m.country || '')}), similarity ${(m.score * 100).toFixed(0)}%</li>`),
                     ...(pep.role_indicators || []).map((m) => `<li>Role indicator: ${esc(m.role)} (“${esc(m.matched_text)}”)</li>`)].join('');
    return `<div class="result-section"><h4>Screening</h4>
      <div class="muted-note">Sanctions list: ${esc(list.name || '')} · ${list.entries || 0} entries · as of ${esc(list.as_of || '?')}${list.synthetic ? ' · <strong>synthetic demo data</strong>' : ''}</div>
      ${matches.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>Role</th><th>Queried</th><th>Listed</th><th>Sim.</th><th>Outcome</th><th>Programs</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="muted-note">No sanctions hits.</p>'}
      ${pepRows ? `<ul class="plain-list">${pepRows}</ul>` : '<p class="muted-note">No PEP indication.</p>'}
      ${s.injection_detected ? '<div class="warning-box"><span>Free-text fields contained instructions aimed at an automated reviewer - flagged and ignored.</span></div>' : ''}</div>`;
}

function sectionGraph(r) {
    const g = r.graph || {};
    if (!(g.edges || []).length) return '';
    const notes = (g.highlights || []).map((h) => {
        if (h.type === 'cycle') return `<li>${chip('Round trip', 'bad')} ${h.nodes.map(esc).join(' → ')} → ${esc(h.nodes[0])} · ${h.length} hops · ~USD ${money(h.amount_usd)}</li>`;
        if (h.type === 'fan_in') return `<li>${chip('Fan-in', 'warn')} ${h.peers.length} senders → ${esc(h.node)} · USD ${money(h.total_usd)}</li>`;
        if (h.type === 'fan_out') return `<li>${chip('Fan-out', 'warn')} ${esc(h.node)} → ${h.peers.length} receivers · USD ${money(h.total_usd)}</li>`;
        if (h.type === 'pass_through') return `<li>${chip('Pass-through', 'warn')} ${esc(h.node)} forwarded USD ${money(h.forwarded_usd)} of ${money(h.received_usd)} in ${h.hours}h</li>`;
        return '';
    }).join('');
    return `<div class="result-section"><h4>Transaction graph</h4>
      <div class="graph-box">${graphSvg(g)}</div><ul class="plain-list">${notes || '<li class="muted-note">No suspicious motif found in this neighbourhood.</li>'}</ul></div>`;
}

function graphSvg(g) {
    const W = 520, H = 300, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 46;
    const nodes = g.nodes.slice(0, 18), pos = {};
    nodes.forEach((n, i) => { const a = (2 * Math.PI * i) / nodes.length - Math.PI / 2; pos[n.id] = [cx + R * Math.cos(a), cy + R * Math.sin(a)]; });
    const edges = g.edges.filter((e) => pos[e.source] && pos[e.target]);
    const lines = edges.map((e) => {
        const [x1, y1] = pos[e.source], [x2, y2] = pos[e.target];
        const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1, ex = x2 - (dx / len) * 14, ey = y2 - (dy / len) * 14;
        const color = e.flagged ? '#ef4444' : e.current ? '#6366f1' : '#475569';
        return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}" stroke="${color}" stroke-width="${e.current ? 2.6 : e.flagged ? 2 : 1.1}" marker-end="url(#arr-${e.flagged ? 'f' : e.current ? 'c' : 'n'})" opacity="${e.flagged || e.current ? 1 : .6}"/>`;
    }).join('');
    const dots = nodes.map((n) => {
        const [x, y] = pos[n.id], fill = n.customer ? '#6366f1' : n.focus ? '#8b5cf6' : '#334155';
        const label = n.id.length > 16 ? n.id.slice(0, 15) + '…' : n.id;
        const anchor = x < cx - 10 ? 'end' : x > cx + 10 ? 'start' : 'middle', dxl = x < cx - 10 ? -12 : x > cx + 10 ? 12 : 0, dyl = Math.abs(x - cx) <= 10 ? (y < cy ? -14 : 20) : 4;
        return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="8" fill="${fill}" stroke="#0a0a0f" stroke-width="2"><title>${esc(n.id)}</title></circle>
                <text x="${(x + dxl).toFixed(1)}" y="${(y + dyl).toFixed(1)}" text-anchor="${anchor}" font-size="10" fill="#cbd5e1">${esc(label)}</text>`;
    }).join('');
    const marker = (id, color) => `<marker id="arr-${id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${color}"/></marker>`;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Transaction graph"><defs>${marker('f', '#ef4444')}${marker('c', '#6366f1')}${marker('n', '#475569')}</defs>${lines}${dots}</svg>`;
}

function sectionFindings(r) {
    const f = r.ai_findings || [];
    if (!f.length) return '';
    return `<div class="result-section"><h4>AI research findings <span class="muted-note">unverified · advisory · capped</span></h4>
      <div class="table-wrap"><table class="data-table"><thead><tr><th>Agent</th><th>Verdict</th><th>Score</th><th>Conf.</th><th>Summary</th></tr></thead><tbody>
      ${f.map((x) => `<tr><td>${esc(x.agent)}</td><td>${esc(x.verdict)}</td><td>${x.risk_score ?? '—'}</td><td>${x.confidence != null ? (x.confidence * 100).toFixed(0) + '%' : '—'}</td>
        <td>${x.parse_status === 'json' || x.parse_status === 'regex' ? esc(x.summary) : chip(`not usable (${x.parse_status})`, 'warn')}</td></tr>`).join('')}
      </tbody></table></div></div>`;
}

function sectionAlerts(r) {
    if (!(r.alerts || []).length) return '';
    return `<div class="result-section"><h4>Alerts (${r.alerts.length})</h4>
      ${r.alerts.map((a) => `<div class="alert-item sev-${lvl(a.severity)}"><span><strong>${esc(a.alert_type.replace(/_/g, ' '))}</strong> · ${esc(a.severity)}<br>${esc(a.title)}</span></div>`).join('')}</div>`;
}

function sectionSteps(r) {
    return `<div class="result-section"><h4>Next steps</h4><ul class="plain-list">${(r.next_steps || []).map((s) => `<li>${esc(s)}</li>`).join('')}</ul></div>`;
}

function sectionReport(r) {
    if (!r.report) return '';
    const c = r.case;
    return `<div class="result-section"><h4>${esc(r.report.report_type)} draft</h4>
      <div class="muted-note">${esc(r.report.status)} · ${esc(r.report.regulator)} · deadline ${esc(r.sar_deadline ? new Date(r.sar_deadline).toLocaleDateString() : 'without delay')}${c ? ` · case <code>${esc(c.case_number)}</code>` : ' · not persisted (demo)'}</div>
      <pre class="report-preview">${esc(r.report.narrative_text)}</pre>
      <div class="btn-row"><button class="btn btn-ghost btn-sm" id="dlJson">JSON</button>
      <button class="btn btn-ghost btn-sm" id="dlMd">Markdown</button></div></div>`;
}

function sectionAudit(r) {
    if (!r.audit) return `<div class="result-section"><h4>Audit trail</h4><p class="muted-note">Not recorded - this request was not persisted (public demo or persist=false).</p></div>`;
    return `<div class="result-section"><h4>Audit trail</h4>
      <div class="audit-box"><div>entry #${r.audit.seq}</div><div class="hash" title="${esc(r.audit.entry_hash)}">${esc(r.audit.entry_hash)}</div>
      <div class="muted-note">previous: <span class="hash">${esc(r.audit.prev_hash.slice(0, 24))}…</span></div>
      <button class="btn btn-ghost btn-sm" id="verifyBtn">Verify entire chain</button> <span id="verifyOut" class="muted-note"></span></div></div>`;
}

function wireResultActions(r) {
    const verify = $('verifyBtn');
    if (verify) verify.addEventListener('click', async () => {
        const out = $('verifyOut'); out.textContent = 'verifying…';
        try {
            const v = await api('/api/v1/audit/verify');
            out.innerHTML = v.valid ? chip(`chain intact · ${v.entries} entries`, 'good') : chip(`BROKEN at #${v.first_invalid_seq}: ${v.detail}`, 'bad');
        } catch (e) { out.textContent = e.status === 403 ? 'Not available in public demo mode.' : `Could not verify: ${e.message}`; }
    });
    const dl = (name, text, type) => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); };
    const j = $('dlJson'), m = $('dlMd');
    if (j) j.addEventListener('click', () => dl(`${r.report.report_type}-draft.json`, JSON.stringify(r.report, null, 2), 'application/json'));
    if (m) m.addEventListener('click', () => dl(`${r.report.report_type}-draft.md`, reportMarkdown(r.report), 'text/markdown'));
}

function reportMarkdown(rep) {
    const kv = (o) => Object.entries(o).map(([k, v]) => `- **${k.replace(/_/g, ' ')}:** ${Array.isArray(v) ? v.join(', ') || 'n/a' : (v ?? 'n/a') === '' ? 'n/a' : (v ?? 'n/a')}`).join('\n');
    return `# ${rep.report_type} draft${rep.case_number ? ' - ' + rep.case_number : ''}\n**${rep.status}**  \nRegulator: ${rep.regulator} · Filing deadline: ${rep.filing_deadline || 'without delay'}\n\n> ${rep.deadline_note}\n\n## Subject\n${kv(rep.subject)}\n\n## Activity\n${kv(rep.activity)}\n\n## Risk\nScore ${rep.risk.score}/100 (${rep.risk.level}) - ${rep.risk.recommended_action}\n\n## Red flags\n${rep.red_flags.map((f) => `- [${f.severity}] ${f.description}`).join('\n')}\n\n## Narrative\n${rep.narrative_text}\n\n## Limitations\n${rep.limitations.map((l) => `- ${l}`).join('\n')}\n`;
}


// ============================================
// Notifications
// ============================================
function showNotification(message, type = 'info') {
    document.querySelectorAll('.notification').forEach((n) => n.remove());
    const n = document.createElement('div');
    n.className = `notification notification-${type}`;
    n.textContent = message;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 4000);
}

// Drex Decision Gateway Dashboard Client

let currentTab = 'overview';
let activeTraceId = null;

document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  loadProviderStatus();
  loadOverview();
  setInterval(refreshActiveTab, 10000);
});

function setupNavigation() {
  const buttons = document.querySelectorAll('.nav-links button');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tab = btn.dataset.tab;
      switchTab(tab);
    });
  });

  const toggle = document.querySelector('.menu-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      document.querySelector('.sidebar').classList.toggle('open');
    });
  }
}

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.nav-links button').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-view').forEach(view => {
    view.style.display = view.id === `view-${tab}` ? 'block' : 'none';
  });
  document.querySelector('.topbar-title').textContent = getTabTitle(tab);

  // Close mobile sidebar
  document.querySelector('.sidebar')?.classList.remove('open');

  refreshActiveTab();
}

function getTabTitle(tab) {
  const titles = {
    overview: 'System Overview & Decision Throughput',
    decisions: 'Live Structured Decisions',
    trace: 'Decision Provenance & Trace Timeline',
    demo: 'End-to-End Coding Agent Loop Demo',
    benchmarks: 'Benchmark Harness & Threshold Simulation',
    health: 'Provider Infrastructure & Model Telemetry'
  };
  return titles[tab] || 'Dashboard';
}

function refreshActiveTab() {
  if (currentTab === 'overview') loadOverview();
  else if (currentTab === 'decisions') loadDecisions();
  else if (currentTab === 'trace' && activeTraceId) loadTrace(activeTraceId);
  else if (currentTab === 'benchmarks') loadBenchmarks();
  else if (currentTab === 'health') loadHealth();
}

async function loadProviderStatus() {
  try {
    const res = await fetch('/v1/providers');
    const data = await res.json();
    const pill = document.getElementById('provider-status-pill');
    if (pill) {
      const mode = data.active_mode;
      const badgeCls = mode === 'LIVE' ? 'badge-live' : 'badge-replay';
      pill.innerHTML = `<span class="dot"></span> ${data.active_provider} <span class="${badgeCls}">${mode}</span>`;
    }
  } catch (err) {
    console.error('Error fetching provider status:', err);
  }
}

async function loadOverview() {
  try {
    const res = await fetch('/v1/stats');
    const s = await res.json();

    document.getElementById('metric-total-decisions').textContent = s.decisions_total ?? 0;
    document.getElementById('metric-calls-avoided').textContent = s.expensive_calls_avoided ?? 0;
    document.getElementById('metric-escalation-rate').textContent = (s.escalation_rate !== null ? (s.escalation_rate * 100).toFixed(1) + '%' : '0.0%');
    document.getElementById('metric-latency-p50').textContent = (s.latency_p50_ms !== null ? s.latency_p50_ms + ' ms' : 'N/A');
    document.getElementById('metric-overhead-p50').textContent = (s.gateway_overhead_p50_ms !== null ? s.gateway_overhead_p50_ms + ' ms' : 'N/A');
    document.getElementById('metric-success-rate').textContent = (s.success_rate !== null ? (s.success_rate * 100).toFixed(1) + '%' : 'N/A');

    // Decision types breakdown table
    const typeBody = document.getElementById('types-table-body');
    if (typeBody) {
      typeBody.innerHTML = '';
      const types = Object.entries(s.decision_types || {}).sort((a,b) => b[1] - a[1]);
      if (types.length === 0) {
        typeBody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">No decisions recorded yet. Run the demo or benchmark.</td></tr>';
      } else {
        types.forEach(([type, count]) => {
          const pct = s.decisions_total ? ((count / s.decisions_total) * 100).toFixed(1) : 0;
          typeBody.innerHTML += `
            <tr>
              <td><code>${escapeHtml(type)}</code></td>
              <td>${count}</td>
              <td>${pct}%</td>
            </tr>
          `;
        });
      }
    }
  } catch (err) {
    console.error('Error fetching overview stats:', err);
  }
}

async function loadDecisions() {
  try {
    const filterType = document.getElementById('filter-decision-type')?.value || '';
    const filterDisp = document.getElementById('filter-disposition')?.value || '';

    let url = '/v1/decisions?limit=30';
    if (filterType) url += `&decision_type=${encodeURIComponent(filterType)}`;
    if (filterDisp) url += `&disposition=${encodeURIComponent(filterDisp)}`;

    const res = await fetch(url);
    const decisions = await res.json();
    const tbody = document.getElementById('decisions-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (!decisions || decisions.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">No decisions found matching filter criteria.</td></tr>';
      return;
    }

    decisions.forEach(d => {
      const dispCls = d.disposition === 'ACCEPT' ? 'badge-accept' : (d.disposition === 'ESCALATE' ? 'badge-escalate' : 'badge-abstain');
      const provCls = d.provider === 'Drex' ? 'badge-live' : 'badge-replay';

      // Build probability bars
      let probBars = '<div class="prob-bar-container">';
      const entries = Object.entries(d.probabilities || {}).sort((a,b) => b[1] - a[1]).slice(0, 3);
      entries.forEach(([choice, prob]) => {
        const pct = (prob * 100).toFixed(1);
        probBars += `
          <div class="prob-row">
            <span class="prob-label" title="${escapeHtml(choice)}">${escapeHtml(choice)}</span>
            <div class="prob-track"><div class="prob-fill" style="width: ${pct}%;"></div></div>
            <span class="prob-pct">${pct}%</span>
          </div>
        `;
      });
      probBars += '</div>';

      tbody.innerHTML += `
        <tr>
          <td><span class="${dispCls}">${d.disposition}</span></td>
          <td><strong>${escapeHtml(d.decision_type)}</strong></td>
          <td><code>${escapeHtml(String(d.selected))}</code> (${(d.confidence * 100).toFixed(1)}%)</td>
          <td>${probBars}</td>
          <td>${d.latency_ms.toFixed(1)}ms <span style="color: var(--text-muted); font-size: 0.72rem;">(gw: ${d.gateway_overhead_ms.toFixed(1)}ms)</span></td>
          <td><span class="${provCls}">${escapeHtml(d.provider)}</span></td>
          <td><button class="btn btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="viewTrace('${d.trace_id}')">Trace</button></td>
        </tr>
      `;
    });
  } catch (err) {
    console.error('Error loading decisions:', err);
  }
}

function viewTrace(traceId) {
  activeTraceId = traceId;
  const input = document.getElementById('trace-id-input');
  if (input) input.value = traceId;
  switchTab('trace');
  loadTrace(traceId);
}

async function loadTrace(traceId) {
  if (!traceId) return;
  activeTraceId = traceId;
  try {
    const res = await fetch(`/v1/traces/${encodeURIComponent(traceId)}`);
    if (!res.ok) {
      document.getElementById('trace-container').innerHTML = `<div style="color: var(--accent-rose); padding: 20px;">Trace not found: ${escapeHtml(traceId)}</div>`;
      return;
    }
    const trace = await res.json();

    document.getElementById('trace-header-id').textContent = trace.trace_id;
    document.getElementById('trace-header-decisions').textContent = trace.total_drex_decisions;
    document.getElementById('trace-header-avoided').textContent = trace.expensive_calls_avoided;
    document.getElementById('trace-header-latency').textContent = trace.total_latency_ms.toFixed(1) + 'ms';

    const timeline = document.getElementById('trace-timeline');
    timeline.innerHTML = '';

    trace.decisions.forEach((d, idx) => {
      const dispCls = d.disposition === 'ACCEPT' ? 'badge-accept' : (d.disposition === 'ESCALATE' ? 'badge-escalate' : 'badge-abstain');
      timeline.innerHTML += `
        <div class="timeline-item">
          <div class="timeline-dot">${idx + 1}</div>
          <div class="timeline-content">
            <div class="timeline-header">
              <span class="timeline-title">${escapeHtml(d.decision_type)}</span>
              <span class="${dispCls}">${d.disposition}</span>
            </div>
            <div style="margin: 8px 0; font-size: 0.9rem;">
              Selected: <strong style="color: var(--accent-cyan);">${escapeHtml(String(d.selected))}</strong> (confidence: ${(d.confidence * 100).toFixed(1)}%)
            </div>
            <div class="timeline-meta">
              Model: ${escapeHtml(d.model)} | Latency: ${d.latency_ms.toFixed(1)}ms | Overhead: ${d.gateway_overhead_ms.toFixed(1)}ms | Time: ${d.created_at}
            </div>
          </div>
        </div>
      `;
    });

    if (trace.outcomes && trace.outcomes.length > 0) {
      trace.outcomes.forEach(o => {
        timeline.innerHTML += `
          <div class="timeline-item">
            <div class="timeline-dot" style="border-color: var(--accent-green); background: rgba(16, 185, 129, 0.2);">✓</div>
            <div class="timeline-content" style="border-left: 3px solid var(--accent-green);">
              <div class="timeline-header">
                <span class="timeline-title" style="color: var(--accent-green);">Verified Downstream Outcome</span>
                <span class="badge-accept">${escapeHtml(o.outcome)}</span>
              </div>
              <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">Success: ${o.success} | Recorded at: ${o.recorded_at}</p>
            </div>
          </div>
        `;
      });
    }
  } catch (err) {
    console.error('Error loading trace:', err);
  }
}

async function runInteractiveDemo() {
  const btn = document.getElementById('btn-run-demo');
  const logContainer = document.getElementById('demo-steps-log');
  const summaryBox = document.getElementById('demo-summary-box');

  if (btn) btn.disabled = true;
  logContainer.innerHTML = '<div style="color: var(--accent-cyan); padding: 12px;">Initiating Drex coding agent loop simulation...</div>';
  summaryBox.style.display = 'none';

  try {
    const res = await fetch('/v1/demo/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ simulate_failure_and_repair: true })
    });
    const report = await res.json();

    logContainer.innerHTML = '';
    report.steps.forEach(step => {
      const actorColor = step.actor.includes('Drex') ? 'var(--accent-cyan)' : (step.actor.includes('Verifier') ? 'var(--accent-green)' : 'var(--accent-purple)');
      logContainer.innerHTML += `
        <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 14px; margin-bottom: 12px;">
          <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 6px;">
            <span style="font-weight: 700; color: ${actorColor};">[Step ${step.step_number}] ${escapeHtml(step.name)}</span>
            <span style="font-family: var(--font-mono); color: var(--text-muted);">${step.latency_ms.toFixed(1)}ms</span>
          </div>
          <div style="font-size: 0.88rem; color: #fff;">${escapeHtml(step.summary)}</div>
        </div>
      `;
    });

    summaryBox.style.display = 'block';
    document.getElementById('demo-total-decisions').textContent = report.total_drex_decisions;
    document.getElementById('demo-calls-avoided').textContent = report.expensive_calls_avoided;
    document.getElementById('demo-drex-latency').textContent = report.total_drex_latency_ms.toFixed(1) + 'ms';
    document.getElementById('demo-final-outcome').textContent = report.final_status;
    document.getElementById('demo-trace-link').onclick = () => viewTrace(report.trace_id);

    // Refresh overview metrics
    loadOverview();
  } catch (err) {
    logContainer.innerHTML = `<div style="color: var(--accent-rose); padding: 12px;">Error executing demo: ${err}</div>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadBenchmarks() {
  try {
    const res = await fetch('/v1/benchmarks');
    const runs = await res.json();
    const container = document.getElementById('benchmarks-history');
    if (!container) return;

    container.innerHTML = '';
    if (!runs || runs.length === 0) {
      container.innerHTML = '<p style="color: var(--text-muted);">No benchmark runs recorded. Run via CLI: <code>drex-gateway benchmark</code></p>';
      return;
    }

    runs.forEach(r => {
      container.innerHTML += `
        <div style="background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; padding: 16px; margin-bottom: 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <strong style="font-size: 0.95rem;">${escapeHtml(r.suite_name)} (${escapeHtml(r.provider)} / ${escapeHtml(r.model)})</strong>
            <span style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted);">${r.created_at}</span>
          </div>
          <div class="metrics-grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom: 12px;">
            <div style="padding: 8px;">
              <span style="font-size: 0.75rem; color: var(--text-muted);">ACCURACY</span>
              <div style="font-size: 1.2rem; font-weight: 700; font-family: var(--font-mono); color: var(--accent-green);">${r.accuracy ? (r.accuracy * 100).toFixed(1) + '%' : 'N/A'}</div>
            </div>
            <div style="padding: 8px;">
              <span style="font-size: 0.75rem; color: var(--text-muted);">COVERAGE</span>
              <div style="font-size: 1.2rem; font-weight: 700; font-family: var(--font-mono); color: var(--accent-cyan);">${(r.coverage * 100).toFixed(1)}%</div>
            </div>
            <div style="padding: 8px;">
              <span style="font-size: 0.75rem; color: var(--text-muted);">ESCALATION</span>
              <div style="font-size: 1.2rem; font-weight: 700; font-family: var(--font-mono); color: var(--accent-amber);">${(r.escalation_rate * 100).toFixed(1)}%</div>
            </div>
            <div style="padding: 8px;">
              <span style="font-size: 0.75rem; color: var(--text-muted);">LATENCY P50</span>
              <div style="font-size: 1.2rem; font-weight: 700; font-family: var(--font-mono);">${r.latency_p50 ? r.latency_p50.toFixed(1) + 'ms' : 'N/A'}</div>
            </div>
          </div>
          ${(r.report && r.report.calibration_bins && r.report.calibration_bins.length > 0) ? `
          <div style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 10px;">
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 6px; font-weight: 600;">CALIBRATION BINS & PROBABILITY ACCURACY</div>
            <table style="width: 100%; font-size: 0.8rem;">
              <thead>
                <tr>
                  <th style="padding: 4px 8px;">Confidence Range</th>
                  <th style="padding: 4px 8px;">Samples</th>
                  <th style="padding: 4px 8px;">Empirical Accuracy</th>
                  <th style="padding: 4px 8px;">Mean Confidence</th>
                </tr>
              </thead>
              <tbody>
                ${r.report.calibration_bins.map(b => `
                  <tr>
                    <td style="padding: 4px 8px;"><code>${b.range}</code></td>
                    <td style="padding: 4px 8px;">${b.count}</td>
                    <td style="padding: 4px 8px; color: ${b.accuracy !== null ? 'var(--accent-green)' : 'var(--text-muted)'};">${b.accuracy !== null ? (b.accuracy * 100).toFixed(1) + '%' : 'N/A'}</td>
                    <td style="padding: 4px 8px;">${b.confidence !== null ? (b.confidence * 100).toFixed(1) + '%' : 'N/A'}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          ` : ''}
        </div>
      `;
    });
  } catch (err) {
    console.error('Error loading benchmarks:', err);
  }
}

async function loadHealth() {
  try {
    const resM = await fetch('/v1/models');
    const mData = await resM.json();
    const modelsTbody = document.getElementById('models-table-body');
    if (modelsTbody) {
      modelsTbody.innerHTML = '';
      (mData.models || []).forEach(m => {
        modelsTbody.innerHTML += `
          <tr>
            <td><code>${escapeHtml(m.name || '')}</code></td>
            <td>${escapeHtml(m.description || '')}</td>
            <td><code>${escapeHtml(m.alias_for || 'None')}</code></td>
            <td>${escapeHtml(m.release_date || 'N/A')}</td>
          </tr>
        `;
      });
    }
  } catch (err) {
    console.error('Error loading health:', err);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

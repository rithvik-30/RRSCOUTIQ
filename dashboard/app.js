/**
 * RR ScoutIQ — Complete Premium Product Redesign
 * Professional Cricket Analytics Platform Application Controller
 * Default Theme: Light Mode | Tabular-First & Responsive
 */

(function () {
  'use strict';

  // 1. Application State
  // Strictly enforce Light Mode as default
  const state = {
    theme: 'light',
    activeTab: 'overview',
    activeDisciplineFilter: 'all',
    selectedPlayerId: 6281, // Default to #1 Batter: Abhishek Sharma
    selectedPlayerType: 'batter', // 'batter' or 'bowler'
    searchQuery: '',
    charts: {
      tierChart: null,
      boundaryChart: null
    }
  };

  const data = window.RR_DATA;
  if (!data) {
    console.error('Fatal: RR_DATA not found. Ensure data.js is loaded.');
    return;
  }

  // 2. DOM Elements
  const body = document.body;
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeToggleText = document.getElementById('themeToggleText');
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const mobileNavDrawer = document.getElementById('mobileNavDrawer');
  const navLinks = document.querySelectorAll('.nav-link');
  const sections = document.querySelectorAll('.page-section');
  const brandLogo = document.getElementById('brandLogo');

  // Batters Elements
  const battersFeaturedContainer = document.getElementById('battersFeaturedContainer');
  const battersTableBody = document.getElementById('battersTableBody');

  // Bowlers Elements
  const bowlersFeaturedContainer = document.getElementById('bowlersFeaturedContainer');
  const bowlersTableBody = document.getElementById('bowlersTableBody');

  // Explorer Elements
  const playerPickerList = document.getElementById('playerPickerList');
  const explorerSearchInput = document.getElementById('explorerSearchInput');
  const explorerFilterBtns = document.querySelectorAll('.filter-pill');

  // Quick Action Buttons
  const heroBtnBatters = document.getElementById('heroBtnBatters');
  const heroBtnBowlers = document.getElementById('heroBtnBowlers');
  const heroBtnExplorer = document.getElementById('heroBtnExplorer');
  const previewLinkBatters = document.getElementById('previewLinkBatters');
  const previewLinkBowlers = document.getElementById('previewLinkBowlers');

  // 3. Theme Handler (Strict Light Mode Default)
  function initTheme() {
    body.classList.remove('dark-theme');
    body.classList.add('light-theme');
    updateThemeUI();
  }

  function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    body.classList.remove('light-theme', 'dark-theme');
    body.classList.add(state.theme === 'dark' ? 'dark-theme' : 'light-theme');
    updateThemeUI();
    updateChartsTheme();
  }

  function updateThemeUI() {
    if (!themeToggleText) return;
    if (state.theme === 'dark') {
      themeToggleText.textContent = 'Light Mode';
      themeToggleBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
        <span>Light Mode</span>
      `;
    } else {
      themeToggleText.textContent = 'Dark Mode';
      themeToggleBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
        <span>Dark Mode</span>
      `;
    }
  }

  // 4. Tab Navigation
  function switchTab(targetTabId) {
    state.activeTab = targetTabId;

    sections.forEach(sec => {
      sec.classList.remove('active');
      if (sec.id === `section-${targetTabId}`) {
        sec.classList.add('active');
      }
    });

    navLinks.forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('data-tab') === targetTabId) {
        link.classList.add('active');
      }
    });

    if (mobileNavDrawer) {
      mobileNavDrawer.classList.remove('open');
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });

    if (targetTabId === 'batters') renderBattersLeaderboard();
    if (targetTabId === 'bowlers') renderBowlersLeaderboard();
    if (targetTabId === 'explorer') renderPlayerExplorer();
  }

  // Expose globally for inline buttons/links
  window.switchTab = switchTab;

  // 5. Render Top 10 Batters (Featured Podium Top 3 + Clean Comparison Table)
  function renderBattersLeaderboard() {
    if (!battersFeaturedContainer || !battersTableBody) return;

    // A. Render Top 3 Featured Podium Cards
    const top3 = data.batters.slice(0, 3);
    battersFeaturedContainer.innerHTML = top3.map(b => `
      <div class="podium-card rank-${b.rank}">
        <div class="podium-header-row">
          <div>
            <h3 class="podium-name">${b.name}</h3>
            <span class="podium-sub">ID: ${b.player_id} • ${b.discipline_eligibility}</span>
          </div>
          <span class="podium-rank-badge">#${b.rank}</span>
        </div>

        <div class="podium-metric-box">
          <span class="podium-metric-label">Primary Metric (LB90)</span>
          <div class="podium-metric-val">+${b.model.lb90.toFixed(2)}%</div>
        </div>

        <div class="podium-stats-grid">
          <div class="podium-stat-box">
            <span class="podium-stat-label">Contextual ΔEB</span>
            <span class="podium-stat-num">+${b.model.val_add.toFixed(2)}%</span>
          </div>
          <div class="podium-stat-box">
            <span class="podium-stat-label">Pressure SR</span>
            <span class="podium-stat-num">${b.pressure.sr.toFixed(2)}</span>
          </div>
          <div class="podium-stat-box">
            <span class="podium-stat-label">Career Legal Balls</span>
            <span class="podium-stat-num">${b.total_balls.toLocaleString()}</span>
          </div>
          <div class="podium-stat-box">
            <span class="podium-stat-label">Pressure Balls</span>
            <span class="podium-stat-num">${b.pressure.balls.toLocaleString()}</span>
          </div>
        </div>

        <div class="podium-footer">
          <span class="badge-status confirmed">Confirmed Positive</span>
          <button class="btn-table-action" data-player-id="${b.player_id}" data-type="batter">
            Analyze in Explorer →
          </button>
        </div>
      </div>
    `).join('');

    // B. Render Full 10-Player Comparison Table
    battersTableBody.innerHTML = data.batters.map(b => {
      const isConfirmed = b.rank <= 3;
      const statusHtml = isConfirmed
        ? `<span class="badge-status confirmed">Confirmed Positive</span>`
        : `<span class="badge-status relative">Relative Leader</span>`;

      return `
        <tr>
          <td style="font-weight:700; font-family:var(--font-mono); color:var(--text-secondary);">#${b.rank}</td>
          <td>
            <div style="font-weight:700; color:var(--text-primary);">${b.name}</div>
            <div style="font-size:0.72rem; color:var(--text-muted);">ID: ${b.player_id} • ${b.discipline_eligibility}</div>
          </td>
          <td class="num-col" style="font-weight:600;">+${b.model.val_add.toFixed(2)}%</td>
          <td class="num-col col-rank-metric">${b.model.lb90 > 0 ? '+' : ''}${b.model.lb90.toFixed(2)}%</td>
          <td class="num-col" style="font-weight:600;">${b.pressure.sr.toFixed(2)}</td>
          <td class="num-col">${b.pressure.bnd_pct.toFixed(2)}%</td>
          <td class="num-col">${b.pressure.dot_pct.toFixed(2)}%</td>
          <td class="num-col">${b.total_balls.toLocaleString()}</td>
          <td class="num-col">${b.pressure.balls.toLocaleString()}</td>
          <td>${statusHtml}</td>
          <td>
            <button class="btn-table-action" data-player-id="${b.player_id}" data-type="batter">
              Analyze
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // 6. Render Top 10 Bowlers (Featured Podium Top 3 + Clean Comparison Table)
  function renderBowlersLeaderboard() {
    if (!bowlersFeaturedContainer || !bowlersTableBody) return;

    // A. Render Top 3 Featured Podium Cards
    const top3 = data.bowlers.slice(0, 3);
    bowlersFeaturedContainer.innerHTML = top3.map(bw => `
      <div class="podium-card rank-${bw.rank}">
        <div class="podium-header-row">
          <div>
            <h3 class="podium-name">${bw.name}</h3>
            <span class="podium-sub">ID: ${bw.player_id} • ${bw.discipline_eligibility}</span>
          </div>
          <span class="podium-rank-badge">#${bw.rank}</span>
        </div>

        <div class="podium-metric-box">
          <span class="podium-metric-label">Primary Metric (UB90)</span>
          <div class="podium-metric-val">+${bw.model.ub90.toFixed(3)} RPO</div>
        </div>

        <div class="podium-stats-grid">
          <div class="podium-stat-box">
            <span class="podium-stat-label">Contextual ΔEB</span>
            <span class="podium-stat-num">${bw.model.delta_rpo.toFixed(3)} RPO</span>
          </div>
          <div class="podium-stat-box">
            <span class="podium-stat-label">Pressure Economy</span>
            <span class="podium-stat-num">${bw.pressure.econ.toFixed(2)} RPO</span>
          </div>
          <div class="podium-stat-box">
            <span class="podium-stat-label">Career Overs</span>
            <span class="podium-stat-num">${bw.overs} ov</span>
          </div>
          <div class="podium-stat-box">
            <span class="podium-stat-label">Pressure Balls</span>
            <span class="podium-stat-num">${bw.pressure.balls.toLocaleString()}</span>
          </div>
        </div>

        <div class="podium-footer">
          <span class="badge-status relative">Relative Leader</span>
          <button class="btn-table-action" data-player-id="${bw.player_id}" data-type="bowler">
            Analyze in Explorer →
          </button>
        </div>
      </div>
    `).join('');

    // B. Render Full 10-Player Comparison Table
    bowlersTableBody.innerHTML = data.bowlers.map(bw => `
      <tr>
        <td style="font-weight:700; font-family:var(--font-mono); color:var(--text-secondary);">#${bw.rank}</td>
        <td>
          <div style="font-weight:700; color:var(--text-primary);">${bw.name}</div>
          <div style="font-size:0.72rem; color:var(--text-muted);">ID: ${bw.player_id} • ${bw.discipline_eligibility}</div>
        </td>
        <td class="num-col" style="font-weight:600;">${bw.model.delta_rpo.toFixed(3)} RPO</td>
        <td class="num-col col-rank-metric">+${bw.model.ub90.toFixed(3)} RPO</td>
        <td class="num-col" style="font-weight:600;">${bw.pressure.econ.toFixed(2)} RPO</td>
        <td class="num-col">${bw.pressure.wkts} (${bw.pressure.sr.toFixed(1)})</td>
        <td class="num-col">${bw.pressure.dot_pct.toFixed(2)}%</td>
        <td class="num-col">${bw.overs} ov</td>
        <td class="num-col">${bw.pressure.balls.toLocaleString()}</td>
        <td><span class="badge-status relative">Relative Leader</span></td>
        <td>
          <button class="btn-table-action" data-player-id="${bw.player_id}" data-type="bowler">
            Analyze
          </button>
        </td>
      </tr>
    `).join('');
  }

  // 7. Render Player Explorer Sidebar List
  function renderPlayerPickerList() {
    if (!playerPickerList) return;

    let players = [];
    if (state.activeDisciplineFilter === 'all' || state.activeDisciplineFilter === 'batter') {
      players = players.concat(data.batters.map(b => ({ ...b, type: 'batter' })));
    }
    if (state.activeDisciplineFilter === 'all' || state.activeDisciplineFilter === 'bowler') {
      players = players.concat(data.bowlers.map(bw => ({ ...bw, type: 'bowler' })));
    }

    if (state.searchQuery.trim()) {
      const q = state.searchQuery.toLowerCase();
      players = players.filter(p => p.name.toLowerCase().includes(q) || String(p.player_id).includes(q));
    }

    if (players.length === 0) {
      playerPickerList.innerHTML = `
        <div style="padding:24px; text-align:center; color:var(--text-muted); font-size:0.82rem;">
          No candidates match "${state.searchQuery}"
        </div>
      `;
      return;
    }

    playerPickerList.innerHTML = players.map(p => {
      const isSelected = p.player_id === state.selectedPlayerId && p.type === state.selectedPlayerType;
      const isBatter = p.type === 'batter';
      const metricVal = isBatter
        ? `${p.model.lb90 > 0 ? '+' : ''}${p.model.lb90.toFixed(2)}% LB`
        : `+${p.model.ub90.toFixed(3)} UB`;

      return `
        <div class="player-list-item ${isSelected ? 'active' : ''}" data-player-id="${p.player_id}" data-type="${p.type}">
          <div>
            <div class="player-list-item-name">#${p.rank} ${p.name}</div>
            <div class="player-list-item-role">${isBatter ? 'Batter' : 'Bowler'} • ${p.pressure.balls.toLocaleString()} press balls</div>
          </div>
          <div class="player-list-item-val" style="color:var(--primary);">
            ${metricVal}
          </div>
        </div>
      `;
    }).join('');

    // Attach click listeners to player items
    playerPickerList.querySelectorAll('.player-list-item').forEach(item => {
      item.addEventListener('click', () => {
        state.selectedPlayerId = parseInt(item.getAttribute('data-player-id'), 10);
        state.selectedPlayerType = item.getAttribute('data-type');
        renderPlayerPickerList();
        renderPlayerExplorer();
      });
    });
  }

  // 8. Render Player Detail Workbench
  function renderPlayerExplorer() {
    const isBatter = state.selectedPlayerType === 'batter';
    const player = isBatter
      ? data.batters.find(b => b.player_id === state.selectedPlayerId)
      : data.bowlers.find(bw => bw.player_id === state.selectedPlayerId);

    if (!player) return;

    renderPlayerPickerList();

    // A. Header Elements
    const detailRank = document.getElementById('detailPlayerRank');
    const detailName = document.getElementById('detailPlayerName');
    const detailMeta = document.getElementById('detailPlayerMeta');
    const detailStatus = document.getElementById('detailPlayerStatus');

    if (detailRank) detailRank.textContent = `#${player.rank}`;
    if (detailName) detailName.textContent = player.name;
    if (detailMeta) {
      const vol = isBatter
        ? `${player.total_balls.toLocaleString()} balls faced`
        : `${player.overs} ov (${player.total_balls.toLocaleString()} balls)`;
      detailMeta.innerHTML = `<span>ID: <strong>${player.player_id}</strong></span> • <span>Eligibility: <strong>${player.discipline_eligibility}</strong></span> • <span>${player.matches} Matches (${vol})</span>`;
    }
    if (detailStatus) {
      if (isBatter && player.is_confirmed_positive) {
        detailStatus.innerHTML = `<span class="badge-status confirmed">Confirmed Positive</span>`;
      } else {
        detailStatus.innerHTML = `<span class="badge-status relative">Relative Leader</span>`;
      }
    }

    // B. Metric Boxes
    const box1Val = document.getElementById('explorerBox1Val');
    const box1Sub = document.getElementById('explorerBox1Sub');
    const box2Val = document.getElementById('explorerBox2Val');
    const box2Sub = document.getElementById('explorerBox2Sub');
    const box3Val = document.getElementById('explorerBox3Val');
    const box3Sub = document.getElementById('explorerBox3Sub');
    const box4Val = document.getElementById('explorerBox4Val');
    const box4Sub = document.getElementById('explorerBox4Sub');

    if (isBatter) {
      if (box1Val) box1Val.textContent = `+${player.model.val_add.toFixed(2)}%`;
      if (box1Sub) box1Sub.textContent = `Contextual Batting Val-Add (ΔEB)`;

      if (box2Val) {
        box2Val.textContent = `${player.model.lb90 > 0 ? '+' : ''}${player.model.lb90.toFixed(2)}%`;
        box2Val.style.color = 'var(--primary)';
      }
      if (box2Sub) box2Sub.textContent = `95% Lower Posterior Bound (LB90)`;

      if (box3Val) box3Val.textContent = `${player.pressure.sr.toFixed(2)}`;
      if (box3Sub) box3Sub.textContent = `Pressure Strike Rate (T2–4)`;

      if (box4Val) box4Val.textContent = `${player.pressure.dot_pct.toFixed(2)}%`;
      if (box4Sub) box4Sub.textContent = `Pressure Dot Ball %`;
    } else {
      if (box1Val) box1Val.textContent = `${player.model.delta_rpo.toFixed(3)} RPO`;
      if (box1Sub) box1Sub.textContent = `Contextual Economy Delta (ΔEB)`;

      if (box2Val) {
        box2Val.textContent = `+${player.model.ub90.toFixed(3)} RPO`;
        box2Val.style.color = 'var(--primary)';
      }
      if (box2Sub) box2Sub.textContent = `95% Upper Posterior Bound (UB90)`;

      if (box3Val) box3Val.textContent = `${player.pressure.econ.toFixed(2)} RPO`;
      if (box3Sub) box3Sub.textContent = `Pressure Economy (T2–4)`;

      if (box4Val) box4Val.textContent = `${player.pressure.wkts} wkts`;
      if (box4Sub) box4Sub.textContent = `Pressure Wickets (${player.pressure.sr.toFixed(1)} SR)`;
    }

    // C. Render 4-Tier Match-State Table
    renderTierTable(player, isBatter);

    // D. Render Charts
    renderCharts(player, isBatter);

    // E. Limitations Notice
    const limitTitle = document.getElementById('explorerLimitTitle');
    const limitBody = document.getElementById('explorerLimitBody');
    if (limitTitle && limitBody) {
      if (isBatter) {
        if (player.t4.balls === 0) {
          limitTitle.textContent = 'Exposure Notice: Zero Tier 4 Balls';
          limitBody.textContent = `This batter has exactly 0 career deliveries in Tier 4 Extreme Leverage. His high ranking is driven by performance in Tier 2 and Tier 3 (top-order and middle-overs pressure). No terminal crunch-time execution can be statistically asserted.`;
        } else if (player.t4.balls < 50) {
          limitTitle.textContent = `Exposure Notice: Small Tier 4 Sample (${player.t4.balls} Balls)`;
          limitBody.textContent = `Tier 4 sample size is modest (${player.t4.balls} deliveries). The primary pressure rating is established through consistent performance across Tier 2 and Tier 3.`;
        } else {
          limitTitle.textContent = `Robust Exposure (${player.t4.balls} Tier 4 Balls)`;
          limitBody.textContent = `This player maintains verified high exposure across terminal crunch situations, absorbing ${player.t4.balls} deliveries in Tier 4 Extreme Pressure with consistent execution.`;
        }
      } else {
        limitTitle.textContent = 'Statistical Confidence Disclosure';
        limitBody.textContent = `The 95% one-sided upper posterior credible bound (+${player.model.ub90.toFixed(3)} RPO) crosses zero. Like all bowlers in the cohort, economy suppression below context is an empirical relative ranking rather than an assertion of suppression under the credible bound.`;
      }
    }
  }

  // 9. Render 4-Tier Match-State Table
  function renderTierTable(player, isBatter) {
    const tbody = document.getElementById('explorerTierTableBody');
    const thead = document.getElementById('explorerTierTableHead');
    if (!tbody || !thead) return;

    if (isBatter) {
      thead.innerHTML = `
        <tr>
          <th>Tier / State</th>
          <th>DLI Range</th>
          <th class="num-col">Balls</th>
          <th class="num-col">Runs</th>
          <th class="num-col">SR</th>
          <th class="num-col">Boundaries</th>
          <th class="num-col">Dots</th>
          <th class="num-col">Outs (Hazard)</th>
        </tr>
      `;

      const rows = [
        { name: 'T1: Normal Baseline', range: 'DLI < 0.90', d: player.normal },
        { name: 'T2: Medium Leverage', range: '0.90 ≤ DLI < 1.35', d: player.t2 },
        { name: 'T3: High Leverage', range: '1.35 ≤ DLI < 2.25', d: player.t3 },
        { name: 'T4: Extreme Crunch', range: 'DLI ≥ 2.25', d: player.t4 },
        { name: 'Combined Pressure (T2–4)', range: 'DLI ≥ 0.90', d: player.pressure },
        { name: 'High Pressure (T3–4)', range: 'DLI ≥ 1.35', d: player.high }
      ];

      tbody.innerHTML = rows.map(r => `
        <tr style="${r.name.includes('Combined') ? 'font-weight:700; background:var(--surface-soft);' : ''}">
          <td>${r.name}</td>
          <td style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-secondary);">${r.range}</td>
          <td class="num-col">${r.d.balls.toLocaleString()}</td>
          <td class="num-col">${r.d.runs.toLocaleString()}</td>
          <td class="num-col" style="font-weight:700; color:${r.d.balls > 0 && r.d.sr >= 170 ? 'var(--primary)' : 'inherit'};">
            ${r.d.balls > 0 ? r.d.sr.toFixed(2) : '—'}
          </td>
          <td class="num-col">${r.d.bnd} (${r.d.balls > 0 ? r.d.bnd_pct.toFixed(1) + '%' : '—'})</td>
          <td class="num-col">${r.d.dots} (${r.d.balls > 0 ? r.d.dot_pct.toFixed(1) + '%' : '—'})</td>
          <td class="num-col">${r.d.outs} (${r.d.balls > 0 ? r.d.hazard.toFixed(2) + '%' : '—'})</td>
        </tr>
      `).join('');
    } else {
      thead.innerHTML = `
        <tr>
          <th>Tier / State</th>
          <th>DLI Range</th>
          <th class="num-col">Balls (Overs)</th>
          <th class="num-col">Runs Conceded</th>
          <th class="num-col">Economy (RPO)</th>
          <th class="num-col">Wickets</th>
          <th class="num-col">Bowling SR</th>
          <th class="num-col">Dot Ball %</th>
        </tr>
      `;

      const rows = [
        { name: 'T1: Normal Baseline', range: 'DLI < 0.90', d: player.normal },
        { name: 'T2: Medium Leverage', range: '0.90 ≤ DLI < 1.35', d: player.t2 },
        { name: 'T3: High Leverage', range: '1.35 ≤ DLI < 2.25', d: player.t3 },
        { name: 'T4: Extreme Crunch', range: 'DLI ≥ 2.25', d: player.t4 },
        { name: 'Combined Pressure (T2–4)', range: 'DLI ≥ 0.90', d: player.pressure },
        { name: 'High Pressure (T3–4)', range: 'DLI ≥ 1.35', d: player.high }
      ];

      tbody.innerHTML = rows.map(r => `
        <tr style="${r.name.includes('Combined') ? 'font-weight:700; background:var(--surface-soft);' : ''}">
          <td>${r.name}</td>
          <td style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-secondary);">${r.range}</td>
          <td class="num-col">${r.d.balls.toLocaleString()} (${(r.d.balls / 6).toFixed(1)} ov)</td>
          <td class="num-col">${r.d.runs.toLocaleString()}</td>
          <td class="num-col" style="font-weight:700; color:${r.d.balls > 0 && r.d.econ <= 7.5 ? 'var(--primary)' : 'inherit'};">
            ${r.d.balls > 0 ? r.d.econ.toFixed(2) : '—'}
          </td>
          <td class="num-col">${r.d.wkts}</td>
          <td class="num-col">${r.d.balls > 0 && r.d.wkts > 0 ? r.d.sr.toFixed(1) : '—'}</td>
          <td class="num-col">${r.d.balls > 0 ? r.d.dot_pct.toFixed(2) + '%' : '—'}</td>
        </tr>
      `).join('');
    }
  }

  // 10. Render Chart.js Visualizations (Mandated Vibrant Rajasthan Royals Pink Palette)
  function renderCharts(player, isBatter) {
    if (typeof Chart === 'undefined') {
      console.warn('Chart.js not loaded. Skipping canvas renders.');
      return;
    }

    const isDark = state.theme === 'dark';
    const textColor = isDark ? '#D4C3D8' : '#746779';
    const gridColor = isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(244, 214, 228, 0.7)';
    const primaryPink = '#EA1A7A'; // Vibrant RR Jersey Pink
    const fillPink = 'rgba(234, 26, 122, 0.12)';

    // Chart 1: Tier Progression Line Chart
    const ctx1 = document.getElementById('chartTierProgression');
    if (ctx1) {
      if (state.charts.tierChart) state.charts.tierChart.destroy();

      const labels = ['T1: Low', 'T2: Med', 'T3: High', 'T4: Ext'];
      const values = isBatter
        ? [player.normal.sr, player.t2.sr, player.t3.sr, player.t4.balls > 0 ? player.t4.sr : null]
        : [player.normal.econ, player.t2.econ, player.t3.econ, player.t4.balls > 0 ? player.t4.econ : null];

      const metricLabel = isBatter ? 'Strike Rate' : 'Economy Rate (RPO)';

      state.charts.tierChart = new Chart(ctx1, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: metricLabel,
            data: values,
            borderColor: primaryPink,
            backgroundColor: fillPink,
            fill: true,
            tension: 0.25,
            borderWidth: 2.5,
            pointBackgroundColor: '#FFFFFF',
            pointBorderColor: primaryPink,
            pointBorderWidth: 2,
            pointRadius: 4.5
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: isDark ? '#2C1933' : '#31243A',
              titleFont: { family: 'Inter', size: 12 },
              bodyFont: { family: 'JetBrains Mono', size: 12 }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { family: 'Inter', size: 11 } }
            },
            y: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { family: 'Inter', size: 11 } }
            }
          }
        }
      });
    }

    // Chart 2: Boundary % vs Dot % Composition Bar Chart
    const ctx2 = document.getElementById('chartComposition');
    if (ctx2) {
      if (state.charts.boundaryChart) state.charts.boundaryChart.destroy();

      const labels = ['Normal (T1)', 'Pressure (T2–4)', 'High (T3–4)'];
      const bndData = [player.normal.bnd_pct, player.pressure.bnd_pct, player.high.bnd_pct];
      const dotData = [player.normal.dot_pct, player.pressure.dot_pct, player.high.dot_pct];

      state.charts.boundaryChart = new Chart(ctx2, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            {
              label: isBatter ? 'Boundary %' : 'Bnd Conceded %',
              data: bndData,
              backgroundColor: primaryPink,
              borderRadius: 4
            },
            {
              label: 'Dot Ball %',
              data: dotData,
              backgroundColor: isDark ? '#96899A' : '#746779',
              borderRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              labels: {
                color: textColor,
                boxWidth: 12,
                font: { family: 'Inter', size: 11 }
              }
            },
            tooltip: {
              backgroundColor: isDark ? '#2C1933' : '#31243A',
              titleFont: { family: 'Inter', size: 12 },
              bodyFont: { family: 'JetBrains Mono', size: 12 }
            }
          },
          scales: {
            x: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { family: 'Inter', size: 11 } }
            },
            y: {
              grid: { color: gridColor },
              ticks: { color: textColor, font: { family: 'Inter', size: 11 } }
            }
          }
        }
      });
    }
  }

  function updateChartsTheme() {
    renderPlayerExplorer();
  }

  // 11. Event Listeners Setup
  function setupEvents() {
    // Theme toggle
    if (themeToggleBtn) {
      themeToggleBtn.addEventListener('click', toggleTheme);
    }

    // Mobile menu toggle
    if (mobileMenuBtn && mobileNavDrawer) {
      mobileMenuBtn.addEventListener('click', () => {
        mobileNavDrawer.classList.toggle('open');
      });
    }

    // Brand logo returns to overview
    if (brandLogo) {
      brandLogo.addEventListener('click', () => switchTab('overview'));
    }

    // Nav links
    navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetTab = link.getAttribute('data-tab');
        if (targetTab) switchTab(targetTab);
      });
    });

    // Overview buttons & links
    if (heroBtnBatters) heroBtnBatters.addEventListener('click', () => switchTab('batters'));
    if (heroBtnBowlers) heroBtnBowlers.addEventListener('click', () => switchTab('bowlers'));
    if (heroBtnExplorer) heroBtnExplorer.addEventListener('click', () => switchTab('explorer'));
    if (previewLinkBatters) previewLinkBatters.addEventListener('click', () => switchTab('batters'));
    if (previewLinkBowlers) previewLinkBowlers.addEventListener('click', () => switchTab('bowlers'));

    // Search input
    if (explorerSearchInput) {
      explorerSearchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value;
        renderPlayerPickerList();
      });
    }

    // Filter pills
    explorerFilterBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        explorerFilterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.activeDisciplineFilter = btn.getAttribute('data-filter');
        renderPlayerPickerList();
      });
    });

    // Delegate table and featured action clicks (Analyze -> switches to Explorer)
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-table-action');
      if (btn) {
        const pid = parseInt(btn.getAttribute('data-player-id'), 10);
        const type = btn.getAttribute('data-type');
        if (pid && type) {
          state.selectedPlayerId = pid;
          state.selectedPlayerType = type;
          switchTab('explorer');
        }
      }
    });
  }

  // 12. Application Initialization
  function init() {
    initTheme();
    setupEvents();
    renderBattersLeaderboard();
    renderBowlersLeaderboard();
    renderPlayerPickerList();
    renderPlayerExplorer();

    // Check initial hash route (e.g. #batters, #bowlers, #explorer, #methodology)
    const hash = window.location.hash.replace('#', '');
    if (['overview', 'batters', 'bowlers', 'explorer', 'methodology'].includes(hash)) {
      switchTab(hash);
    }

    console.log('RR ScoutIQ Analytics Platform initialized (Vibrant RR Pink & Light Mode).');
  }

  // Listen to hash changes for deep linking
  window.addEventListener('hashchange', () => {
    const hash = window.location.hash.replace('#', '');
    if (['overview', 'batters', 'bowlers', 'explorer', 'methodology'].includes(hash)) {
      switchTab(hash);
    }
  });

  // Launch on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

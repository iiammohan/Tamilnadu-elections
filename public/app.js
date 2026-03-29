/* === TN Elections 2026 Dashboard — App Logic === */

const PARTY_COLORS = {
  'DMK': '#c41e3a', 'AIADMK': '#0d8c3f', 'INC': '#19769f', 'BJP': '#ff6b00',
  'PMK': '#e6c200', 'VCK': '#8b1a8b', 'CPI(M)': '#cc0000', 'CPI': '#cc0033',
  'DMDK': '#003366', 'MDMK': '#006633', 'IUML': '#009933', 'AMMK': '#228b22',
  'TMC(M)': '#336699', 'NTK': '#cc3300', 'KMDK': '#996633', 'TVK': '#5c2d91',
  'Others': '#888'
};

function getPartyColor(party) {
  return PARTY_COLORS[party] || '#888';
}

function formatNum(n) {
  return n ? n.toLocaleString('en-IN') : '0';
}

/* === Theme === */
function toggleTheme() {
  document.body.classList.toggle('dark');
  updateChartColors();
}
// Init from system preference
if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
  document.body.classList.add('dark');
}

/* === Tabs === */
function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.add('active');
  if (tab === 'table' && !tableBuilt) buildTable();
  if (tab === 'overview' && !chartsBuilt) buildCharts();
}

/* === D3 Map === */
let geoData = null;
let mapSvg, mapG, projection, pathGen;
let currentHighlight = null;

async function initMap() {
  const resp = await fetch('tn_constituencies.geojson');
  geoData = await resp.json();

  const container = document.getElementById('mapSvg');
  const w = container.clientWidth;
  const h = container.clientHeight || w * 1.33;

  mapSvg = d3.select('#mapSvg').append('svg')
    .attr('viewBox', `0 0 ${w} ${h}`)
    .attr('preserveAspectRatio', 'xMidYMid meet');

  mapG = mapSvg.append('g');

  projection = d3.geoMercator().fitSize([w * 0.88, h * 0.92], geoData);
  // Center the map in the container
  const [[x0, y0], [x1, y1]] = d3.geoPath().projection(projection).bounds(geoData);
  const mapW = x1 - x0;
  const offsetX = (w - mapW) / 2 - x0;
  projection.translate([projection.translate()[0] + offsetX, projection.translate()[1]]);
  pathGen = d3.geoPath().projection(projection);

  // Draw constituencies
  mapG.selectAll('path')
    .data(geoData.features)
    .join('path')
    .attr('d', pathGen)
    .attr('class', 'constituency')
    .attr('stroke', 'var(--bg)')
    .attr('stroke-width', 0.5)
    .attr('cursor', 'pointer')
    .on('mouseover', handleMouseOver)
    .on('mousemove', handleMouseMove)
    .on('mouseout', handleMouseOut)
    .on('click', handleClick);

  // Zoom
  const zoom = d3.zoom()
    .scaleExtent([1, 12])
    .on('zoom', (e) => mapG.attr('transform', e.transform));
  mapSvg.call(zoom);

  updateMapColoring();
}

function getConstData(acNo) {
  return CONSTITUENCIES.find(c => c.ac === acNo);
}

function updateMapColoring() {
  const mode = document.getElementById('mapColorMode').value;
  const legend = document.getElementById('mapLegend');
  const partiesUsed = new Set();

  mapG.selectAll('path').each(function(d) {
    const acNo = d.properties.ac_no;
    const c = getConstData(acNo);
    let color = '#ddd';
    let party = '';

    if (mode === '2021' && c) {
      party = c.w21;
      color = getPartyColor(party);
    } else if (mode === 'generic') {
      // Neutral color for generic constituency map
      color = '#7fb3d3';
    }
    if (party) partiesUsed.add(party);
    d3.select(this).attr('fill', color).attr('fill-opacity', 0.85);
  });

  // Update legend
  if (mode === 'generic') {
    legend.innerHTML = '<span class="legend-item"><span class="legend-swatch" style="background:#7fb3d3"></span>Constituency</span>';
  } else {
    legend.innerHTML = Array.from(partiesUsed).sort().map(p =>
      `<span class="legend-item"><span class="legend-swatch" style="background:${getPartyColor(p)}"></span>${p}</span>`
    ).join('');
  }
}

function handleMouseOver(e, d) {
  const c = getConstData(d.properties.ac_no);
  if (!c) return;
  const mode = document.getElementById('mapColorMode').value;
  let partyInfo = '';
  if (mode === '2021') partyInfo = `<span class="tt-party">2021 Winner: ${c.w21}</span>`;
  else partyInfo = `<span class="tt-party">District: ${c.d}</span>`;

  document.getElementById('tooltip').innerHTML =
    `<strong>AC ${c.ac}: ${c.n}</strong><br>${partyInfo}<br>Voters: ${formatNum(c.t)}`;
  document.getElementById('tooltip').style.display = 'block';
  d3.select(this).attr('stroke', '#fff').attr('stroke-width', 2).attr('fill-opacity', 1);
}

function handleMouseMove(e) {
  const tt = document.getElementById('tooltip');
  tt.style.left = (e.clientX + 14) + 'px';
  tt.style.top = (e.clientY - 10) + 'px';
}

function handleMouseOut(e, d) {
  document.getElementById('tooltip').style.display = 'none';
  d3.select(this).attr('stroke', 'var(--bg)').attr('stroke-width', 0.5).attr('fill-opacity', 0.85);
  if (currentHighlight) {
    d3.select(currentHighlight).attr('stroke', 'var(--accent)').attr('stroke-width', 3);
  }
}

function handleClick(e, d) {
  const c = getConstData(d.properties.ac_no);
  if (c) openDetailPanel(c, d.properties.district);
}

function highlightConstituency(acNo) {
  // Remove old highlight
  if (currentHighlight) {
    d3.select(currentHighlight).attr('stroke', 'var(--bg)').attr('stroke-width', 0.5);
  }
  mapG.selectAll('path').each(function(d) {
    if (d.properties.ac_no === acNo) {
      currentHighlight = this;
      d3.select(this).attr('stroke', 'var(--accent)').attr('stroke-width', 3).raise();
      // Zoom to it
      const [[x0, y0], [x1, y1]] = pathGen.bounds(d);
      const svgEl = mapSvg.node();
      const vb = svgEl.viewBox.baseVal;
      const dx = x1 - x0, dy = y1 - y0;
      const x = (x0 + x1) / 2, y = (y0 + y1) / 2;
      const scale = Math.min(8, 0.8 / Math.max(dx / vb.width, dy / vb.height));
      const translate = [vb.width / 2 - scale * x, vb.height / 2 - scale * y];
      mapSvg.transition().duration(750).call(
        d3.zoom().scaleExtent([1, 12]).on('zoom', (e) => mapG.attr('transform', e.transform))
          .transform,
        d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
      );
    }
  });
}

/* === Search === */
function searchConstituency(query) {
  const box = document.getElementById('searchResults');
  if (!query || query.length < 2) { box.classList.remove('active'); return; }
  const q = query.toLowerCase();
  const matches = CONSTITUENCIES.filter(c =>
    c.n.toLowerCase().includes(q) || c.d.toLowerCase().includes(q) || String(c.ac).includes(q)
  ).slice(0, 10);

  if (!matches.length) { box.classList.remove('active'); return; }
  box.innerHTML = matches.map(c =>
    `<div class="search-result-item" onclick="selectSearchResult(${c.ac})">
      <div class="sr-name">AC ${c.ac}: ${c.n}</div>
      <div class="sr-meta">${c.d} · ${formatNum(c.t)} voters</div>
    </div>`
  ).join('');
  box.classList.add('active');
}

function selectSearchResult(acNo) {
  document.getElementById('searchResults').classList.remove('active');
  document.getElementById('mapSearch').value = '';
  highlightConstituency(acNo);
  const c = getConstData(acNo);
  const geo = geoData.features.find(f => f.properties.ac_no === acNo);
  if (c) openDetailPanel(c, geo ? geo.properties.district : c.d);
}

// Close search on click outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-bar')) {
    document.querySelectorAll('.search-results').forEach(r => r.classList.remove('active'));
  }
});

/* === Detail Panel === */
function openDetailPanel(c, district) {
  const panel = document.getElementById('detailPanel');
  const content = document.getElementById('panelContent');

  content.innerHTML = `
    <div class="panel-header">
      <h2>${c.n}</h2>
      <div class="panel-ac">AC ${c.ac} · ${district || c.d}</div>
    </div>
    <div class="panel-section">
      <h4>Voter Demographics</h4>
      <div class="panel-grid">
        <div class="panel-stat"><div class="ps-value">${formatNum(c.t)}</div><div class="ps-label">Total</div></div>
        <div class="panel-stat"><div class="ps-value">${formatNum(c.m)}</div><div class="ps-label">Male</div></div>
        <div class="panel-stat"><div class="ps-value">${formatNum(c.f)}</div><div class="ps-label">Female</div></div>
        <div class="panel-stat"><div class="ps-value">${formatNum(c.tg)}</div><div class="ps-label">Third Gender</div></div>
      </div>
    </div>
    <div class="panel-section">
      <h4>2026 Candidates</h4>
      <div class="panel-candidate">
        <div class="pc-dot" style="background:${getPartyColor(c.sp)}"></div>
        <div>
          <div class="pc-name">${c.sc || 'TBA'}</div>
          <div class="pc-party">SPA · ${c.sp}</div>
        </div>
      </div>
      <div class="panel-candidate">
        <div class="pc-dot" style="background:${getPartyColor(c.np)}"></div>
        <div>
          <div class="pc-name">${c.nc || 'TBA'}</div>
          <div class="pc-party">NDA · ${c.np}</div>
        </div>
      </div>
      <div class="panel-candidate">
        <div class="pc-dot" style="background:${getPartyColor('TVK')}"></div>
        <div>
          <div class="pc-name">${c.tc || 'TBA'}</div>
          <div class="pc-party">TVK</div>
        </div>
      </div>
      <div class="panel-candidate">
        <div class="pc-dot" style="background:${getPartyColor('NTK')}"></div>
        <div>
          <div class="pc-name">${c.nkc || 'TBA'}</div>
          <div class="pc-party">NTK</div>
        </div>
      </div>
    </div>
    <div class="panel-section">
      <h4>2021 Election</h4>
      <div class="panel-candidate">
        <div class="pc-dot" style="background:${getPartyColor(c.w21)}"></div>
        <div>
          <div class="pc-name">Winner: ${c.w21}</div>
          <div class="pc-party">2021 Assembly Election</div>
        </div>
      </div>
    </div>
  `;

  panel.classList.add('open');
}

function closePanel() {
  document.getElementById('detailPanel').classList.remove('open');
}

/* === Table === */
let tableBuilt = false;
let tableData = [];
let sortCol = 0;
let sortAsc = true;

function buildTable() {
  tableData = CONSTITUENCIES.map(c => [
    c.ac, c.n, c.d, c.t, c.m, c.f, c.tg, c.w21, c.sp, c.sc, c.np, c.nc, c.tc, c.nkc
  ]);
  renderTable(tableData);
  tableBuilt = true;
}

function renderTable(data) {
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = data.map(r => {
    const partyBg = getPartyColor(r[7]);
    return `<tr onclick="tableRowClick(${r[0]})">
      <td>${r[0]}</td>
      <td><strong>${r[1]}</strong></td>
      <td>${r[2]}</td>
      <td class="num">${formatNum(r[3])}</td>
      <td class="num">${formatNum(r[4])}</td>
      <td class="num">${formatNum(r[5])}</td>
      <td class="num">${formatNum(r[6])}</td>
      <td><span class="party-badge" style="background:${partyBg}">${r[7]}</span></td>
      <td><span class="party-badge" style="background:${getPartyColor(r[8])}">${r[8]}</span></td>
      <td>${r[9] || '<em style="color:var(--text-faint)">TBA</em>'}</td>
      <td><span class="party-badge" style="background:${getPartyColor(r[10])}">${r[10]}</span></td>
      <td>${r[11] || '<em style="color:var(--text-faint)">TBA</em>'}</td>
      <td><span class="party-badge" style="background:${getPartyColor('TVK')}">${r[12] || 'TBA'}</span></td>
      <td><span class="party-badge" style="background:${getPartyColor('NTK')}">${r[13] || 'TBA'}</span></td>
    </tr>`;
  }).join('');
}

function filterTable(query) {
  if (!query) { renderTable(tableData); return; }
  const q = query.toLowerCase();
  const filtered = tableData.filter(r =>
    r.some(cell => String(cell).toLowerCase().includes(q))
  );
  renderTable(filtered);
}

function sortTable(col) {
  if (sortCol === col) sortAsc = !sortAsc;
  else { sortCol = col; sortAsc = true; }
  tableData.sort((a, b) => {
    let va = a[col], vb = b[col];
    if (typeof va === 'number') return sortAsc ? va - vb : vb - va;
    va = String(va).toLowerCase();
    vb = String(vb).toLowerCase();
    return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  renderTable(tableData);
}

function tableRowClick(acNo) {
  const c = getConstData(acNo);
  if (c) openDetailPanel(c, c.d);
}

/* === Charts === */
let chartsBuilt = false;
let chartInstances = {};

function getChartTextColor() {
  return document.body.classList.contains('dark') ? '#a09a90' : '#6b6560';
}
function getChartGridColor() {
  return document.body.classList.contains('dark') ? '#333' : '#e0dcd4';
}

function buildCharts() {
  const textColor = getChartTextColor();
  const gridColor = getChartGridColor();

  Chart.defaults.font.family = "'General Sans', sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.color = textColor;

  // 2021 Results Bar Chart
  const results = { DMK: 133, AIADMK: 66, INC: 18, PMK: 5, VCK: 4, BJP: 4, 'CPI(M)': 2, CPI: 2 };
  chartInstances.results = new Chart(document.getElementById('results2021Chart'), {
    type: 'bar',
    data: {
      labels: Object.keys(results),
      datasets: [{
        data: Object.values(results),
        backgroundColor: Object.keys(results).map(p => getPartyColor(p)),
        borderRadius: 4,
        maxBarThickness: 50,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.label}: ${ctx.raw} seats`
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: { color: textColor }
        },
        x: {
          grid: { display: false },
          ticks: { color: textColor, font: { weight: 600 } }
        }
      }
    }
  });

  // Gender Breakdown Donut
  const totalMale = CONSTITUENCIES.reduce((s, c) => s + c.m, 0);
  const totalFemale = CONSTITUENCIES.reduce((s, c) => s + c.f, 0);
  const totalTG = CONSTITUENCIES.reduce((s, c) => s + c.tg, 0);
  chartInstances.gender = new Chart(document.getElementById('genderChart'), {
    type: 'doughnut',
    data: {
      labels: ['Male', 'Female', 'Third Gender'],
      datasets: [{
        data: [totalMale, totalFemale, totalTG],
        backgroundColor: ['#19769f', '#c41e3a', '#e6c200'],
        borderWidth: 2,
        borderColor: document.body.classList.contains('dark') ? '#1e1e1e' : '#fff',
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: { position: 'bottom', labels: { padding: 16, color: textColor, usePointStyle: true, pointStyleWidth: 10 } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const pct = ((ctx.raw / (totalMale + totalFemale + totalTG)) * 100).toFixed(1);
              return `${ctx.label}: ${formatNum(ctx.raw)} (${pct}%)`;
            }
          }
        }
      }
    }
  });

  // SPA Pie
  const spa = { DMK: 164, INC: 28, DMDK: 10, VCK: 8, 'CPI(M)': 5, CPI: 5, MDMK: 3, IUML: 2, KMDK: 2, Others: 7 };
  chartInstances.spa = new Chart(document.getElementById('spaChart'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(spa),
      datasets: [{
        data: Object.values(spa),
        backgroundColor: Object.keys(spa).map(p => getPartyColor(p)),
        borderWidth: 2,
        borderColor: document.body.classList.contains('dark') ? '#1e1e1e' : '#fff',
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '40%',
      plugins: {
        legend: { position: 'bottom', labels: { padding: 10, color: textColor, usePointStyle: true, pointStyleWidth: 8, font: { size: 10 } } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.raw} seats` } }
      }
    }
  });

  // NDA Pie
  const nda = { AIADMK: 166, BJP: 25, PMK: 18, AMMK: 11, 'TMC(M)': 5, Others: 9 };
  chartInstances.nda = new Chart(document.getElementById('ndaChart'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(nda),
      datasets: [{
        data: Object.values(nda),
        backgroundColor: Object.keys(nda).map(p => getPartyColor(p)),
        borderWidth: 2,
        borderColor: document.body.classList.contains('dark') ? '#1e1e1e' : '#fff',
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '40%',
      plugins: {
        legend: { position: 'bottom', labels: { padding: 10, color: textColor, usePointStyle: true, pointStyleWidth: 8, font: { size: 10 } } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.raw} seats` } }
      }
    }
  });

  chartsBuilt = true;
}

function updateChartColors() {
  if (!chartsBuilt) return;
  const tc = getChartTextColor();
  const gc = getChartGridColor();
  const borderC = document.body.classList.contains('dark') ? '#1e1e1e' : '#fff';

  Object.values(chartInstances).forEach(chart => {
    chart.options.plugins.legend.labels.color = tc;
    if (chart.options.scales) {
      if (chart.options.scales.y) { chart.options.scales.y.grid.color = gc; chart.options.scales.y.ticks.color = tc; }
      if (chart.options.scales.x) { chart.options.scales.x.ticks.color = tc; }
    }
    chart.data.datasets.forEach(ds => {
      if (ds.borderColor && typeof ds.borderColor === 'string' && (ds.borderColor === '#fff' || ds.borderColor === '#1e1e1e')) {
        ds.borderColor = borderC;
      }
    });
    chart.update('none');
  });
}

/* === Init === */
document.addEventListener('DOMContentLoaded', () => {
  initMap();
});

"""
Build market regimes HTML section.
Generates report/output/market_regimes.html
"""

import json, os
import pandas as pd
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')

QUADRANTS = {
    'Q1': ('Growth + Low Inflation', '#60a5fa', 'Stocks up, bonds stable, gold flat. Best for: Total Market, SCV.'),
    'Q2': ('Growth + High Inflation', '#c084fc', 'Stocks mixed, bonds down, gold up. Best for: Gold, SCV.'),
    'Q3': ('Stagnation + Low Inflation', '#67e8f9', 'Stocks down, bonds up, gold mixed. Best for: LT Bonds, ST Bonds.'),
    'Q4': ('Stagnation + High Inflation', '#f9a8d4', 'Stocks down, bonds down, gold up. Best for: Gold, ST Bonds.'),
}

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'output')

with open(os.path.join(DATA, 'regimes.json')) as f:
    regimes_data = json.load(f)

us_regimes = regimes_data['us']  # {"1950": {"q":"Q1","gdp":13.4,"infl":5.8}, ...}
eu_regimes = regimes_data['eu']
methodology = regimes_data['methodology']


def q_pill(q):
    label, color, _ = QUADRANTS[q]
    return (
        '<span class="q-pill" style="background:' + color + '20;color:' + color
        + ';border:1px solid ' + color + '40">' + q + '</span>'
    )


def build_quadrant_grid():
    items = ''
    for q in ['Q1', 'Q2', 'Q3', 'Q4']:
        label, color, desc = QUADRANTS[q]
        items += (
            '<div style="flex:1;padding:0.5rem 0.7rem;border-left:3px solid ' + color + ';min-width:140px">'
            '<div style="display:flex;align-items:center;gap:0.4rem;margin-bottom:0.2rem">'
            '<span class="q-pill" style="background:' + color + '20;color:' + color + ';border:1px solid ' + color + '40">' + q + '</span>'
            '<b style="font-size:0.82rem">' + label + '</b>'
            '</div>'
            '<div style="font-size:0.75rem;color:var(--muted)">' + desc + '</div>'
            '</div>'
        )
    return '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin:1rem 0">' + items + '</div>'


Q_COLORS = {'Q1': '#60a5fa', 'Q2': '#c084fc', 'Q3': '#67e8f9', 'Q4': '#f9a8d4'}
Q_LABELS = {'Q1': 'Growth + Low Inflation', 'Q2': 'Growth + High Inflation',
            'Q3': 'Stagnation + Low Inflation', 'Q4': 'Stagnation + High Inflation'}
MIN_YR, MAX_YR = 1950, 2026


def year_to_quadrant(yr, region):
    r = us_regimes if region == 'us' else eu_regimes
    d = r.get(str(yr))
    return d['q'] if d else 'Q1'


def build_regime_bar(region):
    span = MAX_YR - MIN_YR
    def pct(yr): return round((yr - MIN_YR) / span * 100, 2)
    bars = ''
    for yr in range(MIN_YR, MAX_YR):
        q = year_to_quadrant(yr, region)
        color = Q_COLORS[q]
        bars += ('<div style="position:absolute;left:' + str(pct(yr)) + '%;'
                 'width:' + str(pct(yr + 1) - pct(yr)) + '%;height:100%;'
                 'background:' + color + ';opacity:0.5;"'
                 ' title="' + str(yr) + ': ' + q + '"></div>')
    ticks = ''
    for yr in range(1960, MAX_YR, 10):
        ticks += ('<span style="position:absolute;left:' + str(pct(yr)) + '%;'
                  'transform:translateX(-50%);font-size:0.62rem;color:#64748b;top:2px;">' + str(yr) + '</span>')
    ticks += '<span style="position:absolute;left:0%;font-size:0.62rem;color:#64748b;top:2px;">' + str(MIN_YR) + '</span>'
    ticks += '<span style="position:absolute;right:0%;font-size:0.62rem;color:#64748b;top:2px;">' + str(MAX_YR) + '</span>'
    legend = ''.join(
        '<span style="display:inline-flex;align-items:center;gap:0.3rem;font-size:0.72rem;color:#94a3b8">'
        '<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + Q_COLORS[q] + ';opacity:0.7"></span>'
        + q + '</span>'
        for q in ['Q1', 'Q2', 'Q3', 'Q4']
    )
    return (
        '<div style="margin:1rem 0 0.3rem">'
        '<div style="position:relative;height:14px;border-radius:4px;overflow:hidden;background:rgba(255,255,255,0.04)">' + bars + '</div>'
        '<div style="position:relative;height:16px;">' + ticks + '</div>'
        '<div style="display:flex;gap:1rem;margin-top:0.3rem">' + legend + '</div>'
        '</div>'
    )


def build_table(region):
    r = us_regimes if region == 'us' else eu_regimes
    rows = ''
    for yr in range(MIN_YR, MAX_YR):
        d = r.get(str(yr))
        if not d:
            continue
        q = d['q']
        gdp_src = d.get('gdp_source', 'bea') if region == 'eu' else 'bea'
        infl_src = d.get('infl_source', 'bls') if region == 'eu' else 'bls'
        proxy_note = ' *' if (gdp_src == 'us_proxy' or infl_src == 'us_proxy') else ''
        rows += (
            '<tr>'
            '<td>' + str(yr) + proxy_note + '</td>'
            '<td>' + q_pill(q) + '</td>'
            '<td class="regime-num">' + ('+' if d['gdp'] > 0 else '') + str(d['gdp']) + '%</td>'
            '<td class="regime-num">' + str(d['infl']) + '%</td>'
            '</tr>'
        )
    infl_label = 'CPI' if region == 'us' else 'HICP'
    return (
        '<table class="regime-table">'
        '<thead><tr><th>Year</th><th>Regime</th><th>GDP YoY</th><th>' + infl_label + ' YoY</th></tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
        '<p style="font-size:0.75rem;color:var(--muted);margin-top:0.3rem">* EU data unavailable; US proxy used.</p>'
    )


def build_comparison_table():
    rows = ''
    for yr in range(MIN_YR, MAX_YR):
        us_d = us_regimes.get(str(yr))
        eu_d = eu_regimes.get(str(yr))
        if not us_d:
            continue
        us_q = us_d['q']
        eu_q = eu_d['q'] if eu_d else '—'
        diff = ' class="regime-diff"' if eu_d and us_q != eu_q else ''
        eu_cell = q_pill(eu_q) if eu_d else '<span style="color:var(--muted)">—</span>'
        rows += (
            '<tr' + diff + '>'
            '<td>' + str(yr) + '</td>'
            '<td>' + q_pill(us_q) + '</td>'
            '<td>' + eu_cell + '</td>'
            '<td class="regime-num">' + ('+' if us_d['gdp'] > 0 else '') + str(us_d['gdp']) + '%</td>'
            '<td class="regime-num">' + str(us_d['infl']) + '%</td>'
            '</tr>'
        )
    return (
        '<table class="regime-table">'
        '<thead><tr><th>Year</th><th>US</th><th>EU</th><th>US GDP</th><th>US CPI</th></tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
    )


# ── Metrics computation ──────────────────────────────────────

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'output')
prices = pd.read_pickle(os.path.join(DATA, 'proxy_prices.pkl'))

COMPONENTS = {
    'us': {
        'Total Market': 'us_tm_gspc',
        'Small Cap Value': 'us_scv_gspc2',
        'LT Bonds': 'us_lt_model',
        'ST Bonds': 'us_st_model',
        'Gold': 'us_gold_synth',
    },
    'eu': {
        'Total Market': 'eu_tm_spliced',
        'Small Cap Value': 'eu_scv_naesx_eur',
        'LT Bonds': 'us_lt_model',
        'ST Bonds': 'us_st_model',
        'Gold': 'us_gold_synth',
    },
}

ETF_COMPONENTS = {
    'us': {
        'Total Market': 'us_tm_vti',
        'Small Cap Value': 'us_scv_vbr',
        'LT Bonds': 'us_lt_tlt',
        'ST Bonds': 'us_st_shy',
        'Gold': 'us_gold_gld',
    },
    'eu': {
        'Total Market': 'eu_tm_iwda',
        'Small Cap Value': 'eu_scv_iusn',
        'LT Bonds': 'eu_lt_dtla',
        'ST Bonds': 'eu_st_ibta',
        'Gold': 'eu_gold_igln',
    },
}




def compute_annual(region, comp_map=None):
    comps = comp_map or COMPONENTS[region]
    result = {}
    for comp, col in comps.items():
        s = prices[col].dropna()
        annual = {}
        for yr in range(1950, 2026):
            sy = s[s.index.year == yr]
            if len(sy) < 20:
                continue
            ret = (sy.iloc[-1] / sy.iloc[0] - 1) * 100
            annual[yr] = round(ret, 1)
        result[comp] = annual
    return result


def build_charts_json(region, comp_map=None, y_range=None):
    annual = compute_annual(region, comp_map)
    comps = list((comp_map or COMPONENTS[region]).keys())
    all_years = set()
    for comp in comps:
        all_years.update(annual[comp].keys())
    years = sorted(all_years)
    qs = [year_to_quadrant(yr, region) for yr in years]

    cagr_matrix = []
    for comp in comps:
        row = [annual[comp].get(yr) for yr in years]
        cagr_matrix.append(row)

    result = {
        'comps': comps, 'years': years, 'qs': qs,
        'cagr': cagr_matrix,
        'q_colors': Q_COLORS,
    }
    if y_range:
        result['y_range'] = y_range
    return result


def compute_global_y_range():
    """Compute global min/max across all regions and proxy/etf."""
    all_vals = []
    for region in ['us', 'eu']:
        for comp_map in [COMPONENTS[region], ETF_COMPONENTS[region]]:
            annual = compute_annual(region, comp_map)
            for comp in annual:
                all_vals.extend(v for v in annual[comp].values() if v is not None)
    mn = min(all_vals)
    mx = max(all_vals)
    pad = (mx - mn) * 0.05
    return [round(mn - pad, 0), round(mx + pad, 0)]


global_y_range = compute_global_y_range()
us_proxy_data = build_charts_json('us', y_range=global_y_range)
us_etf_data = build_charts_json('us', ETF_COMPONENTS['us'], y_range=global_y_range)
eu_proxy_data = build_charts_json('eu', y_range=global_y_range)
eu_etf_data = build_charts_json('eu', ETF_COMPONENTS['eu'], y_range=global_y_range)
us_proxy_json = json.dumps(us_proxy_data, separators=(',', ':'))
us_etf_json = json.dumps(us_etf_data, separators=(',', ':'))
eu_proxy_json = json.dumps(eu_proxy_data, separators=(',', ':'))
eu_etf_json = json.dumps(eu_etf_data, separators=(',', ':'))


def build_macro_chart_json(region):
    """Build JSON for GDP + CPI time series chart with thresholds."""
    r = us_regimes if region == 'us' else eu_regimes
    years = sorted(int(y) for y in r.keys())
    gdp_vals = [r[str(y)]['gdp'] for y in years]
    infl_vals = [r[str(y)]['infl'] for y in years]
    qs = [r[str(y)]['q'] for y in years]
    if region == 'us':
        gdp_thresh = methodology['us_thresholds']['gdp_median']
        infl_thresh = methodology['us_thresholds']['cpi_median']
    else:
        gdp_thresh = methodology['eu_thresholds']['gdp_median']
        infl_thresh = methodology['eu_thresholds']['hicp_median']
    return json.dumps({
        'years': years, 'gdp': gdp_vals, 'infl': infl_vals, 'qs': qs,
        'gdp_thresh': gdp_thresh, 'infl_thresh': infl_thresh,
        'q_colors': Q_COLORS,
    }, separators=(',', ':'))


us_macro_json = build_macro_chart_json('us')
eu_macro_json = build_macro_chart_json('eu')


CSS = """
  :root {
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Inter", -apple-system, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6;
    padding: 2rem;
  }
  h2 {
    font-size: 1.4rem; margin: 2rem 0 0.5rem;
    border-left: 4px solid var(--accent); padding-left: 0.8rem;
  }
  h3 { font-size: 1.1rem; color: var(--accent); margin: 1.5rem 0 0.3rem; }
  p, .subtitle { color: var(--muted); font-size: 0.9rem; margin-bottom: 1rem; }
  .section {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0;
  }
  .note {
    background: rgba(59,130,246,0.06); border: 1px solid rgba(59,130,246,0.15);
    border-radius: 8px; padding: 0.8rem; margin: 1rem 0; font-size: 0.85rem;
    color: var(--muted);
  }

  /* Quadrant grid */
  .q-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem;
    margin: 1rem 0;
  }
  .q-card {
    background: rgba(255,255,255,0.02); border: 1px solid var(--border);
    border-radius: 8px; padding: 0.7rem 0.9rem;
  }
  .q-card-head { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.3rem; }
  .q-card-desc { font-size: 0.8rem; color: var(--muted); }
  .q-pill {
    display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
    font-size: 0.75rem; font-weight: 700;
  }

  /* Regime table */
  .regime-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; margin: 1rem 0; }
  .regime-table th, .regime-table td {
    padding: 0.45rem 0.7rem; border-bottom: 1px solid var(--border); text-align: left;
  }
  .regime-table th { color: var(--accent); font-weight: 600; background: rgba(59,130,246,0.04); }
  .regime-table tr:hover td { background: rgba(59,130,246,0.04); }
  .regime-desc { color: var(--muted); font-size: 0.8rem; }
  .regime-num { font-family: monospace; font-size: 0.8rem; text-align: right; }
  .regime-diff { background: rgba(234,179,8,0.04); }

  .region { display: none; }
  .region.active { display: block; }

  /* Quadrant legend */
  .q-legend { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.8rem 0; }
  .q-legend-btn {
    display: flex; align-items: center; gap: 0.4rem;
    padding: 0.3rem 0.8rem; border-radius: 999px; cursor: pointer;
    border: 1px solid var(--qc); background: color-mix(in srgb, var(--qc) 12%, transparent);
    color: var(--text); font-size: 0.78rem; font-weight: 600; transition: all 0.15s;
  }
  .q-legend-btn:hover { background: color-mix(in srgb, var(--qc) 22%, transparent); }
  .q-legend-btn.q-legend-off {
    background: transparent; color: var(--muted);
    border-color: var(--border); opacity: 0.5;
  }
  .q-legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

  /* Tabs */
  .tabs { display: flex; gap: 0.25rem; margin: 0.8rem 0 0; border-bottom: 1px solid var(--border); }
  .tab-btn {
    padding: 0.35rem 0.9rem; border: none; background: none;
    color: var(--muted); font-size: 0.8rem; cursor: pointer;
    border-bottom: 2px solid transparent; margin-bottom: -1px; transition: all 0.15s;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
  .tab-panels { margin-top: 0.6rem; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
"""

JS = """
function applyRegion() {
  var region = window.location.hash.replace('#', '') || 'us';
  document.querySelectorAll('.region').forEach(function(el) {
    var isActive = el.dataset.region === region;
    el.classList.toggle('active', isActive);
    if (isActive) {
      allCompDivs = [];
      activeQs = {Q1:true, Q2:true, Q3:true, Q4:true};
      document.querySelectorAll('.q-legend-btn').forEach(function(b){ b.classList.remove('q-legend-off'); });
      setTimeout(function() {
        el.querySelectorAll('div[data-charts]').forEach(function(div) {
          // Skip charts inside hidden tab panels
          var panel = div.closest('.tab-panel');
          if (panel && !panel.classList.contains('active')) return;
          if (div.children.length === 0) {
            var d = JSON.parse(div.getAttribute('data-charts'));
            var mode = div.getAttribute('data-mode');
            if (mode === 'compbar') drawCompBar(div.id, d);
            else if (mode === 'qsummary') drawQSummary(div.id, d, div.getAttribute('data-metric') || 'return');
            else if (mode === 'macro') drawMacroChart(div.id, d);
          }
        });
      }, 50);
    }
  });
}
window.addEventListener('hashchange', applyRegion);
window.addEventListener('DOMContentLoaded', applyRegion);
if (document.readyState !== 'loading') applyRegion();

var Q_NAMES = {Q1:'Growth + Low Infl.', Q2:'Growth + High Infl.', Q3:'Stagnation + Low Infl.', Q4:'Stagnation + High Infl.'};
var activeQs = {Q1:true, Q2:true, Q3:true, Q4:true};
var allCompDivs = [];

function drawMacroChart(divId, d) {
  var years = d.years.map(String);
  // Background quadrant bands
  var shapes = [];
  var prevQ = null, segStart = 0;
  d.qs.forEach(function(q, i) {
    if (q !== prevQ && prevQ !== null) {
      shapes.push({type:'rect',xref:'x',yref:'paper',x0:years[segStart],x1:years[i],y0:0,y1:1,
        fillcolor:d.q_colors[prevQ],opacity:0.08,line:{width:0}});
      segStart = i;
    }
    prevQ = q;
  });
  shapes.push({type:'rect',xref:'x',yref:'paper',x0:years[segStart],x1:years[years.length-1],y0:0,y1:1,
    fillcolor:d.q_colors[prevQ],opacity:0.08,line:{width:0}});
  // GDP threshold line
  shapes.push({type:'line',xref:'paper',yref:'y',x0:0,x1:1,y0:d.gdp_thresh,y1:d.gdp_thresh,
    line:{color:'#60a5fa',width:1,dash:'dot'}});
  // Inflation threshold line
  shapes.push({type:'line',xref:'paper',yref:'y',x0:0,x1:1,y0:d.infl_thresh,y1:d.infl_thresh,
    line:{color:'#f9a8d4',width:1,dash:'dot'}});
  var traces = [
    {x:years, y:d.gdp, name:'GDP YoY', type:'scatter', mode:'lines+markers',
     line:{color:'#60a5fa',width:2}, marker:{size:3},
     customdata:d.qs,
     hovertemplate:'%{x} (%{customdata})<br>GDP: %{y:.1f}%<extra></extra>'},
    {x:years, y:d.infl, name:'CPI/HICP YoY', type:'scatter', mode:'lines+markers',
     line:{color:'#f9a8d4',width:2}, marker:{size:3},
     customdata:d.qs,
     hovertemplate:'%{x} (%{customdata})<br>Inflation: %{y:.1f}%<extra></extra>'}
  ];
  var annotations = [
    {x:1,y:d.gdp_thresh,xref:'paper',yref:'y',text:'GDP median '+d.gdp_thresh+'%',
     showarrow:false,font:{size:9,color:'#60a5fa'},xanchor:'right',yshift:8},
    {x:1,y:d.infl_thresh,xref:'paper',yref:'y',text:'CPI median '+d.infl_thresh+'%',
     showarrow:false,font:{size:9,color:'#f9a8d4'},xanchor:'right',yshift:-10}
  ];
  var layout = {
    paper_bgcolor:'transparent', plot_bgcolor:'#0a1628',
    font:{family:'Inter,sans-serif',color:'#94a3b8',size:11},
    margin:{t:10,r:20,b:35,l:45},
    xaxis:{tickfont:{size:9},dtick:5,gridcolor:'#1e293b',range:[years[0],years[years.length-1]]},
    yaxis:{ticksuffix:'%',gridcolor:'#1e293b',zeroline:true,zerolinecolor:'#334155',tickfont:{size:9}},
    legend:{bgcolor:'transparent',font:{size:10},orientation:'h',y:-0.12},
    shapes:shapes, annotations:annotations,
    hovermode:'x unified',
    hoverlabel:{bgcolor:'#1e293b',bordercolor:'#334155',font:{color:'#e2e8f0',size:11}}
  };
  Plotly.newPlot(divId, traces, layout, {displayModeBar:false, responsive:true, doubleClick:'reset+autosize'});
}

function drawQSummary(divId, d, metric) {
  var qs = ['Q1','Q2','Q3','Q4'];
  var axes = [{x:'x',y:'y'},{x:'x2',y:'y2'},{x:'x3',y:'y3'},{x:'x4',y:'y4'}];
  var nc = d.comps.length;
  var qd = d.all_data[metric];
  var qde = d.all_data_etf[metric];
  var suffix = d.metric_suffix[metric];
  var traces = [];
  qs.forEach(function(q, qi) {
    d.comps.forEach(function(comp, ci) {
      var vals = qd[q][comp] || [];
      var xp = ci * 3;
      var xe = ci * 3 + 1;
      traces.push({
        y: vals, x0: xp, type: 'box', name: comp+' (proxy)',
        boxmean: true, width: 0.7,
        marker: { color: d.comp_colors[ci], opacity: 0.8, size: 3 },
        line: { color: d.comp_colors[ci], width: 1.5 },
        fillcolor: d.comp_colors[ci] + '30',
        xaxis: axes[qi].x, yaxis: axes[qi].y,
        legendgroup: comp+'_p', showlegend: qi === 0,
        hoverinfo: 'y+name'
      });
      var vals_etf = qde[q][comp] || [];
      if (vals_etf.length > 0) {
        traces.push({
          y: vals_etf, x0: xe, type: 'box', name: comp+' (ETF)',
          boxmean: true, width: 0.7,
          marker: { color: d.comp_colors_etf[ci], opacity: 0.9, size: 3 },
          line: { color: d.comp_colors_etf[ci], width: 1.5, dash: 'dot' },
          fillcolor: d.comp_colors_etf[ci] + '20',
          xaxis: axes[qi].x, yaxis: axes[qi].y,
          legendgroup: comp+'_e', showlegend: qi === 0,
          hoverinfo: 'y+name'
        });
      }
    });
  });
  var tickvals = []; var ticktext = [];
  d.comps.forEach(function(comp, ci) { tickvals.push(ci*3+0.5); ticktext.push(comp); });
  var xrange = [-0.8, nc*3-0.2];
  var xaxisBase = {tickvals:tickvals,ticktext:ticktext,tickfont:{size:8},range:xrange,showgrid:false};
  var domains = [[0,0.48,0.55,0.96],[0.52,1,0.55,0.96],[0,0.48,0.04,0.45],[0.52,1,0.04,0.45]];
  var shapes = qs.map(function(q, qi) {
    var dm = domains[qi];
    return {type:'rect',xref:'paper',yref:'paper',x0:dm[0],x1:dm[1],y0:dm[2],y1:dm[3],
      line:{color:d.q_colors[q],width:2},fillcolor:'transparent'};
  });
  var annotations = qs.map(function(q, qi) {
    var dm = domains[qi];
    return {text:'<b>'+q+'</b>  '+d.q_labels[q],xref:'paper',yref:'paper',
      x:(dm[0]+dm[1])/2, y:dm[3], showarrow:false,
      xanchor:'center', yanchor:'bottom',
      font:{size:11,color:d.q_colors[q]}};
  });
  var yaxisBase = {ticksuffix:suffix,gridcolor:'#1e293b',zeroline:true,zerolinecolor:'#334155',tickfont:{size:8}};
  var layout = {
    paper_bgcolor:'transparent', plot_bgcolor:'#0a1628',
    font:{family:'Inter,sans-serif',color:'#94a3b8',size:10},
    height:600,
    margin:{t:50,r:15,b:50,l:45},
    showlegend:true,
    legend:{bgcolor:'transparent',font:{size:8},orientation:'h',y:-0.06,traceorder:'grouped'},
    xaxis:  Object.assign({domain:domains[0].slice(0,2),anchor:'y'},  xaxisBase),
    yaxis:  Object.assign({domain:domains[0].slice(2,4),anchor:'x'},  yaxisBase),
    xaxis2: Object.assign({domain:domains[1].slice(0,2),anchor:'y2'}, xaxisBase),
    yaxis2: Object.assign({domain:domains[1].slice(2,4),anchor:'x2',matches:'y'}, yaxisBase),
    xaxis3: Object.assign({domain:domains[2].slice(0,2),anchor:'y3'}, xaxisBase),
    yaxis3: Object.assign({domain:domains[2].slice(2,4),anchor:'x3',matches:'y'}, yaxisBase),
    xaxis4: Object.assign({domain:domains[3].slice(0,2),anchor:'y4'}, xaxisBase),
    yaxis4: Object.assign({domain:domains[3].slice(2,4),anchor:'x4',matches:'y'}, yaxisBase),
    shapes:shapes, annotations:annotations,
    hoverlabel:{bgcolor:'#1e293b',bordercolor:'#334155',font:{color:'#e2e8f0',size:11}}
  };
  Plotly.newPlot(divId, traces, layout, {displayModeBar:false, responsive:true});
}

function switchMetricTab(tid, idx) {
  var btns = document.querySelectorAll('.tabs[data-tabs="'+tid+'"] .tab-btn');
  var panels = document.querySelectorAll('.tab-panels[data-tabs="'+tid+'"] .tab-panel');
  btns.forEach(function(b,i){ b.classList.toggle('active', i===idx); });
  panels.forEach(function(p,i){
    p.classList.toggle('active', i===idx);
    if (i===idx) {
      setTimeout(function() {
        p.querySelectorAll('div[data-charts]').forEach(function(div) {
          if (div.children.length === 0) {
            var dd = JSON.parse(div.getAttribute('data-charts'));
            var m = div.getAttribute('data-metric') || 'return';
            drawQSummary(div.id, dd, m);
          } else {
            Plotly.relayout(div.id, {width: div.parentElement.offsetWidth});
          }
        });
      }, 80);
    }
  });
}

function drawCompBar(divId, d) {
  allCompDivs.push(divId);
  var years = d.years;
  var traces = [];
  ['Q1','Q2','Q3','Q4'].forEach(function(q) {
    var x = [], y = [];
    years.forEach(function(yr, i) {
      if (d.qs[i] === q && d.cagr[i] !== null) {
        x.push(yr);
        y.push(d.cagr[i]);
      }
    });
    traces.push({
      x: x, y: y, type: 'bar', name: q,
      marker: { color: d.q_colors[q], opacity: 0.85 },
      width: 0.8,
      hovertemplate: '%{x} %{y:.1f}%<extra></extra>',
      showlegend: false,
      visible: activeQs[q] ? true : 'legendonly'
    });
  });
  var yrange = d.y_range || null;
  var layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: '#0a1628',
    font: { family: 'Inter,sans-serif', color: '#94a3b8', size: 11 },
    margin: { t: 22, r: 12, b: 30, l: 45 },
    barmode: 'overlay',
    xaxis: { tickfont: {size:8}, dtick:5, type: 'linear' },
    yaxis: { ticksuffix:'%', gridcolor:'#1e293b', tickfont:{size:9},
             zeroline:true, zerolinecolor:'#334155', range: yrange },
    annotations: [{text:d.comp, xref:'paper', yref:'paper', x:0, y:1.08,
      showarrow:false, font:{size:11, color:'#e2e8f0', weight:600}}],
    hoverlabel: { bgcolor: '#1e293b', bordercolor: '#334155', font: {color:'#e2e8f0', size:11} }
  };
  Plotly.newPlot(divId, traces, layout, {displayModeBar:false, responsive:true, doubleClick:'reset+autosize'});
}

function toggleQuadrant(q) {
  activeQs[q] = !activeQs[q];
  var btn = document.getElementById('qbtn_' + q);
  if (btn) btn.classList.toggle('q-legend-off', !activeQs[q]);
  var qIdx = ['Q1','Q2','Q3','Q4'].indexOf(q);
  allCompDivs.forEach(function(divId) {
    var div = document.getElementById(divId);
    if (div && div.data) {
      var vis = activeQs[q] ? true : 'legendonly';
      Plotly.restyle(divId, {visible: vis}, [qIdx]);
    }
  });
}

function switchAnalysisTab(tid, idx) {
  var btns = document.querySelectorAll('.tabs[data-tabs="'+tid+'"] .tab-btn');
  var panels = document.querySelectorAll('.tab-panels[data-tabs="'+tid+'"] .tab-panel');
  btns.forEach(function(b,i){ b.classList.toggle('active', i===idx); });
  panels.forEach(function(p,i){
    p.classList.toggle('active', i===idx);
    if (i===idx) {
      setTimeout(function() {
        p.querySelectorAll('div[data-charts]').forEach(function(div) {
          if (div.children.length === 0) {
            var d = JSON.parse(div.getAttribute('data-charts'));
            drawCompBar(div.id, d);
          }
        });
      }, 50);
    }
  });
  activeQs = {Q1:true, Q2:true, Q3:true, Q4:true};
  allCompDivs = [];
  document.querySelectorAll('.q-legend-btn').forEach(function(b){ b.classList.remove('q-legend-off'); });
  var activePanel = document.querySelector('.tab-panels[data-tabs="'+tid+'"] .tab-panel.active');
  if (activePanel) {
    activePanel.querySelectorAll('div[data-charts]').forEach(function(div) {
      if (allCompDivs.indexOf(div.id) < 0) allCompDivs.push(div.id);
    });
  }
}
"""

meth = methodology
quadrant_grid = build_quadrant_grid()

intro = """
<h2>Market Regimes</h2>
<p class="subtitle">How do macro environments map to portfolio component performance?</p>
<div class="section">
  <p>Markets cycle through four fundamental regimes defined by the intersection of
  <b>growth vs stagnation</b> and <b>low vs high inflation</b>.
  The Golden Butterfly is designed to hold assets that thrive in each quadrant.</p>
  <div class="note">
    <b>The 2×2 framework</b> (Dalio / Bridgewater "All Weather" model):<br>
    Each regime favors different asset classes. A balanced portfolio holds all four
    so that at least one component performs well in any environment.
  </div>
""" + quadrant_grid + """
</div>
"""


def build_methodology(region):
    if region == "us":
        thresh = "<b>Thresholds:</b> GDP median = " + str(meth["us_thresholds"]["gdp_median"]) + "%, CPI median = " + str(meth["us_thresholds"]["cpi_median"]) + "%"
        sources = (
            "<li>CPI: FRED CPIAUCSL (Bureau of Labor Statistics)</li>"
            "<li>GDP: FRED GDPC1 (Bureau of Economic Analysis)</li>"
        )
        notes = ""
    else:
        thresh = "<b>Thresholds:</b> GDP median = " + str(meth["eu_thresholds"]["gdp_median"]) + "%, HICP/blend median = " + str(meth["eu_thresholds"]["hicp_median"]) + "%"
        sources = (
            "<li>CPI 1956–1996: blend of DE/FR/UK/IT CPI (FRED, OECD MEI)</li>"
            "<li>HICP 1996+: FRED CP0000EZ19M086NEST (Eurostat)</li>"
            "<li>GDP 1971–1995: blend of DE/FR/UK real GDP index (FRED, OECD)</li>"
            "<li>GDP 1995+: FRED CLVMNACSCAB1GQEA19 (Eurostat)</li>"
        )
        notes = (
            '<p style="font-size:0.8rem;color:var(--muted)">' + meth["eu_fallback"] + '</p>'
            '<p style="font-size:0.78rem;color:var(--muted)">Validation: blend CPI vs HICP = 0.98 corr, blend GDP vs EU GDP = 0.97 corr.</p>'
        )
    return (
        '<div class="section">' +
        '<h3>Methodology</h3>' +
        '<p style="font-size:0.85rem;color:var(--muted)">Each year classified via <b>median split</b> on YoY GDP growth and YoY inflation.</p>' +
        '<div class="note">' + thresh + '</div>' +
        '<p style="font-size:0.82rem;color:var(--muted)"><b>Data sources:</b></p>' +
        '<ul style="color:var(--muted);font-size:0.8rem;margin:0.3rem 0 0.5rem 1.2rem">' + sources + '</ul>' +
        notes +
        '</div>'
    )


COMP_COLORS = ['#94a3b8', '#a78bfa', '#7dd3fc', '#fda4af', '#d4d4d8']
COMP_COLORS_ETF = ['#64748b', '#7c3aed', '#0ea5e9', '#e11d48', '#a1a1aa']

def _yearly_metrics(series, year):
    """Compute annual metrics for one year."""
    sy = series[series.index.year == year]
    if len(sy) < 20:
        return None
    ret = (sy.iloc[-1] / sy.iloc[0] - 1) * 100
    daily_r = sy.pct_change().dropna()
    vol = daily_r.std() * np.sqrt(252) * 100
    cum = (1 + daily_r).cumprod()
    mdd = (cum / cum.cummax() - 1).min() * 100
    sharpe = ret / vol if vol > 0 else 0
    calmar = ret / abs(mdd) if mdd != 0 else 0
    monthly_r = daily_r.resample('ME').apply(lambda x: (1+x).prod()-1)
    win_rate = (monthly_r > 0).sum() / len(monthly_r) * 100 if len(monthly_r) > 0 else 0
    return {
        'return': round(ret, 1),
        'volatility': round(vol, 1),
        'max_dd': round(mdd, 1),
        'sharpe': round(sharpe, 2),
        'calmar': round(calmar, 2),
        'win_rate': round(win_rate, 1),
    }


METRICS = ['return', 'volatility', 'max_dd', 'sharpe', 'calmar', 'win_rate']
METRIC_LABELS = {
    'return': 'Annual Return',
    'volatility': 'Volatility',
    'max_dd': 'Max Drawdown',
    'sharpe': 'Sharpe Ratio',
    'calmar': 'Calmar Ratio',
    'win_rate': 'Win Rate',
}
METRIC_SUFFIX = {'return': '%', 'volatility': '%', 'max_dd': '%', 'sharpe': '', 'calmar': '', 'win_rate': '%'}


def build_quadrant_summary_json(region):
    """Compute per-year metrics per component per quadrant for boxplots (proxy + ETF)."""
    comps_proxy = COMPONENTS[region]
    comps_etf = ETF_COMPONENTS[region]
    r = us_regimes if region == 'us' else eu_regimes
    comp_names = list(comps_proxy.keys())

    # {metric: {q: {comp: [val, ...]}}}
    all_data = {m: {q: {} for q in ['Q1','Q2','Q3','Q4']} for m in METRICS}
    all_data_etf = {m: {q: {} for q in ['Q1','Q2','Q3','Q4']} for m in METRICS}

    for q in ['Q1', 'Q2', 'Q3', 'Q4']:
        q_years = [int(yr) for yr, d in r.items() if d['q'] == q]
        for comp in comp_names:
            # Proxy
            s = prices[comps_proxy[comp]].dropna()
            for m in METRICS:
                all_data[m][q][comp] = []
            for yr in q_years:
                met = _yearly_metrics(s, yr)
                if met:
                    for m in METRICS:
                        all_data[m][q][comp].append(met[m])
            # ETF
            se = prices[comps_etf[comp]].dropna()
            for m in METRICS:
                all_data_etf[m][q][comp] = []
            for yr in q_years:
                met = _yearly_metrics(se, yr)
                if met:
                    for m in METRICS:
                        all_data_etf[m][q][comp].append(met[m])

    return json.dumps({
        'comps': comp_names,
        'metrics': METRICS,
        'metric_labels': METRIC_LABELS,
        'metric_suffix': METRIC_SUFFIX,
        'all_data': all_data,
        'all_data_etf': all_data_etf,
        'q_colors': Q_COLORS, 'comp_colors': COMP_COLORS, 'comp_colors_etf': COMP_COLORS_ETF,
        'q_labels': Q_LABELS,
    }, separators=(',', ':'))


def build_summary_description(region):
    comps = COMPONENTS[region]
    r = us_regimes if region == 'us' else eu_regimes

    # Compute all metrics per quadrant per component
    q_stats = {q: {} for q in ['Q1','Q2','Q3','Q4']}
    for q in ['Q1','Q2','Q3','Q4']:
        q_years = [int(yr) for yr, d in r.items() if d['q'] == q]
        for comp, col in comps.items():
            s = prices[col].dropna()
            metrics = [_yearly_metrics(s, yr) for yr in q_years]
            metrics = [m for m in metrics if m]
            if not metrics:
                q_stats[q][comp] = None
                continue
            q_stats[q][comp] = {
                'ret': round(np.mean([m['return'] for m in metrics]), 1),
                'med_ret': round(np.median([m['return'] for m in metrics]), 1),
                'vol': round(np.mean([m['volatility'] for m in metrics]), 1),
                'mdd': round(np.mean([m['max_dd'] for m in metrics]), 1),
                'sharpe': round(np.mean([m['sharpe'] for m in metrics]), 2),
                'calmar': round(np.mean([m['calmar'] for m in metrics]), 2),
                'wr': round(np.mean([m['win_rate'] for m in metrics]), 0),
                'n': len(metrics),
            }

    def fmt(v, suffix='%'):
        if v is None: return 'N/A'
        return ('+' if v > 0 else '') + str(v) + suffix

    def comp_rank(q, metric, reverse=False):
        vals = {c: q_stats[q][c][metric] for c in comps if q_stats[q][c]}
        ranked = sorted(vals.items(), key=lambda x: x[1], reverse=not reverse)
        return ranked

    q_names = {'Q1': 'Growth + Low Inflation', 'Q2': 'Growth + High Inflation',
               'Q3': 'Stagnation + Low Inflation', 'Q4': 'Stagflation'}

    html = '<div style="margin-top:1.2rem">'

    # Q1 Analysis
    q = 'Q1'
    st = q_stats[q]
    html += (
        '<div style="border-left:3px solid ' + Q_COLORS[q] + ';padding:0.6rem 0.8rem;margin:0.8rem 0">'
        '<h4 style="color:' + Q_COLORS[q] + ';font-size:0.95rem;margin-bottom:0.4rem">' + q + ' \u2014 ' + q_names[q] + ' (' + str(st[list(comps.keys())[0]]['n']) + ' years)</h4>'
        '<p style="font-size:0.83rem;color:var(--muted);line-height:1.6">'
        'The best environment for equities. '
        '<b>SCV leads</b> with ' + fmt(st['Small Cap Value']['ret']) + ' avg return (Sharpe ' + str(st['Small Cap Value']['sharpe']) + '), '
        'followed by Total Market at ' + fmt(st['Total Market']['ret']) + '. '
        'Both show low volatility (' + str(st['Total Market']['vol']) + '%) and shallow drawdowns (' + str(st['Total Market']['mdd']) + '%). '
        'Win rates are high: SCV ' + str(int(st['Small Cap Value']['wr'])) + '%, TM ' + str(int(st['Total Market']['wr'])) + '%. '
        '<b>ST Bonds</b> deliver the best Sharpe (' + str(st['ST Bonds']['sharpe']) + ') and Calmar (' + str(st['ST Bonds']['calmar']) + ') '
        'due to near-zero drawdowns, but returns are modest (' + fmt(st['ST Bonds']['ret']) + '). '
        '<b>LT Bonds</b> underperform (' + fmt(st['LT Bonds']['ret']) + ') \u2014 low inflation means no rate cuts to boost bond prices. '
        '<b>Gold</b> is flat (' + fmt(st['Gold']['ret']) + ') \u2014 no inflation hedge needed.'
        '</p></div>'
    )

    # Q2 Analysis
    q = 'Q2'
    st = q_stats[q]
    gold_note = ' (mean; median is 0% due to Bretton Woods pre-1971 fixed price)' if region == 'us' else ''
    html += (
        '<div style="border-left:3px solid ' + Q_COLORS[q] + ';padding:0.6rem 0.8rem;margin:0.8rem 0">'
        '<h4 style="color:' + Q_COLORS[q] + ';font-size:0.95rem;margin-bottom:0.4rem">' + q + ' \u2014 ' + q_names[q] + ' (' + str(st[list(comps.keys())[0]]['n']) + ' years)</h4>'
        '<p style="font-size:0.83rem;color:var(--muted);line-height:1.6">'
        '<b>Gold dominates</b> with ' + fmt(st['Gold']['ret']) + ' avg return' + gold_note + ', '
        'driven by massive spikes during inflationary episodes (1971\u20131979). '
        'Equities remain positive (TM ' + fmt(st['Total Market']['ret']) + ', SCV ' + fmt(st['Small Cap Value']['ret']) + ') \u2014 '
        'growth supports earnings even as inflation erodes real returns. '
        'Volatility rises to ' + str(st['Total Market']['vol']) + '% for equities. '
        '<b>LT Bonds</b> at ' + fmt(st['LT Bonds']['ret']) + ' \u2014 rising inflation pushes yields up and prices down, '
        'with ' + str(st['LT Bonds']['mdd']) + '% avg drawdown. '
        '<b>ST Bonds</b> benefit from rising rates: ' + fmt(st['ST Bonds']['ret']) + ' with ' + str(int(st['ST Bonds']['wr'])) + '% win rate.'
        '</p></div>'
    )

    # Q3 Analysis
    q = 'Q3'
    st = q_stats[q]
    html += (
        '<div style="border-left:3px solid ' + Q_COLORS[q] + ';padding:0.6rem 0.8rem;margin:0.8rem 0">'
        '<h4 style="color:' + Q_COLORS[q] + ';font-size:0.95rem;margin-bottom:0.4rem">' + q + ' \u2014 ' + q_names[q] + ' (' + str(st[list(comps.keys())[0]]['n']) + ' years)</h4>'
        '<p style="font-size:0.83rem;color:var(--muted);line-height:1.6">'
        '<b>LT Bonds shine</b> with ' + fmt(st['LT Bonds']['ret']) + ' avg return \u2014 '
        'central banks cut rates during stagnation, boosting bond prices. '
        'However, volatility is high (' + str(st['LT Bonds']['vol']) + '%) with ' + str(st['LT Bonds']['mdd']) + '% avg drawdown. '
        '<b>Gold</b> also performs well (' + fmt(st['Gold']['ret']) + ') as a safe haven. '
        'Equities are mixed: TM ' + fmt(st['Total Market']['ret']) + ' (median ' + fmt(st['Total Market']['med_ret']) + ') '
        'with elevated volatility (' + str(st['Total Market']['vol']) + '%) and deeper drawdowns (' + str(st['Total Market']['mdd']) + '%). '
        'This is where the Golden Butterfly\'s bond allocation earns its keep. '
        '<b>ST Bonds</b> remain steady (' + fmt(st['ST Bonds']['ret']) + ', ' + str(int(st['ST Bonds']['wr'])) + '% win rate).'
        '</p></div>'
    )

    # Q4 Analysis
    q = 'Q4'
    st = q_stats[q]
    html += (
        '<div style="border-left:3px solid ' + Q_COLORS[q] + ';padding:0.6rem 0.8rem;margin:0.8rem 0">'
        '<h4 style="color:' + Q_COLORS[q] + ';font-size:0.95rem;margin-bottom:0.4rem">' + q + ' \u2014 ' + q_names[q] + ' (' + str(st[list(comps.keys())[0]]['n']) + ' years)</h4>'
        '<p style="font-size:0.83rem;color:var(--muted);line-height:1.6">'
        'The worst environment for most assets. '
        'Equities suffer: TM ' + fmt(st['Total Market']['ret']) + ' (median ' + fmt(st['Total Market']['med_ret']) + '), '
        'with the highest volatility (' + str(st['Total Market']['vol']) + '%) and deepest drawdowns (' + str(st['Total Market']['mdd']) + '%). '
        'Win rate drops to ' + str(int(st['Total Market']['wr'])) + '% \u2014 barely a coin flip. '
        '<b>LT Bonds also struggle</b> (' + fmt(st['LT Bonds']['ret']) + ', median ' + fmt(st['LT Bonds']['med_ret']) + ') '
        'with ' + str(st['LT Bonds']['mdd']) + '% avg drawdown \u2014 inflation destroys bond value. '
        '<b>ST Bonds are the standout</b>: ' + fmt(st['ST Bonds']['ret']) + ' avg return, '
        'best Sharpe (' + str(st['ST Bonds']['sharpe']) + ') and Calmar (' + str(st['ST Bonds']['calmar']) + ') of any asset in any quadrant. '
        'Win rate ' + str(int(st['ST Bonds']['wr'])) + '%. Short duration protects against rate hikes while capturing rising yields. '
        '<b>Gold</b> at ' + fmt(st['Gold']['ret']) + ' \u2014 modest, but the only other asset with positive mean return alongside ST Bonds.'
        '</p></div>'
    )

    # Cross-quadrant summary
    # Compute ETF coverage per quadrant
    etf_starts = {
        'us': min(2001, 2004, 2002, 2002, 2004),
        'eu': min(2009, 2018, 2018, 2017, 2011),
    }
    etf_from = etf_starts[region]
    q_counts_proxy = {}
    q_counts_etf = {}
    for q in ['Q1','Q2','Q3','Q4']:
        q_years = [int(yr) for yr, d in r.items() if d['q'] == q]
        q_counts_proxy[q] = len(q_years)
        q_counts_etf[q] = len([y for y in q_years if y >= etf_from])

    html += (
        '<div style="border-left:3px solid var(--accent);padding:0.6rem 0.8rem;margin:0.8rem 0">'
        '<h4 style="color:var(--accent);font-size:0.95rem;margin-bottom:0.4rem">Key Takeaways</h4>'
        '<ul style="font-size:0.83rem;color:var(--muted);line-height:1.7;margin:0.3rem 0 0 1rem">'
        '<li><b>Equities (TM, SCV)</b> dominate in Q1, hold up in Q2/Q3, but suffer in Q4. SCV consistently outperforms TM by 2\u20133pp across all regimes.</li>'
        '<li><b>LT Bonds</b> are the Q3 hero but the Q4 villain. High volatility makes them unreliable outside their sweet spot.</li>'
        '<li><b>ST Bonds</b> are the portfolio\'s anchor: positive in every quadrant, best risk-adjusted returns in Q4 (when everything else fails). Low volatility, high win rate, minimal drawdowns.</li>'
        '<li><b>Gold</b> spikes in Q2 (inflation hedge) and provides diversification in Q3, but is unreliable in Q1/Q4. Pre-1971 data is flat (Bretton Woods).</li>'
        '<li><b>The Golden Butterfly works</b> because no single quadrant leaves all 5 components negative. In the worst regime (Q4), ST Bonds and Gold provide positive returns while equities and LT Bonds suffer.</li>'
        '</ul></div>'
    )

    html += (
        '<div style="border-left:3px solid #c084fc;padding:0.6rem 0.8rem;margin:0.8rem 0">'
        '<h4 style="color:#c084fc;font-size:0.95rem;margin-bottom:0.4rem">Why Proxies Matter</h4>'
        '<p style="font-size:0.83rem;color:var(--muted);line-height:1.7">'
        'Comparing the <b>Proxy</b> and <b>ETF</b> tabs reveals a critical limitation of ETF-only analysis. '
        'ETFs have existed for only ~20 years (US) or ~15 years (EU), and this period is heavily skewed toward Q3 (stagnation + low inflation \u2014 the post-GFC, QE era). '
        'The data coverage per quadrant:</p>'
        '<table style="font-size:0.8rem;color:var(--muted);margin:0.5rem 0;border-collapse:collapse;width:100%">'
        '<tr style="border-bottom:1px solid var(--border)">'
        '<th style="text-align:left;padding:0.3rem 0.5rem">Quadrant</th>'
        '<th style="text-align:right;padding:0.3rem 0.5rem">Proxy years</th>'
        '<th style="text-align:right;padding:0.3rem 0.5rem">ETF years (from ' + str(etf_from) + ')</th>'
        '<th style="text-align:left;padding:0.3rem 0.5rem">Assessment</th></tr>'
        + ''.join(
            '<tr style="border-bottom:1px solid var(--border)">'
            '<td style="padding:0.3rem 0.5rem">' + q_pill(q) + '</td>'
            '<td style="text-align:right;padding:0.3rem 0.5rem">' + str(q_counts_proxy[q]) + '</td>'
            '<td style="text-align:right;padding:0.3rem 0.5rem">' + str(q_counts_etf[q]) + '</td>'
            '<td style="padding:0.3rem 0.5rem;font-size:0.78rem">' + (
                '\u2705 Sufficient' if q_counts_etf[q] >= 8 else
                '\u26a0\ufe0f Limited' if q_counts_etf[q] >= 3 else
                '\u274c Insufficient \u2014 proxy essential'
            ) + '</td></tr>'
            for q in ['Q1','Q2','Q3','Q4']
        )
        + '</table>'
        '<p style="font-size:0.83rem;color:var(--muted);line-height:1.7;margin-top:0.5rem">'
        'With only <b>' + str(q_counts_etf['Q1']) + '</b> Q1 years and <b>' + str(q_counts_etf['Q4']) + '</b> Q4 years in the ETF period, '
        'drawing conclusions about portfolio behavior in growth or stagflation regimes from ETF data alone would be statistically meaningless. '
        'The proxy chain extends coverage to <b>' + str(q_counts_proxy['Q1']) + '</b> Q1 years and <b>' + str(q_counts_proxy['Q4']) + '</b> Q4 years, '
        'capturing the full range of macro environments including the 1970s stagflation, 1980s disinflation bull, and 1990s tech boom \u2014 '
        'regimes that no ETF has ever experienced. '
        'This is the fundamental reason proxies are necessary: <b>without them, the analysis would only reflect the post-GFC low-rate world</b>, '
        'which is precisely the environment least likely to persist.</p>'
        '</div>'
    )

    html += '</div>'
    return html



def build_analysis_section(region, proxy_json, etf_json):
    summary_json = build_quadrant_summary_json(region)

    # Build metric tabs for the boxplot section
    mtid = region + '_metrics'
    metric_icons = {'return': '📈', 'volatility': '🌊', 'max_dd': '📉', 'sharpe': '⚖️', 'calmar': '🎯', 'win_rate': '✅'}
    metric_tab_btns = ''
    metric_tab_panels = ''
    for mi, m in enumerate(METRICS):
        active = ' active' if mi == 0 else ''
        metric_tab_btns += (
            '<button class="tab-btn' + active + '" onclick="switchMetricTab(\'' + mtid + '\',' + str(mi) + ')">' +
            metric_icons.get(m, '') + ' ' + METRIC_LABELS[m] + '</button>'
        )
        div_id = region + '_qbox_' + m
        metric_tab_panels += (
            '<div class="tab-panel' + active + '">'
            '<div id="' + div_id + '" style="width:100%;height:600px"'
            ' data-charts=\'' + summary_json + '\' data-mode="qsummary" data-metric="' + m + '"></div>'
            '</div>'
        )
    metric_tabs = (
        '<div class="tabs" data-tabs="' + mtid + '">' + metric_tab_btns + '</div>'
        '<div class="tab-panels" data-tabs="' + mtid + '">' + metric_tab_panels + '</div>'
    )

    legend = '<div class="q-legend">'
    for q in ['Q1', 'Q2', 'Q3', 'Q4']:
        label, color, desc = QUADRANTS[q]
        legend += (
            '<button class="q-legend-btn" id="qbtn_' + q + '" onclick="toggleQuadrant(\'' + q + '\')"'
            ' style="--qc:' + color + '">'
            '<span class="q-legend-dot" style="background:' + color + '"></span>'
            + q + ' — ' + label
            + '</button>'
        )
    legend += '</div>'

    def build_divs(data_json, prefix):
        d = json.loads(data_json)
        divs = ''
        for ci, comp in enumerate(d['comps']):
            cid = prefix + '_comp_' + str(ci)
            comp_json = json.dumps({
                'comp': comp, 'years': d['years'], 'qs': d['qs'],
                'cagr': d['cagr'][ci], 'q_colors': d['q_colors'],
                'y_range': d.get('y_range'),
            }, separators=(',', ':'))
            divs += '<div id="' + cid + '" style="width:100%;height:180px" data-charts=\'' + comp_json + '\' data-mode="compbar"></div>'
        return divs

    tid = region + '_analysis'
    proxy_divs = build_divs(proxy_json, region + '_proxy')
    etf_divs = build_divs(etf_json, region + '_etf')

    return (
        '<div class="section">'
        '<h3>Component Annual Returns by Regime</h3>'
        '<p style="color:var(--muted);font-size:0.85rem">'
        'Year-by-year returns for each asset. Bar color = market regime. '
        'Click a quadrant to show/hide its years.</p>'
        + legend
        + '<div class="tabs" data-tabs="' + tid + '">'
        '<button class="tab-btn active" onclick="switchAnalysisTab(\'' + tid + '\',0)">📈 Proxy (full history)</button>'
        '<button class="tab-btn" onclick="switchAnalysisTab(\'' + tid + '\',1)">🎯 ETF (real data)</button>'
        '</div>'
        '<div class="tab-panels" data-tabs="' + tid + '">'
        '<div class="tab-panel active">' + proxy_divs + '</div>'
        '<div class="tab-panel">' + etf_divs + '</div>'
        '</div>'
        '</div>'
        '<div class="section">'
        '<h3>Component Performance by Regime</h3>'
        '<p style="color:var(--muted);font-size:0.85rem">'
        'Distribution of annual metrics per component in each quadrant. '
        'Dashed line = mean. Proxy (solid) and ETF (dotted) shown side by side.</p>'
        + metric_tabs
        + build_summary_description(region)
        + '</div>'
    )



us_content = (
    build_methodology('us')
    + '<div class="section">'
    '<h3>US Market Regimes (1950–present)</h3>'
    '<p>Classification based on US GDP growth and US CPI inflation.</p>'
    '<div id="us_macro" style="width:100%;height:280px" data-charts=\'' + us_macro_json + '\' data-mode="macro"></div>'
    + build_regime_bar('us')
    + '</div>'
    + build_analysis_section('us', us_proxy_json, us_etf_json)
)

eu_content = (
    build_methodology('eu')
    + '<div class="section">'
    '<h3>EU Market Regimes (1950–present)</h3>'
    '<p>Classification based on blended EU GDP growth and CPI/HICP inflation.</p>'
    '<div id="eu_macro" style="width:100%;height:280px" data-charts=\'' + eu_macro_json + '\' data-mode="macro"></div>'
    + build_regime_bar('eu')
    + '</div>'
    + build_analysis_section('eu', eu_proxy_json, eu_etf_json)
)

html_parts = [
    '<!DOCTYPE html>',
    '<html lang="en"><head>',
    '<meta charset="UTF-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '<title>Market Regimes</title>',
    '<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>',
    '<style>' + CSS + '</style>',
    '</head><body>',
    intro,
    '<div class="region" data-region="us">',
    us_content,
    '</div>',
    '<div class="region" data-region="eu">',
    eu_content,
    '</div>',
    '<script>' + JS + '</script>',
    '</body></html>',
]
html = '\n'.join(html_parts)

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, 'market_regimes.html')
with open(path, 'w') as f:
    f.write(html)
print(f'\u2705 {path} ({len(html)//1024} KB)')

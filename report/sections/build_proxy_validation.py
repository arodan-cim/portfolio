"""
Build proxy validation HTML section.
Reads output/proxy_validation.json and generates report/output/proxy_validation.html
"""

import json, os, re

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'output')
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'output')

with open(os.path.join(DATA, 'proxy_validation.json')) as f:
    results = json.load(f)

with open(os.path.join(DATA, 'proxy_chart_data.json')) as f:
    chart_data = json.load(f)


def verdict(v):
    checks = [
        v['monthly_corr'] >= 0.90,
        v['cagr_gap'] <= 0.02,
        v['dd_diff'] <= 0.05,
        v['roll1y_corr'] >= 0.85,
    ]
    n = sum(checks)
    if n == 4: return 'PASS', 'green'
    if n == 3: return 'MARGINAL', 'gold'
    return 'FAIL', 'red'


def pill(text, color):
    return f'<span class="pill pill-{color}">{text}</span>'


def metric_cell(val, good, ok_fn):
    """Format a metric value with color."""
    if ok_fn(val):
        return f'<td class="good">{val}</td>'
    return f'<td class="warn">{val}</td>'



ASSETS = {
    # US ETFs
    'VTI':   ('Vanguard Total Stock Market ETF', 'US', 'Real ETF', 'Tracks CRSP US Total Market (~4,000 stocks, 100% of investable US equity). ER 0.03%. Since 2001.'),
    'VBR':   ('Vanguard Small-Cap Value ETF', 'US', 'Real ETF', 'Tracks CRSP US Small Cap Value Index — small companies with low P/B ratios. ER 0.07%. Since 2004.'),
    'TLT':   ('iShares 20+ Year Treasury Bond ETF', 'US', 'Real ETF', 'Holds US Treasuries with 20+ year maturity. Effective duration ~17yr. ER 0.15%. Since 2002.'),
    'SHY':   ('iShares 1-3 Year Treasury Bond ETF', 'US', 'Real ETF', 'Holds short-term US Treasuries. Effective duration ~1.9yr. ER 0.15%. Since 2002.'),
    'GLD':   ('SPDR Gold Shares', 'US', 'Real ETF', 'Physically backed gold trust. Largest gold ETF globally. ER 0.40%. Since 2004.'),
    # EU ETFs
    'IWDA.AS': ('iShares Core MSCI World UCITS ETF', 'EU', 'Real ETF', 'EUR-denominated. ~1,500 large/mid-cap stocks across 23 developed markets (~70% US). Accumulating. ER 0.20%. Since 2009.'),
    'IUSN.DE': ('iShares MSCI World Small Cap UCITS ETF', 'EU', 'Real ETF', 'EUR-denominated. ~3,400 small-cap stocks across developed markets. All small caps, not specifically value. ER 0.35%. Since 2018.'),
    'DTLA.L':  ('iShares $ Treasury Bond 20+yr UCITS ETF', 'EU', 'Real ETF', 'USD-denominated. Same underlying as TLT. For EU investors holding USD bond exposure. ER 0.07%. Since 2015.'),
    'IBTA.L':  ('iShares $ Treasury Bond 1-3yr UCITS ETF', 'EU', 'Real ETF', 'USD-denominated. Same underlying as SHY. ER 0.07%. Since 2017.'),
    'IGLN.L':  ('iShares Physical Gold ETC', 'EU', 'Real ETF', 'USD-denominated. Physically backed gold. ER 0.12%. Since 2011.'),
    # Indices
    '^GSPC':  ('S&P 500 Index', 'US', 'Index', '~500 large-cap US stocks, ~80% of US market cap. Available from 1950. Used as total market proxy — misses mid/small caps.'),
    '^RUT':   ('Russell 2000 Index', 'US', 'Index', '2,000 smallest stocks in the Russell 3000. Best available small-cap index. Available from 1987.'),
    '^N225':  ('Nikkei 225', 'Japan', 'Index', 'Price-weighted index of 225 large Japanese companies. Available from 1965. Used in EU equity blend.'),
    '^FTSE':  ('FTSE 100', 'UK', 'Index', '100 largest companies on the London Stock Exchange. Available from 1984. Used in EU equity blend.'),

    # Mutual funds
    'NAESX':  ('Vanguard Small Cap Index Fund', 'US', 'Mutual Fund', 'Tracks CRSP US Small Cap Index. Near-perfect match for VBR (0.98 corr). Available from 1980 — bridges the gap before VBR (2004).'),
    'VUSTX':  ('Vanguard Long-Term Treasury Fund', 'US', 'Mutual Fund', 'Holds 15-30yr Treasuries. Available from ~1986. Reference comparison for TLT.'),
    # FRED yield models
    'DGS20':  ('FRED DGS20 — 20-Year Treasury Yield', 'US', 'FRED Model', 'Daily Constant Maturity Rate for 20-Year US Treasuries, published by the Federal Reserve (FRED). Available from 1962. Converted to total return via duration model (d=18).'),
    'DGS1+DGS2': ('DGS1 → DGS2 Splice (d=1.9)', 'US', 'FRED Model', 'Uses DGS1 before 1976, DGS2 from 1976. Duration model d=1.9 matches SHY effective duration. Splice validated — 0.96 monthly corr in overlap.'),
    'DGS1':   ('FRED DGS1 — 1-Year Treasury Yield', 'US', 'FRED Model', 'Daily Constant Maturity Rate for 1-Year US Treasuries (FRED). Available from 1962. Used pre-1976 when DGS2 is not available.'),
    'DGS2':   ('FRED DGS2 — 2-Year Treasury Yield', 'US', 'FRED Model', 'Daily Constant Maturity Rate for 2-Year US Treasuries (FRED). Available from 1976. Duration d=1.9 matches SHY effective duration (~1.9yr).'),
    # Gold
    'GC=F':   ('COMEX Gold Futures', 'US', 'Futures', 'Continuous front-month gold futures. Available from ~2000 on Yahoo Finance. Used as gold proxy post-2000.'),
    'Milestones': ('Gold Annual Milestones (1950-2000)', 'US', 'Synthetic', 'Known annual average gold prices (USD/oz) from World Gold Council and LBMA records, interpolated daily. Prices verified against historical records. LIMITATION: no intra-year volatility. Drawdowns within a year are invisible (e.g. 1980 crash from 850 to 480 USD in 2 months shows as smooth annual decline). Reliable for decade-level CAGR, NOT for drawdown or volatility analysis.'),

    # FX
    'EUR/USD': ('EUR/USD Exchange Rate', 'FX', 'FRED', 'Daily EUR/USD rate from FRED (DEXUSEU). Available from 1999-01-04 (EUR inception). Used to convert USD equity returns to EUR for EU proxies.'),
    'CHF/USD': ('CHF/USD Exchange Rate', 'FX', 'FRED', 'Daily Swiss Franc / USD rate from FRED (DEXSZUS). Available from 1971. Used as EUR/USD proxy pre-1999 (CHF/EUR monthly corr = 0.94 in overlap period).'),
    # Blends
    '60/20/20_EUR':    ('Global Equity Blend → EUR', 'EU', 'Synthetic', '60% ^GSPC + 20% ^N225 + 20% ^FTSE, converted to EUR. Approximates MSCI World in EUR. Available from 1984.'),
    'GSPC_EUR':        ('^GSPC → EUR', 'EU', 'Synthetic', 'S&P 500 converted to EUR. Used pre-1984 when only ^GSPC is available. MSCI World is ~70% US so this captures most of the movement.'),
    'NAESX_EUR':       ('NAESX → EUR', 'EU', 'Synthetic', 'Vanguard Small Cap Index Fund converted to EUR. Best available EU SCV proxy. Available from 1980.'),
    '^GSPC+2%':        ('^GSPC + 2% Annual Premium', 'US', 'Synthetic', 'S&P 500 daily returns + 2% annualized premium (Fama-French size+value factor). Used pre-1980 when no small-cap index exists. FAILS validation vs NAESX (0.80 corr, 7.7pp DD diff).'),
}

TYPE_COLOR = {
    'Real ETF': 'etf', 'Index': 'index', 'Mutual Fund': 'fund',
    'FRED Model': 'synth', 'Futures': 'synth', 'Synthetic': 'synth', 'FX': 'synth',
}

def asset_badge(ticker):
    a = ASSETS.get(ticker)
    if not a:
        return ''
    name, region, atype, desc = a
    color = TYPE_COLOR.get(atype, 'gold')
    return (
        f'<div class="asset-badge">'
        f'<span class="pill pill-{color}">{atype}</span> '
        f'<b>{ticker}</b> — {name}'
        f'<div class="asset-desc">{desc}</div>'
        f'</div>'
    )

def build_link_card(link):
    """Build HTML for one validation link."""
    vd, vc = verdict(link)
    corr = link['monthly_corr']
    gap = link['cagr_gap']
    dd = link['dd_diff']
    roll = link['roll1y_corr']

    c_ok = '✅' if corr >= 0.90 else '⚠️' if corr >= 0.85 else '❌'
    g_ok = '✅' if gap <= 0.01 else '⚠️' if gap <= 0.02 else '❌'
    d_ok = '✅' if dd <= 0.05 else '❌'
    r_ok = '✅' if roll >= 0.85 else '❌'

    notes_html = ''
    for note in link.get('notes', []):
        notes_html += f'<li>{note}</li>\n'

    return f'''
    <div class="link-card">
      <div class="link-header">
        {pill(vd, vc)} <b>{link['chain']}</b>
        <span class="link-overlap">{link['start']} → {link['end']} ({link['years']}yr)</span>
      </div>
      <table class="metrics-mini">
        <tr>
          <td>{c_ok} Correlation</td><td><b>{corr:.2f}</b>
            <span class="detail">(monthly returns)</span></td>
          <td>{g_ok} CAGR gap</td><td><b>{gap:.2%}</b>
            <span class="detail">({link['label_a']}={link['a_cagr']:.2%} {link['label_b']}={link['b_cagr']:.2%})</span></td>
        </tr>
        <tr>
          <td>{d_ok} Max DD diff</td><td><b>{dd:.1%}</b>pp
            <span class="detail">({link['label_a']}={link['a_dd']:.1%} {link['label_b']}={link['b_dd']:.1%})</span></td>
          <td>{r_ok} Stability</td><td><b>{roll:.2f}</b>
            <span class="detail">(rolling 1Y corr)</span></td>
        </tr>
      </table>
      {'<ul class="link-notes">' + notes_html + '</ul>' if notes_html else ''}
    </div>'''



# Timeline data: (label, start_year, end_year, type, active_start, active_end, validations)
# type: 'proxy', 'fund', 'etf'
# active_start/end: the period this asset is actually USED in the proxy chain (gets border)
# validations: [(from_yr, to_yr, verdict_color, vs_label), ...]
TIMELINES = {
    'us': {
        'total_market': [
            ('^GSPC', 1950, 2026, 'proxy', 1950, 2026, [(2001, 2026, 'gold', 'vs VTI')]),
            ('VTI', 2001, 2026, 'etf', 2001, 2026, []),
        ],
        'scv': [
            ('^GSPC+2%', 1950, 2026, 'proxy', 1950, 1980, [(1980, 2026, 'red', 'vs NAESX (FAIL)')]),
            ('NAESX', 1980, 2026, 'fund', 1980, 2026, [(2004, 2026, 'green', 'vs VBR (PASS)')]),
            ('VBR', 2004, 2026, 'etf', 2004, 2026, []),
        ],
        'lt_bonds': [
            
            ('DGS20 d=18', 1962, 2026, 'proxy', 1962, 2026, [(2002, 2026, 'green', 'vs TLT (PASS)')]),
            ('TLT', 2002, 2026, 'etf', 2002, 2026, []),
        ],
        'st_bonds': [
            ('DGS1 d=1.9', 1962, 2026, 'proxy', 1962, 1976, [(1976, 2026, 'green', 'vs DGS2 (PASS)')]),
            ('DGS2 d=1.9', 1976, 2026, 'proxy', 1976, 2026, [(2002, 2026, 'green', 'vs SHY (PASS)')]),
            ('SHY', 2002, 2026, 'etf', 2002, 2026, []),
        ],
        'gold': [
            ('Milestones', 1950, 2000, 'proxy', 1950, 2000, []),
            ('GC=F', 2000, 2026, 'proxy', 2000, 2026, [(2004, 2026, 'green', 'vs GLD (PASS)')]),
            ('GLD', 2004, 2026, 'etf', 2004, 2026, []),
        ],
    },
    'eu': {
        'total_market': [
            ('^GSPC→EUR', 1971, 2026, 'proxy', 1971, 1984, [(1984, 2026, 'green', 'vs 60/20/20 (PASS)')]),
            ('60/20/20→EUR', 1984, 2026, 'proxy', 1984, 2026, [(2009, 2026, 'green', 'vs IWDA (PASS)')]),
            ('IWDA.AS', 2009, 2026, 'etf', 2009, 2026, []),
        ],
        'scv': [
            ('NAESX→EUR', 1980, 2026, 'proxy', 1980, 2026, [(2018, 2026, 'green', 'vs IUSN (PASS)')]),
            ('IUSN.DE', 2018, 2026, 'etf', 2018, 2026, []),
        ],
        'lt_bonds': [
            ('DGS20 d=18', 1962, 2026, 'proxy', 1962, 2026, [(2018, 2026, 'green', 'vs DTLA (PASS)')]),
            ('DTLA.L', 2018, 2026, 'etf', 2018, 2026, []),
        ],
        'st_bonds': [
            ('DGS1 d=1.9', 1962, 2026, 'proxy', 1962, 1976, [(1976, 2026, 'green', 'vs DGS2 (PASS)')]),
            ('DGS2 d=1.9', 1976, 2026, 'proxy', 1976, 2026, [(2017, 2026, 'green', 'vs IBTA (PASS)')]),
            ('IBTA.L', 2017, 2026, 'etf', 2017, 2026, []),
        ],
        'gold': [
            ('Milestones', 1950, 2000, 'proxy', 1950, 2000, []),
            ('GC=F', 2000, 2026, 'proxy', 2000, 2026, [(2011, 2026, 'green', 'vs IGLN (PASS)')]),
            ('IGLN.L', 2011, 2026, 'etf', 2011, 2026, []),
        ],
    },
}

TIMELINE_COLORS = {
    'proxy': 'rgba(100,116,139,0.4)',   # soft slate
    'fund': 'rgba(148,163,184,0.4)',    # soft gray
    'etf': 'rgba(203,213,225,0.4)',     # soft light
}

# Quadrant colors (matching build_market_regimes.py)
Q_COLORS = {
    'Q1': '#60a5fa', 'Q2': '#c084fc', 'Q3': '#67e8f9', 'Q4': '#f9a8d4',
}

with open(os.path.join(DATA, 'regimes.json')) as f:
    _regimes_data = json.load(f)
_us_regimes = _regimes_data['us']
_eu_regimes = _regimes_data['eu']

def _year_to_q(yr, region):
    r = _us_regimes if region == 'us' else _eu_regimes
    d = r.get(str(yr))
    return d['q'] if d else 'Q1'


def build_timeline(region, comp, vd_color=None):
    tl = TIMELINES.get(region, {}).get(comp, [])
    if not tl:
        return ''
    all_years = []
    for item in tl:
        all_years.extend([item[1], item[2]])
    min_yr = 1950  # fixed start for all timelines
    max_yr = max(all_years)
    span = max_yr - min_yr
    if span == 0:
        return ''

    ov_colors = {'green': 'rgba(34,197,94,0.45)', 'gold': 'rgba(234,179,8,0.45)', 'red': 'rgba(239,68,68,0.45)'}

    def pct(yr):
        return round((yr - min_yr) / span * 100, 1)

    rows = ''
    for label, start, end, ttype, act_start, act_end, validations in tl:
        base_color = TIMELINE_COLORS.get(ttype, '#94a3b8')
        bars = ''

        # Build segments: base color + validation overlays
        if not validations:
            bars = ('<div class="tl-bar" style="left:' + str(pct(start)) + '%;'
                    'width:' + str(pct(end) - pct(start)) + '%;'
                    'background:' + base_color + ';"></div>')
        else:
            # Collect all boundaries
            points = sorted(set([start] + [v[0] for v in validations] + [v[1] for v in validations] + [end]))
            for i in range(len(points) - 1):
                seg_start = points[i]
                seg_end = points[i + 1]
                if seg_end <= start or seg_start >= end:
                    continue
                seg_start = max(seg_start, start)
                seg_end = min(seg_end, end)
                # Check if this segment has a validation
                seg_color = base_color
                seg_opacity = '1'
                seg_title = ''
                for v_from, v_to, v_color, v_label in validations:
                    if seg_start >= v_from and seg_end <= v_to and v_color:
                        seg_color = ov_colors.get(v_color, base_color)
                        seg_opacity = '1'
                        seg_title = v_label
                        break
                title_attr = ' title="' + seg_title + '"' if seg_title else ''
                bars += ('<div class="tl-bar" style="left:' + str(pct(seg_start)) + '%;'
                         'width:' + str(pct(seg_end) - pct(seg_start)) + '%;'
                         'background:' + seg_color + ';opacity:' + seg_opacity + ';"'
                         + title_attr + '></div>')

        # Active period border overlay
        active_border = ('<div class="tl-active" style="left:' + str(pct(act_start)) + '%;'
                        'width:' + str(pct(act_end) - pct(act_start)) + '%;"></div>')

        rows += ('<div class="tl-row">'
                 '<span class="tl-label">' + label + '</span>'
                 '<div class="tl-track">' + bars + active_border + '</div>'
                 '</div>')

    # Decade markers
    ticks = ''
    for yr in range(((min_yr // 10) + 1) * 10, max_yr, 10):
        ticks += '<span class="tl-tick" style="left:' + str(pct(yr)) + '%">' + str(yr) + '</span>'

    legend = (
        '<div class="tl-legend">'
        '<span><span class="tl-dot" style="background:rgba(100,116,139,0.5)"></span>Proxy</span>'
        '<span><span class="tl-dot" style="background:rgba(148,163,184,0.5)"></span>Fund/Futures</span>'
        '<span><span class="tl-dot" style="background:rgba(203,213,225,0.5)"></span>Real ETF</span>'
        '<span><span class="tl-dot" style="background:rgba(34,197,94,0.45)"></span>PASS</span>'
        '<span><span class="tl-dot" style="background:rgba(234,179,8,0.45)"></span>MARGINAL</span>'
        '<span><span class="tl-dot" style="background:rgba(239,68,68,0.45)"></span>FAIL</span>'
        '<span><span class="tl-dot tl-dot-active"></span>Active in chain</span>'
        '</div>'
        '<div class="tl-legend" style="margin-top:0.2rem">'
        '<span style="color:#64748b;font-size:0.68rem;margin-right:0.3rem">Regimes:</span>'
        '<span><span class="tl-dot" style="background:#60a5fa;opacity:0.5"></span>Q1</span>'
        '<span><span class="tl-dot" style="background:#c084fc;opacity:0.5"></span>Q2</span>'
        '<span><span class="tl-dot" style="background:#67e8f9;opacity:0.5"></span>Q3</span>'
        '<span><span class="tl-dot" style="background:#f9a8d4;opacity:0.5"></span>Q4</span>'
        '</div>'
    )

    # Quadrant regime bar
    q_bars = ''
    for yr in range(min_yr, max_yr):
        q = _year_to_q(yr, region)
        color = Q_COLORS[q]
        q_bars += ('<div class="tl-bar" style="left:' + str(pct(yr)) + '%;'
                   'width:' + str(pct(yr + 1) - pct(yr)) + '%;'
                   'background:' + color + ';opacity:0.35;"'
                   ' title="' + str(yr) + ': ' + q + '"></div>')
    regime_row = ('<div class="tl-row">'
                  '<span class="tl-label" style="font-size:0.65rem">Regime</span>'
                  '<div class="tl-track">' + q_bars + '</div>'
                  '</div>')

    return (
        '<div class="timeline">'
        + rows
        + regime_row
        + '<div class="tl-axis">'
        + '<span class="tl-tick" style="left:0%">' + str(min_yr) + '</span>'
        + ticks
        + '<span class="tl-tick" style="left:100%">' + str(max_yr) + '</span>'
        + '</div>'
        + legend
        + '</div>'
    )

def _build_chain_label(data):
    chain = data['chain']
    etf = data['etf']
    # Split chain at the ETF: everything before is proxy, the ETF itself is separate
    # Chain format: "proxy1 (year) -> proxy2 (year) -> ETF (year)"
    parts = [p.strip() for p in chain.split('→')]
    proxy_parts = []
    etf_part = ''
    for p in parts:
        if etf.split('.')[0] in p or etf in p:
            etf_part = p
        else:
            proxy_parts.append(p)
    proxy_chain = ' → '.join(proxy_parts) if proxy_parts else '—'
    etf_label = etf_part if etf_part else etf
    return (
        '<div class="chain-label">'
        'Proxy: <code>' + proxy_chain + '</code>'
        '    vs    '
        'ETF: <code>' + etf_label + '</code>'
        '</div>'
    )

def _comp_verdict_color(data):
    if not data['links']:
        return None
    link = data['links'][-1]  # last link = ETF overlap
    vd, vc = verdict(link)
    return vc

_chart_id = [0]
def _next_id():
    _chart_id[0] += 1
    return f'chart{_chart_id[0]}'

def build_chart(region, comp, mode):
    """Build a plotly chart div for a component. mode: 'full' or 'overlap'."""
    cdata = chart_data.get(region, {}).get(comp)
    if not cdata:
        return '<p style="color:var(--muted);font-size:0.85rem">No chart data available.</p>'

    links = results[region][comp]['links']
    overlap_start = links[-1]['start'] if links else None

    series = [dict(s) for s in cdata['proxy'] + cdata['etf']]

    if mode == 'overlap' and overlap_start:
        trimmed = []
        for s in series:
            idx = next((i for i, d in enumerate(s['dates']) if d >= overlap_start[:7]), 0)
            dates = s['dates'][idx:]
            vals = s['values'][idx:]
            if vals:
                base = vals[0]
                vals = [round(v / base * 100, 1) for v in vals]
            trimmed.append({'label': s['label'], 'dates': dates, 'values': vals})
        series = trimmed

    # Compute drawdown for each series
    dd_series = []
    for s in series:
        vals = s['values']
        peak = 0
        dd_vals = []
        for v in vals:
            if v > peak:
                peak = v
            dd_vals.append(round((v / peak - 1) * 100, 2) if peak > 0 else 0)
        dd_series.append({'label': s['label'], 'dates': s['dates'], 'values': dd_vals})

    cid = _next_id()
    etf_label = results[region][comp]['etf']
    chart_json = json.dumps({'series': series, 'dd': dd_series}, separators=(',', ':'))
    etf_names = json.dumps([etf_label.split('.')[0]])

    return (
        '<div class="chart-wrap">'
        '<div id="' + cid + '" style="width:100%;height:400px;"'
        ' data-chart=\'' + chart_json + '\' data-etf=\'' + etf_names + '\'></div>'
        '</div>'
    )


def build_component(region, comp, data):
    """Build HTML for one component."""
    links_html = ''
    for link in data['links']:
        links_html += build_link_card(link)

    comp_notes = ''
    for note in data.get('notes', []):
        comp_notes += '<li>' + note + '</li>'

    nice = {
        'total_market': 'Total Market', 'scv': 'Small Cap Value',
        'lt_bonds': 'Long-Term Bonds', 'st_bonds': 'Short-Term Bonds', 'gold': 'Gold',
    }

    # Build asset badges for ETF + all proxies in the chain
    chain = data['chain']
    seen = set()
    badges = ''
    # ETF first
    b = asset_badge(data['etf'])
    if b:
        badges += b
        seen.add(data['etf'])
    # Then proxies from chain
    for tok in re.split(r'[\s\(\)→,]+', chain):
        tok = tok.strip()
        if not tok or tok in seen:
            continue
        # For compound keys like DGS20+DGS30, show individual parts AND the compound
        if '+' in tok and tok in ASSETS:
            for part in tok.split('+'):
                if part in ASSETS and part not in seen:
                    badges += asset_badge(part)
                    seen.add(part)
            badges += asset_badge(tok)
            seen.add(tok)
        elif tok in ASSETS:
            badges += asset_badge(tok)
            seen.add(tok)

    assets_html = '<div class="assets-grid">' + badges + '</div>' if badges else ''
    notes_html = '<div class="comp-notes"><b>⚠️ Limitations:</b><ul>' + comp_notes + '</ul></div>' if comp_notes else ''

    tid = region + '_' + comp
    full_chart = build_chart(region, comp, 'full')
    overlap_chart = build_chart(region, comp, 'overlap')

    tabs_html = (
        '<div class="tabs" data-tabs="' + tid + '">'
        '<button class="tab-btn active" onclick="switchTab(\'' + tid + '\',0)">📊 Summary</button>'
        '<button class="tab-btn" onclick="switchTab(\'' + tid + '\',1)">📈 Full Period</button>'
        '<button class="tab-btn" onclick="switchTab(\'' + tid + '\',2)">🔍 ETF Overlap</button>'
        '</div>'
        '<div class="tab-panels" data-tabs="' + tid + '">'
        '<div class="tab-panel active">' + links_html + notes_html + '</div>'
        '<div class="tab-panel">' + full_chart + '</div>'
        '<div class="tab-panel">' + overlap_chart + '</div>'
        '</div>'
    )

    return (
        '<div class="component">'
        + '<h3>' + nice.get(comp, comp) + ' — ' + data['etf'] + '</h3>'
        + _build_chain_label(data)
        + build_timeline(region, comp, _comp_verdict_color(data))
        + assets_html
        + tabs_html
        + '</div>'
    )


# Component-level warnings (for unvalidatable deep history)
COMP_WARNINGS = {
    ('us', 'gold'): ('gold', 'Milestones (1950-2000) cannot be validated against any real asset. Interpolated annual prices are reliable for decade-level CAGR, but NOT for drawdown or volatility analysis pre-2000.'),
    ('eu', 'gold'): ('gold', 'Same as US: Milestones pre-2000 are unvalidatable. Reliable for CAGR only.'),
    ('eu', 'total_market'): ('gold', 'Pre-1984: ^GSPC only (no ^FTSE/^N225 blend). Pre-1999: CHF/USD as EUR proxy. These periods cannot be validated against IWDA.AS (starts 2009).'),
}

def build_summary_table(region, data):
    """Build summary table for a region."""
    nice = {
        'total_market': 'Total Market', 'scv': 'Small Cap Value',
        'lt_bonds': 'Long-Term Bonds', 'st_bonds': 'Short-Term Bonds', 'gold': 'Gold',
    }
    rows = ''
    for comp in ['total_market', 'scv', 'lt_bonds', 'st_bonds', 'gold']:
        if comp not in data:
            continue
        d = data[comp]
        if not d['links']:
            continue
        link = d['links'][-1]
        vd, vc = verdict(link)

        # Check weakest link in the chain
        worst_chain_vc = None
        worst_chain_tip = ''
        # Check component-level warnings (unvalidatable deep history)
        comp_warn = COMP_WARNINGS.get((region, comp))
        if comp_warn:
            cw_color, cw_tip = comp_warn
            if worst_chain_vc != 'red':
                worst_chain_vc = cw_color
                worst_chain_tip = cw_tip
        for lnk in d['links'][:-1]:
            lnk_vd, lnk_vc = verdict(lnk)
            if lnk_vc == 'red':
                worst_chain_vc = 'red'
                worst_chain_tip = (lnk['chain'] + ': FAIL — '
                    'corr=' + str(lnk['monthly_corr']) + ', '
                    'DD diff=' + f"{lnk['dd_diff']:.1%}" + 'pp. '
                    'Deep history before ' + str(lnk['start']) + ' may be unreliable.')
                break
            elif lnk_vc == 'gold' and worst_chain_vc != 'red':
                worst_chain_vc = 'gold'
                worst_chain_tip = (lnk['chain'] + ': MARGINAL — '
                    'corr=' + str(lnk['monthly_corr']) + ', '
                    'CAGR gap=' + f"{lnk['cagr_gap']:.2%}" + '. '
                    'Deep history may have some bias.')

        # Downgrade verdict if chain has weak links
        if worst_chain_vc == 'red' and vc == 'green':
            vd, vc = 'MARGINAL', 'gold'
        
        # Build verdict cell
        if worst_chain_vc:
            verdict_html = (pill(vd, vc)
                + ' <span class="chain-warn" title="' + worst_chain_tip + '">⚠️</span>')
        else:
            verdict_html = pill(vd, vc)

        # Split chain into proxy vs ETF
        chain = d['chain']
        etf = d['etf']
        parts = [p.strip() for p in chain.split('→')]
        proxy_parts = [p for p in parts if etf.split('.')[0] not in p and etf not in p]
        proxy_str = ' → '.join(proxy_parts) if proxy_parts else '—'
        etf_part = next((p for p in parts if etf.split('.')[0] in p or etf in p), etf)

        rows += (
            '<tr>'
            '<td>' + nice.get(comp, comp) + '</td>'
            '<td><code>' + proxy_str + '</code></td>'
            '<td><code>' + etf_part + '</code></td>'
            '<td>' + f"{link['monthly_corr']:.2f}" + '</td>'
            '<td>' + f"{link['roll1y_corr']:.2f}" + '</td>'
            '<td>' + f"{link['cagr_gap']:.2%}" + '</td>'
            '<td>' + f"{link['dd_diff']:.1%}" + 'pp</td>'
            '<td>' + verdict_html + '</td>'
            '</tr>'
        )

    return (
        '<table class="summary-table">'
        '<thead><tr>'
        '<th>Component</th><th>Proxy</th><th>ETF</th>'
        '<th>Correlation</th><th>Stability</th><th>CAGR Gap</th><th>DD Diff</th><th>Verdict</th>'
        '</tr></thead>'
        '<tbody>' + rows + '</tbody>'
        '</table>'
    )


# ── Build HTML ────────────────────────────────────────────────

# ── Build HTML ────────────────────────────────────────────────

def build_region(region):
    data = results[region]
    components = ""
    for comp in ["total_market", "scv", "lt_bonds", "st_bonds", "gold"]:
        if comp in data:
            components += build_component(region, comp, data[comp])
    return build_summary_table(region, data) + components


us_content = build_region("us")
eu_content = build_region("eu")

CSS = """
  :root {
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6;
    --green: #22c55e; --red: #ef4444; --gold: #eab308;
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
  code {
    background: rgba(59,130,246,0.1); padding: 0.15rem 0.4rem;
    border-radius: 4px; font-size: 0.82rem; color: var(--accent);
  }
  .pill {
    display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
    font-size: 0.75rem; font-weight: 700;
  }
  .pill-green { background: rgba(34,197,94,0.15); color: var(--green); }
  .pill-gold { background: rgba(234,179,8,0.15); color: var(--gold); }
  .pill-red { background: rgba(239,68,68,0.15); color: var(--red); }
  .pill-etf { background: rgba(203,213,225,0.15); color: #cbd5e1; }
  .pill-index { background: rgba(148,163,184,0.15); color: #94a3b8; }
  .pill-fund { background: rgba(148,163,184,0.15); color: #94a3b8; }
  .pill-synth { background: rgba(100,116,139,0.15); color: #64748b; }
  .section {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 12px; padding: 1.5rem; margin: 1.5rem 0;
  }
  .component {
    border: 1px solid var(--border); border-radius: 8px;
    padding: 1rem; margin: 1rem 0;
  }
  .chain-label { font-size: 0.82rem; color: var(--muted); margin-bottom: 0.8rem; }
  .link-card {
    background: rgba(255,255,255,0.02); border: 1px solid var(--border);
    border-radius: 8px; padding: 0.8rem; margin: 0.5rem 0;
  }
  .link-header {
    display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    margin-bottom: 0.5rem;
  }
  .link-overlap { font-size: 0.78rem; color: var(--muted); margin-left: auto; }
  .metrics-mini { width: 100%; font-size: 0.82rem; border-collapse: collapse; }
  .metrics-mini td { padding: 0.25rem 0.5rem; border: none; }
  .detail { font-size: 0.72rem; color: var(--muted); }
  .link-notes {
    font-size: 0.8rem; color: var(--muted); margin: 0.5rem 0 0 1.2rem; list-style: disc;
  }
  .link-notes li { margin: 0.2rem 0; }
  .comp-notes {
    background: rgba(234,179,8,0.06); border: 1px solid rgba(234,179,8,0.15);
    border-radius: 6px; padding: 0.6rem 0.8rem; margin-top: 0.8rem;
    font-size: 0.82rem; color: var(--muted);
  }
  .comp-notes b { color: var(--gold); }
  .comp-notes ul { margin: 0.3rem 0 0 1.2rem; }
  .summary-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; margin: 1rem 0; }
  .summary-table th, .summary-table td {
    padding: 0.5rem 0.7rem; border-bottom: 1px solid var(--border); text-align: left;
  }
  .summary-table th { color: var(--accent); font-weight: 600; background: rgba(59,130,246,0.04); }
  .summary-table tr:hover td { background: rgba(59,130,246,0.04); }
  .chain-warn {
    cursor: help; font-size: 0.9rem; position: relative;
  }
  .chain-warn::after {
    content: attr(title); position: absolute; left: 1.5rem; bottom: 100%;
    width: 300px; padding: 0.5rem 0.7rem;
    background: var(--bg); color: var(--text); border: 1px solid var(--border);
    border-radius: 6px; font-size: 0.75rem; line-height: 1.4;
    pointer-events: none; opacity: 0; transition: opacity 0.15s;
    z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    white-space: normal;
  }
  .chain-warn:hover::after { opacity: 1; }
  .note {
    background: rgba(59,130,246,0.06); border: 1px solid rgba(59,130,246,0.15);
    border-radius: 8px; padding: 0.8rem; margin: 1rem 0; font-size: 0.85rem;
  }
  .thresholds { display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem; font-size: 0.82rem; margin: 0.5rem 0; }
  .assets-grid {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem;
    margin: 0.8rem 0;
  }
  .asset-badge {
    border-left: 3px solid var(--border); padding: 0.35rem 0.6rem;
    font-size: 0.78rem; background: none;
  }
  .asset-badge b { color: var(--text); }
  .asset-desc {
    font-size: 0.7rem; color: var(--muted); margin-top: 0.1rem; line-height: 1.35;
    opacity: 0.8;
  }
  .timeline {
    background: rgba(0,0,0,0.2); border: 1px solid var(--border);
    border-radius: 8px; padding: 0.8rem 1rem 1.5rem; margin: 0.8rem 0;
  }
  .tl-row { display: flex; align-items: center; margin: 0.2rem 0; }
  .tl-label {
    width: 130px; flex-shrink: 0; font-size: 0.75rem; color: var(--muted);
    text-align: right; padding-right: 0.6rem; white-space: nowrap;
  }
  .tl-track {
    flex: 1; height: 14px; position: relative;
    background: rgba(255,255,255,0.05); border-radius: 3px;
  }
  .tl-bar {
    position: absolute; top: 1px; height: 12px; border-radius: 3px;
    min-width: 2px;
  }
  .tl-active {
    position: absolute; top: -1px; height: 16px; border-radius: 4px;
    border: 2px solid rgba(96,165,250,0.8); pointer-events: none;
    box-sizing: border-box;
  }
  .tl-dot-active {
    border: 2px solid rgba(96,165,250,0.8); background: none !important;
  }
  .tl-axis {
    position: relative; height: 18px; margin-left: 130px; margin-top: 0.3rem;
    border-top: 1px solid var(--border);
  }
  .tl-tick {
    position: absolute; top: 2px; font-size: 0.65rem; color: var(--muted);
    transform: translateX(-50%);
  }
  .tl-legend {
    display: flex; gap: 1rem; margin: 0.6rem 0 0 130px;
    font-size: 0.72rem; color: var(--muted);
  }
  .tl-dot {
    display: inline-block; width: 10px; height: 10px; border-radius: 2px;
    margin-right: 0.3rem; vertical-align: middle;
  }
  .region { display: none; }
  .region.active { display: block; }
  /* Tabs */
  .tabs {
    display: flex; gap: 0.25rem; margin: 0.8rem 0 0;
    border-bottom: 1px solid var(--border);
  }
  .tab-btn {
    padding: 0.35rem 0.9rem; border: none; background: none;
    color: var(--muted); font-size: 0.8rem; cursor: pointer;
    border-bottom: 2px solid transparent; margin-bottom: -1px;
    transition: all 0.15s;
  }
  .tab-btn:hover { color: var(--text); }
  .tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
  .tab-panels { margin-top: 0.6rem; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }
  .chart-wrap {
    border-radius: 8px; margin: 0.4rem 0;
  }
"""

JS = """
function applyRegion() {
  var region = window.location.hash.replace('#', '') || 'us';
  document.querySelectorAll('.region').forEach(function(el) {
    el.classList.toggle('active', el.dataset.region === region);
  });
}
window.addEventListener('hashchange', applyRegion);
applyRegion();

function switchTab(tid, idx) {
  var btns = document.querySelectorAll('.tabs[data-tabs="'+tid+'"] .tab-btn');
  var panels = document.querySelectorAll('.tab-panels[data-tabs="'+tid+'"] .tab-panel');
  btns.forEach(function(b,i){ b.classList.toggle('active', i===idx); });
  panels.forEach(function(p,i){
    p.classList.toggle('active', i===idx);
    if (i===idx) {
      p.querySelectorAll('div[data-chart]').forEach(function(el) {
        if (!el._drawn) {
          var d = JSON.parse(el.getAttribute('data-chart'));
          var e = JSON.parse(el.getAttribute('data-etf'));
          drawPlotlyChart(el.id, d.series, d.dd, e);
          el._drawn = true;
        }
      });
    }
  });
}

var PROXY_COLORS = ['#64748b','#94a3b8','#b0bec5','#78909c','#546e7a'];
var ETF_COLOR = '#3b82f6';

function drawPlotlyChart(divId, series, ddSeries, etfLabels) {
  var traces = [];
  var proxyIdx = 0;

  series.forEach(function(s) {
    var isEtf = etfLabels.some(function(e){ return s.label.indexOf(e) >= 0; });
    var color = isEtf ? ETF_COLOR : PROXY_COLORS[proxyIdx++ % PROXY_COLORS.length];
    traces.push({
      x: s.dates, y: s.values, name: s.label,
      type: 'scatter', mode: 'lines',
      line: { color: color, width: isEtf ? 2 : 1.2 },
      opacity: isEtf ? 1 : 0.75,
      xaxis: 'x', yaxis: 'y',
      hovertemplate: '<b>%{fullData.name}</b><br>%{x}<br>%{y:.1f}<extra></extra>'
    });
  });

  proxyIdx = 0;
  ddSeries.forEach(function(s) {
    var isEtf = etfLabels.some(function(e){ return s.label.indexOf(e) >= 0; });
    var color = isEtf ? ETF_COLOR : PROXY_COLORS[proxyIdx++ % PROXY_COLORS.length];
    traces.push({
      x: s.dates, y: s.values, name: s.label,
      type: 'scatter', mode: 'lines', fill: 'tozeroy',
      line: { color: color, width: isEtf ? 1.5 : 1 },
      fillcolor: color.replace(')', ',0.15)').replace('rgb', 'rgba'),
      opacity: isEtf ? 0.9 : 0.5,
      xaxis: 'x', yaxis: 'y2',
      showlegend: false,
      hovertemplate: '<b>%{fullData.name}</b><br>%{x}<br>%{y:.1f}%<extra></extra>'
    });
  });

  var layout = {
    paper_bgcolor: 'transparent', plot_bgcolor: '#0a1628',
    font: { family: 'Inter,sans-serif', color: '#94a3b8', size: 11 },
    margin: { t: 10, r: 20, b: 40, l: 60 },
    height: 400,
    grid: { rows: 2, columns: 1, pattern: 'independent', roworder: 'top to bottom' },
    xaxis:  { domain: [0,1], anchor: 'y',  showgrid: true, gridcolor: '#1e293b', zeroline: false, tickfont: {size:10} },
    xaxis2: { domain: [0,1], anchor: 'y2', showgrid: true, gridcolor: '#1e293b', zeroline: false, tickfont: {size:10}, matches: 'x' },
    yaxis:  { domain: [0.35,1],  type: 'log', showgrid: true, gridcolor: '#1e293b', tickfont: {size:10}, title: {text:'Growth (log)', font:{size:10}} },
    yaxis2: { domain: [0,0.30], showgrid: true, gridcolor: '#1e293b', tickfont: {size:10}, title: {text:'Drawdown %', font:{size:10}}, ticksuffix: '%' },
    legend: { bgcolor: 'transparent', font: {size: 10}, orientation: 'h', y: -0.08 },
    hovermode: 'x unified',
    hoverlabel: { bgcolor: '#1e293b', bordercolor: '#334155', font: {color:'#e2e8f0', size:11} }
  };

  var config = { displayModeBar: false, responsive: true, doubleClick: 'reset+autosize' };
  Plotly.newPlot(divId, traces, layout, config);
}
"""

intro = """
<h2>Proxy Validation</h2>
<p class="subtitle">Can we trust the proxies to represent real ETFs over decades?</p>
<div class="section">
  <p>Each Golden Butterfly component needs a proxy that extends back to 1962+ for deep backtesting.
  Below, each proxy is validated against the real ETF on their <b>overlapping period</b>.
  For spliced proxies, each link in the chain is validated separately.</p>
  <div class="note">
    <b>Validation metrics (monthly returns):</b>
    <div class="thresholds">
      <div>✅ Correlation ≥ 0.90 — do they move together? (computed on monthly returns)</div>
      <div>✅ CAGR gap ≤ 1% ideal, ≤ 2% acceptable — do they arrive at the same place?</div>
      <div>✅ Max DD difference ≤ 5pp — do they crash the same way?</div>
      <div>✅ Stability ≥ 0.85 — is the tracking consistent? (rolling 1-year correlation)</div>
    </div>
  </div>
</div>
"""


html_parts = [
    '<!DOCTYPE html>',
    '<html lang="en"><head>',
    '<meta charset="UTF-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '<title>Proxy Validation</title>',
    '<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>',
    '<style>' + CSS + '</style>',
    '</head><body>',
    intro,
    '<div class="region" data-region="us"><div class="section"><h2>US Proxy Validation</h2>',
    us_content,
    '</div></div>',
    '<div class="region" data-region="eu"><div class="section"><h2>EU Proxy Validation</h2>',
    eu_content,
    '</div></div>',
    '<script>' + JS + '</script>',
    '</body></html>',
]
html = '\n'.join(html_parts)

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, 'proxy_validation.html')
with open(path, 'w') as f:
    f.write(html)
print(f'\u2705 {path} ({len(html)//1024} KB)')

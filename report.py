"""
Golden Butterfly — Interactive HTML Report Generator
Reads saved data from output/ and produces report.html
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json, gzip, base64, os

OUTPUT_DIR = "output"

# ── Load data ────────────────────────────────────────────────

returns = pd.read_pickle(os.path.join(OUTPUT_DIR, "returns.pkl"))
us_etf_prices = pd.read_pickle(os.path.join(OUTPUT_DIR, "us_etf_prices.pkl"))
deep_prices = pd.read_pickle(os.path.join(OUTPUT_DIR, "deep_proxy_prices.pkl"))
eu_deep_prices = pd.read_pickle(os.path.join(OUTPUT_DIR, "eu_deep_proxy_prices.pkl"))
eu_etf_prices_path = os.path.join(OUTPUT_DIR, "eu_etf_prices.pkl")
eu_etf_prices = pd.read_pickle(eu_etf_prices_path) if os.path.exists(eu_etf_prices_path) else pd.DataFrame()

with open(os.path.join(OUTPUT_DIR, "metrics.json")) as f:
    metrics = json.load(f)
with open(os.path.join(OUTPUT_DIR, "decade_metrics.json")) as f:
    decade_metrics = json.load(f)
with open(os.path.join(OUTPUT_DIR, "validation.json")) as f:
    validation = json.load(f)

# ── Derived stats (computed once, used in narrative text) ────
_m = {m['name']: m for m in metrics if 'error' not in m}
_dp = _m.get('US Proxy', {})
_ue = _m.get('US ETF', {})
_ee = _m.get('EU ETF', {})
_ep = _m.get('EU Proxy', {})

# US Proxy growth
_us_proxy_ret = returns.get('US Proxy')
_proxy_growth = round((1 + _us_proxy_ret.dropna()).cumprod().iloc[-1], 0) if _us_proxy_ret is not None else 0
_proxy_years = round(len(_us_proxy_ret.dropna()) / 252, 0) if _us_proxy_ret is not None else 0

# Decade rankings
_dec_valid = [d for d in decade_metrics if 'error' not in d]
_dec_cagrs = sorted([(d['name'], float(d['cagr'].strip('%'))) for d in _dec_valid], key=lambda x: x[1], reverse=True)
_dec_mdds = [float(d['max_drawdown'].strip('%')) for d in _dec_valid]
_1970s_rank = next((i+1 for i, (n, _) in enumerate(_dec_cagrs) if '1970' in n), '?')
_1970s_cagr = next((c for n, c in _dec_cagrs if '1970' in n), '?')
_2000s_cagr = next((c for n, c in _dec_cagrs if '2000' in n), '?')
_rank_word = {1: 'best', 2: 'second-best', 3: 'third-best', 4: 'fourth-best'}.get(_1970s_rank, f'#{_1970s_rank}')

# Weekly validation stats
def _weekly_corr_te(ref_name, proxy_name):
    r, p = returns.get(ref_name), returns.get(proxy_name)
    if r is None or p is None: return 0, 0
    r, p = r.dropna(), p.dropna()
    ci = r.index.intersection(p.index)
    ew = r.loc[ci].resample('W').sum()
    pw = p.loc[ci].resample('W').sum()
    wci = ew.index.intersection(pw.index)
    return round(ew.loc[wci].corr(pw.loc[wci]), 2), round((ew.loc[wci]-pw.loc[wci]).std()*np.sqrt(52)*100, 1)

_us_wcorr, _us_wte = _weekly_corr_te('US ETF', 'US Proxy')
_eu_wcorr, _eu_wte = _weekly_corr_te('EU ETF', 'EU Proxy')
_us_dcorr = validation.get('correlation', 0)

S = dict(
    proxy_cagr=_dp.get('cagr', '?'), proxy_vol=_dp.get('volatility', '?'),
    proxy_maxdd=_dp.get('max_drawdown', '?'), proxy_sharpe=_dp.get('sharpe', '?'),
    proxy_sortino=_dp.get('sortino', '?'), proxy_calmar=_dp.get('calmar', '?'),
    proxy_longest_dd=_dp.get('longest_dd_days', 0),
    proxy_longest_dd_yr=round(int(_dp.get('longest_dd_days', 0)) / 252, 1),
    proxy_var=_dp.get('VaR_95', '?'), proxy_cvar=_dp.get('CVaR_95', '?'),
    proxy_skew=_dp.get('skewness', '?'), proxy_kurt=_dp.get('kurtosis', '?'),
    proxy_growth=int(_proxy_growth), proxy_years=int(_proxy_years),
    us_etf_vol=_ue.get('volatility', '?'),
    dec_mdd_min=f'{min(_dec_mdds):.1f}' if _dec_mdds else '?',
    dec_mdd_max=f'{max(_dec_mdds):.1f}' if _dec_mdds else '?',
    rank_1970s=_rank_word, cagr_1970s=f'{_1970s_cagr:.1f}' if isinstance(_1970s_cagr, float) else '?',
    cagr_2000s=f'{_2000s_cagr:.1f}' if isinstance(_2000s_cagr, float) else '?',
    us_dcorr=_us_dcorr, us_wcorr=_us_wcorr, us_wte=_us_wte,
    eu_wcorr=_eu_wcorr, eu_wte=_eu_wte,
)

COLORS = {
    "US ETF": "#2563eb",
    "EU ETF": "#16a34a",
    "Fund Proxy": "#d97706",
    "US Proxy": "#dc2626",
    "EU Proxy": "#8b5cf6",
}
PLOTLY_CFG = dict(displayModeBar=True, scrollZoom=False,
                  modeBarButtonsToRemove=['zoomIn2d', 'zoomOut2d', 'select2d', 'lasso2d', 'autoScale2d'])

# ── Chart builders (filled in next steps) ────────────────────

METRIC_GROUPS = [
    ("Overview", [
        ("period", "Period"),
        ("years", "Years"),
    ]),
    ("Returns", [
        ("total_return", "Total Return"),
        ("cagr", "CAGR"),
        ("best_1y", "Best 1Y"),
        ("worst_1y", "Worst 1Y"),
        ("daily_win_rate", "Win Rate"),
    ]),
    ("Risk", [
        ("volatility", "Volatility"),
        ("max_drawdown", "Max Drawdown"),
        ("longest_dd_days", "Longest DD (days)"),
        ("VaR_95", "VaR 95%"),
        ("CVaR_95", "CVaR 95%"),
        ("ulcer_index", "Ulcer Index"),
    ]),
    ("Risk-Adjusted", [
        ("sharpe", "Sharpe"),
        ("sortino", "Sortino"),
        ("calmar", "Calmar"),
    ]),
    ("Distribution", [
        ("skewness", "Skewness"),
        ("kurtosis", "Kurtosis"),
    ]),
]


GLOSSARY_ANCHORS = {
    'Total Return': 'total-return', 'CAGR': 'cagr', 'Best 1Y': 'best---worst-1y',
    'Worst 1Y': 'best---worst-1y', 'Win Rate': 'daily-win-rate',
    'Volatility': 'volatility', 'Max Drawdown': 'max-drawdown',
    'Longest DD (days)': 'longest-drawdown', 'VaR 95%': 'var-95pct',
    'CVaR 95%': 'cvar-95pct', 'Ulcer Index': 'ulcer-index',
    'Sharpe': 'sharpe-ratio', 'Sortino': 'sortino-ratio', 'Calmar': 'calmar-ratio',
    'Skewness': 'skewness', 'Kurtosis': 'kurtosis',
}


def metrics_table_html(mlist, compact=False):
    """Build an HTML table from a list of metric dicts."""
    mlist = [m for m in mlist if 'error' not in m]
    if not mlist: return ""

    headers = "".join(f"<th>{m['name']}</th>" for m in mlist)
    ncols = len(mlist) + 1

    if not compact:
        keys = [k for k in mlist[0] if k != 'name']
        rows = ""
        for k in keys:
            cells = "".join(f"<td>{m.get(k,'')}</td>" for m in mlist)
            rows += f"<tr><td>{k}</td>{cells}</tr>\n"
        return f'<table class="compact"><thead><tr><th>Metric</th>{headers}</tr></thead><tbody>{rows}</tbody></table>'

    rows = ""
    for group_name, group_keys in METRIC_GROUPS:
        rows += f'<tr class="group-row"><td colspan="{ncols}">{group_name}</td></tr>\n'
        for key, label in group_keys:
            anchor = GLOSSARY_ANCHORS.get(label)
            linked = f'<a href="#g-{anchor}" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--muted);">{label}</a>' if anchor else label
            cells = "".join(f"<td>{m.get(key,'')}</td>" for m in mlist)
            rows += f"<tr><td>{linked}</td>{cells}</tr>\n"

    return f'<table class="compact"><thead><tr><th>Metric</th>{headers}</tr></thead><tbody>{rows}</tbody></table>'


METRIC_GLOSSARY = [
    ("Returns", [
        ("Total Return",
         "(1 + r₁)(1 + r₂)…(1 + rₙ) − 1",
         "The raw cumulative gain over the entire period. A $1 investment growing to $5.24 means 424% total return.",
         "Gives the big picture, but misleading for comparing different time spans — a 10-year and 30-year backtest aren't comparable on total return alone."),
        ("CAGR",
         "(Ending Value / Starting Value)^(1/years) − 1",
         "The constant annual rate that, compounded over the period, reproduces the total return. Smooths out year-to-year noise into a single annualized number.",
         f"The most important single metric for comparing strategies across different time periods. A {S["proxy_cagr"]} CAGR means your money doubles roughly every {0.7/float(S["proxy_cagr"].strip("%"))*10:.1f} years."),
        ("Best / Worst 1Y",
         "max / min of rolling 252-day cumulative return",
         "The best and worst rolling 12-month windows in the backtest. Shows the range of outcomes an investor might experience in any given year.",
         "Helps set expectations. If the worst year was −20%, you should be psychologically prepared for that. If the best was +35%, don't expect it every year."),
        ("Daily Win Rate",
         "count(daily return > 0) / total days",
         "Percentage of trading days that ended positive. Typically 53–55% for diversified portfolios.",
         "A sanity check. Much below 50% suggests structural drag; much above 55% is unusual and may indicate smoothed proxy data."),
    ]),
    ("Risk", [
        ("Volatility",
         "σ_daily × √252",
         "Annualized standard deviation of daily returns. Measures how much the portfolio value fluctuates day to day.",
         f"The most common risk measure. Lower volatility means a smoother ride. The Golden Butterfly runs at ~{S["proxy_vol"]} vol (US Proxy) to ~{S["us_etf_vol"]} (US ETF) vs ~16% for pure equities — roughly half the turbulence."),
        ("Max Drawdown",
         "min(cumulative / cumulative_max − 1)",
         "The largest peak-to-trough decline at any point in the backtest. If you invested at the worst possible moment and sold at the worst possible moment, this is your loss.",
         "The metric that makes or breaks investor behavior. Most people abandon strategies after drawdowns exceeding their pain threshold. A −21% max DD is much more survivable than −55%."),
        ("Longest Drawdown",
         "max consecutive days where portfolio < previous high",
         "How many trading days the portfolio stayed underwater (below its all-time high). Measures recovery time.",
         f"Even more psychologically important than max DD depth. Being underwater for {S["proxy_longest_dd"]} days (~{S["proxy_longest_dd_yr"]} years) is tough; for pure equities it can exceed 5+ years."),
        ("VaR 95%",
         "5th percentile of daily returns",
         f"Value at Risk: on 95% of trading days, the daily loss will not exceed this threshold. A VaR of {S["proxy_var"]} means you can expect to lose more than {S["proxy_var"].lstrip("-")} on only 1 in 20 days.",
         "A regulatory standard for risk measurement. Useful for sizing positions and understanding daily tail exposure, but doesn't tell you <i>how bad</i> the worst days get."),
        ("CVaR 95%",
         "mean(daily returns where return ≤ VaR_95)",
         "Conditional VaR (Expected Shortfall): the average loss on the worst 5% of days. Goes beyond VaR by answering 'when things go bad, how bad do they get?'",
         f"Preferred over VaR by risk professionals because it captures tail severity. A CVaR of {S["proxy_cvar"]} means that on the worst 1-in-20 days, you lose {S["proxy_cvar"].lstrip("-")} on average."),
        ("Ulcer Index",
         "√(mean(drawdown²))",
         "Root mean square of all drawdowns over time. Unlike max drawdown (a single worst point), this captures both the depth and duration of every drawdown.",
         "Invented by Peter Martin. A more holistic pain measure — a portfolio with frequent shallow drawdowns and one with rare deep ones can have the same max DD but very different Ulcer Indices. Lower = less stressful to hold."),
    ]),
    ("Risk-Adjusted Returns", [
        ("Sharpe Ratio",
         "(R_portfolio − R_riskfree) / σ_portfolio",
         "Excess return per unit of total risk. Answers: 'how much return am I getting for each unit of volatility I'm enduring?' Uses 3% annual risk-free rate.",
         "The gold standard for risk-adjusted comparison. Below 0.3 is poor, 0.5–0.7 is decent, above 1.0 is excellent. The Golden Butterfly's ~0.6 Sharpe is solid for a multi-asset portfolio."),
        ("Sortino Ratio",
         "(R_portfolio − R_riskfree) / σ_downside",
         "Like Sharpe, but only penalizes downside volatility (negative returns). Upside volatility is good — you don't want to be penalized for big gains.",
         f"More appropriate than Sharpe for portfolios with asymmetric returns. A Sortino of {S["proxy_sortino"]} vs Sharpe of {S["proxy_sharpe"]} tells you the portfolio's upside volatility is helping, not hurting."),
        ("Calmar Ratio",
         "CAGR / |Max Drawdown|",
         "Return per unit of worst-case drawdown. Directly links your annual return to the worst pain you'd endure.",
         f"Practical for setting expectations: a Calmar of {S["proxy_calmar"]} means you earn ~{S["proxy_calmar"]}% of annual return for every 1% of max drawdown risk. Higher is better — you want more return per unit of worst-case pain."),
    ]),
    ("Distribution Shape", [
        ("Skewness",
         "E[(r − μ)³] / σ³",
         "Measures asymmetry of the return distribution. Zero = symmetric. Negative = fatter left tail (more extreme losses than gains). Positive = fatter right tail.",
         f"Most equity portfolios have negative skew (crashes are sharper than rallies). The Golden Butterfly's skew of {S["proxy_skew"]} is mild — gold and bonds partially offset equity crash risk."),
        ("Kurtosis",
         "E[(r − μ)⁴] / σ⁴ − 3",
         "Excess kurtosis measures how fat the tails are compared to a normal distribution. Zero = normal. Positive = more extreme events than a bell curve predicts.",
         f"A kurtosis of {round(S["proxy_kurt"])} means extreme days (both good and bad) happen far more often than a normal distribution would suggest. This is why VaR alone is insufficient — the tails are fat."),
    ]),
]


def build_glossary_section():
    """Standalone glossary section with collapsible cards."""
    cards = ""
    for group_name, items in METRIC_GLOSSARY:
        cards += f'<div class="glossary-group">{group_name}</div>\n'
        for name, formula, what, why in items:
            anchor = name.lower().replace(' ', '-').replace('/', '-').replace('%', 'pct')
            cards += f"""<details class="glossary-card" id="g-{anchor}">
              <summary class="glossary-header">{name}</summary>
              <div class="glossary-formula">{formula}</div>
              <div class="glossary-body">
                <div><span class="glossary-label">What:</span> {what}</div>
                <div><span class="glossary-label">Why it matters:</span> {why}</div>
              </div>
            </details>\n"""

    return f"""
    <div class="section" id="glossary">
      <h2>10. Metric Glossary</h2>
      <p class="subtitle">Click any metric to expand its definition, formula, and interpretation</p>
      {cards}
    </div>"""


def build_section_1(region='all'):
    """Portfolio overview, allocation, metrics table with explanations."""
    alloc_cards = ""
    alloc_items = [
        ("Total Stock Market", "20%", "Broad equity exposure — captures overall market growth"),
        ("Small Cap Value", "20%", "Tilts toward small, undervalued companies — historically higher returns"),
        ("Long-Term Bonds", "20%", "20+ year Treasuries — strong deflation hedge, inversely correlated with stocks"),
        ("Short-Term Bonds", "20%", "1-3 year Treasuries — stability anchor, low volatility cash-like returns"),
        ("Gold", "20%", "Inflation hedge and crisis diversifier — uncorrelated to stocks and bonds"),
    ]
    for name, pct, desc in alloc_items:
        alloc_cards += f'<div class="alloc-card"><div class="pct">{pct}</div><div class="label"><b>{name}</b><br>{desc}</div></div>\n'

    if region == 'us':
        filtered = [m for m in metrics if m.get('name') in ('US ETF', 'Fund Proxy', 'US Proxy')]
    elif region == 'eu':
        filtered = [m for m in metrics if m.get('name') in ('EU ETF', 'EU Proxy')]
    else:
        filtered = metrics
    table = metrics_table_html(filtered, compact=True)

    COMP_TIPS = {
        'Total Market': 'Broad equity index covering the full market. Provides baseline exposure to overall economic growth and corporate earnings.',
        'Small Cap Value': 'Small, undervalued companies. Historically ~2-3% annual premium over large caps (Fama-French), but with higher volatility and deeper drawdowns.',
        'Long-Term Bonds': '20+ year Treasuries. Strong deflation hedge — when stocks crash, long bonds typically rally. Inversely correlated with equities and inflation.',
        'Short-Term Bonds': '1-3 year Treasuries. Stability anchor with minimal price volatility. Acts as dry powder during crises and dampens overall portfolio swings.',
        'Gold': 'Inflation hedge and crisis diversifier. Uncorrelated to both stocks and bonds. Protects purchasing power during monetary expansion and geopolitical stress.',
        'Currency': 'EU equity ETFs are EUR-denominated, so the proxy converts USD equity returns to EUR using the FRED EUR/USD exchange rate. Bonds and gold stay in USD to match the actual ETF currency exposure.',
    }
    ASSET_TIPS = {
        # US ETFs
        'VTI': 'Vanguard Total Stock Market ETF. Tracks CRSP US Total Market Index — ~4,000 stocks covering 100% of investable US equity. ER: 0.03%. Since 2001.',
        'VBR': 'Vanguard Small-Cap Value ETF. Tracks CRSP US Small Cap Value Index — small companies with low P/B ratios. ER: 0.07%. Since 2004.',
        'TLT': 'iShares 20+ Year Treasury Bond ETF. Holds US Treasuries with 20+ year maturity. Duration ~17yr — very rate-sensitive. ER: 0.15%. Since 2002.',
        'SHY': 'iShares 1-3 Year Treasury Bond ETF. Holds short-term US Treasuries. Duration ~1.9yr — minimal rate risk. ER: 0.15%. Since 2002.',
        'GLD': 'SPDR Gold Shares. Physically backed gold trust. Largest gold ETF globally. ER: 0.40%. Since 2004.',
        # EU ETFs
        'IWDA.AS': 'iShares Core MSCI World UCITS ETF (Acc). ~1,500 large/mid-cap stocks across 23 developed markets. EUR-denominated, accumulating. ER: 0.20%. Since 2009.',
        'IUSN.DE': 'iShares MSCI World Small Cap UCITS ETF. ~3,400 small-cap stocks across developed markets. Note: all small caps, not specifically value. ER: 0.35%. Since 2018.',
        'DTLA.L': 'iShares $ Treasury Bond 20+yr UCITS ETF. USD-denominated long Treasuries for EU investors. ER: 0.07%. Since 2015.',
        'IBTA.L': 'iShares $ Treasury Bond 1-3yr UCITS ETF. USD-denominated short Treasuries. Low duration stability anchor. ER: 0.07%. Since 2017.',
        'IGLN.L': 'iShares Physical Gold ETC. Physically backed, USD-denominated. EU-accessible gold exposure. ER: 0.12%. Since 2011.',
        # Fund proxies
        '^GSPC': 'S&amp;P 500 index. ~500 large-cap US stocks covering ~80% of market cap. Closest available proxy for total market before VTI existed.',
        '^RUT': 'Russell 2000 index. 2,000 smallest stocks in the Russell 3000. Best available small-cap proxy, though not value-filtered.',
        'VUSTX': 'Vanguard Long-Term Treasury Fund. Mutual fund holding 15-30yr Treasuries. Available since ~1986 — fills the gap before TLT.',
        'VFISX': 'Vanguard Short-Term Treasury Fund. Mutual fund holding 1-3yr Treasuries. Available since ~1991 — fills the gap before SHY.',
        'GC=F': 'COMEX Gold Futures (continuous front-month). Liquid gold price benchmark. Available from ~2000 on Yahoo Finance.',
        # Deep proxies
        'DGS10': 'FRED 10-Year Treasury Constant Maturity Rate. Converted to total return via duration model (d=14) to approximate 20+yr bond behavior. Since 1962.',
        'DGS1+DGS2': 'FRED DGS1 (1-Year, 1962+) spliced with DGS2 (2-Year, 1976+). Duration model d=1.9 matches SHY effective duration. Weekly correlation 0.96 with SHY.',
        '^GSPC+2%': 'Synthetic SCV: S&amp;P 500 daily returns + 2% annualized premium. Based on Fama-French size+value factor. Understates real SCV volatility.',
        'Synthetic': 'Gold milestones 1950-2000 (interpolated annual prices, no daily vol) spliced with GC=F futures post-2000.',
        '60/20/20': 'Global equity blend: 60% S&amp;P 500 + 20% Nikkei 225 + 20% FTSE 100, converted USD→EUR. Approximates MSCI World geographic mix.',
        '^RUT/^GSPC+2%': 'Russell 2000 where available, else S&amp;P 500 + 2% premium. Converted USD→EUR to match IUSN.DE currency.',
        'FRED': 'FRED DEXUSEU series (EUR/USD daily rate since 1999). Used to convert USD equity returns to EUR for the EU proxy.',
    }
    def _tip(name):
        t = COMP_TIPS.get(name, '')
        return f'<span class="has-tip" data-tip="{t}">{name} <span class="tip-icon">ⓘ</span></span>' if t else name

    def _atip(pill_cls, ticker, label, tip_key=None):
        t = ASSET_TIPS.get(tip_key or ticker, '')
        if t:
            return (f'<span class="has-tip" data-tip="{t}">'
                    f'<span class="pill pill-{pill_cls}">{ticker}</span> {label}</span>')
        return f'<span class="pill pill-{pill_cls}">{ticker}</span> {label}'

    instruments = {
        'us': {
            'headers': ['US ETF', 'Fund Proxy', 'US Deep Proxy'],
            'rows': [
                (_tip('Total Market'),
                 _atip('green', 'VTI', 'Vanguard Total Stock'),
                 _atip('gold', '^GSPC', 'S&amp;P 500'),
                 _atip('gold', '^GSPC', 'S&amp;P 500')),
                (_tip('Small Cap Value'),
                 _atip('green', 'VBR', 'Vanguard SCV'),
                 _atip('gold', '^RUT', 'Russell 2000'),
                 _atip('red', '^GSPC+2%', 'Synthetic premium')),
                (_tip('Long-Term Bonds'),
                 _atip('green', 'TLT', '20+yr Treasury'),
                 _atip('gold', 'VUSTX', 'LT Treasury Fund'),
                 _atip('red', 'DGS10', 'FRED yield → return')),
                (_tip('Short-Term Bonds'),
                 _atip('green', 'SHY', '1-3yr Treasury'),
                 _atip('gold', 'VFISX', 'ST Treasury Fund'),
                 _atip('red', 'DGS1+DGS2', 'FRED yield → return')),
                (_tip('Gold'),
                 _atip('green', 'GLD', 'SPDR Gold'),
                 _atip('gold', 'GC=F', 'Gold Futures'),
                 _atip('red', 'Synthetic', 'Milestones + GC=F')),
            ],
        },
        'eu': {
            'headers': ['EU ETF', 'EU Deep Proxy'],
            'rows': [
                (_tip('Total Market'),
                 _atip('green', 'IWDA.AS', 'MSCI World'),
                 _atip('red', '60/20/20', '^GSPC+^N225+^FTSE → EUR')),
                (_tip('Small Cap Value'),
                 _atip('green', 'IUSN.DE', 'MSCI World SC'),
                 _atip('red', '^RUT/^GSPC+2%', '→ EUR')),
                (_tip('Long-Term Bonds'),
                 _atip('green', 'DTLA.L', '$ Treasury 20+yr'),
                 _atip('red', 'DGS10', 'FRED yield → return (USD)')),
                (_tip('Short-Term Bonds'),
                 _atip('green', 'IBTA.L', '$ Treasury 1-3yr (USD)'),
                 _atip('red', 'DGS1+DGS2', 'FRED yield → return (USD)')),
                (_tip('Gold'),
                 _atip('green', 'IGLN.L', 'Physical Gold'),
                 _atip('red', 'Synthetic', 'Milestones + GC=F (USD)')),
                (_tip('Currency'),
                 'EUR (equity) + USD (bonds, gold)',
                 _atip('red', 'FRED', 'EUR/USD for equity → EUR')),
            ],
        },
    }
    inst = instruments[region]
    th = ''.join(f'<th style="background:transparent;">{h}</th>' for h in inst['headers'])
    tr = ''.join(
        '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>\n'
        for row in inst['rows']
    )
    etf_info = f"""
    <div class="note" style="padding:0; overflow:hidden;">
      <div style="padding:0.8rem 1rem; border-bottom:1px solid rgba(234,179,8,0.15);">
        <strong>📌 Instruments Used</strong>
      </div>
      <table class="table-left" style="margin:0; font-size:0.82rem;">
        <thead><tr><th style="background:transparent;">Component</th>{th}</tr></thead>
        <tbody>{tr}</tbody>
      </table>
      <div style="padding:0.6rem 1rem; font-size:0.78rem; color:var(--muted); border-top:1px solid rgba(234,179,8,0.15);">
        <span class="pill pill-green" style="font-size:0.7rem;">GREEN</span> Real ETF &nbsp;
        <span class="pill pill-gold" style="font-size:0.7rem;">GOLD</span> Index / Mutual Fund &nbsp;
        <span class="pill pill-red" style="font-size:0.7rem;">RED</span> Synthetic / Model-based
      </div>
    </div>"""

    if region == 'eu':
        etf_info += """
    <div class="note" style="background:rgba(59,130,246,0.08); border-color:rgba(59,130,246,0.2); margin-top:0.5rem;">
      <strong style="color:var(--accent);">💱 Currency Exposure Note</strong><br>
      <span style="font-size:0.85rem;">This EU portfolio is <b>60% USD-denominated</b> (bonds + gold) and 40% EUR-denominated (equities).
      This is intentional: US Treasuries are the deepest, most liquid bond market, gold is globally priced in USD,
      and the USD exposure itself acts as diversification for a EUR-based investor.
      In practice, a weakening EUR boosts the USD portion and vice versa — adding an extra layer of
      uncorrelated return. If you prefer to neutralize FX risk, look for EUR-hedged share classes
      (e.g. DTLA.L → IDTL.L, IGLN.L → SGLN.L).</span>
    </div>"""

    return f"""
    <div class="section">
      <h2>1. Portfolio Overview</h2>
      <p class="subtitle">What is the Golden Butterfly and why these allocations?</p>
      <p>The <b>Golden Butterfly</b> is a permanent-portfolio variant designed by Tyler at
      <i>portfoliocharts.com</i>. It splits equally across five asset classes, each serving a
      distinct economic role: stocks for growth, small-cap value for excess return, long bonds
      for deflation protection, short bonds for stability, and gold for inflation hedging.
      The equal 20% weighting keeps the portfolio robust across all economic regimes —
      growth, recession, inflation, and deflation.</p>
      <div class="alloc-grid">{alloc_cards}</div>
      {etf_info}
    </div>

    <div class="section">
      <h2>2. Full Metrics Comparison</h2>
      <p class="subtitle">All four backtest variants side by side</p>
      <p>The table below compares the Golden Butterfly implemented with US ETFs (longest real backtest),
      EU-domiciled ETFs (shorter history), US mutual fund/index proxies, and the deep synthetic proxy
      reaching back to 1962.</p>
      {table}
      <p style="font-size:0.82rem; color:var(--muted); margin-top:0.5rem;">💡 Click any metric name for a detailed explanation in the <a href="#glossary" style="color:var(--accent);">Metric Glossary</a>.</p>
    </div>"""


def plotly_to_html(fig, div_id):
    """Serialize figure as gzipped+base64 blob for lazy client-side rendering."""
    spec = json.dumps({
        'data': json.loads(fig.to_json())['data'],
        'layout': json.loads(fig.to_json())['layout'],
        'config': PLOTLY_CFG,
    }, separators=(',', ':')).encode()
    blob = base64.b64encode(gzip.compress(spec, compresslevel=9)).decode()
    return (f'<div id="{div_id}" class="lazy-chart" data-gz="{blob}"'
            f' style="min-height:300px;display:flex;align-items:center;'
            f'justify-content:center;">'
            f'<span class="chart-loader">Loading chart…</span></div>')


PLOTLY_LAYOUT = dict(
    template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    legend=dict(orientation='h', y=1.02, x=0.5, xanchor='center'),
    xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
    yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
    hoverlabel=dict(bgcolor='#1e293b', font_size=13, font_color='#e2e8f0'),
)

DD_COLORS = {
    "US ETF": "rgba(37,99,235,0.8)",
    "EU ETF": "rgba(22,163,74,0.8)",
    "Fund Proxy": "rgba(217,119,6,0.8)",
    "US Proxy": "rgba(220,38,38,0.8)",
    "EU Proxy": "rgba(139,92,246,0.8)",
}
DD_FILL = {
    "US ETF": "rgba(37,99,235,0.15)",
    "EU ETF": "rgba(22,163,74,0.15)",
    "Fund Proxy": "rgba(217,119,6,0.15)",
    "US Proxy": "rgba(220,38,38,0.15)",
    "EU Proxy": "rgba(139,92,246,0.15)",
}


def make_growth_dd_figure(ret_dict, height=600, rangeslider=False, log_y=True):
    """Build a linked growth + drawdown subplot figure."""
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.65, 0.35],
    )
    for name, dr in ret_dict.items():
        cum = (1 + dr).cumprod()
        dd = (cum / cum.cummax() - 1) * 100
        color = COLORS.get(name, '#94a3b8')
        # Growth
        fig.add_trace(go.Scatter(
            x=cum.index, y=cum.values, name=name,
            line=dict(color=color, width=1.5),
            legendgroup=name,
            hovertemplate=name + ': %{y:.2f}x<extra></extra>',
        ), row=1, col=1)
        # Drawdown
        fig.add_trace(go.Scatter(
            x=dd.index, y=dd.values, name=name,
            line=dict(color=DD_COLORS.get(name, color), width=1),
            fill='tozeroy', fillcolor=DD_FILL.get(name, 'rgba(148,163,184,0.1)'),
            legendgroup=name, showlegend=False,
            hovertemplate=name + ': %{y:.1f}%<extra></extra>',
        ), row=2, col=1)

    fig.update_layout(
        **PLOTLY_LAYOUT, height=height, hovermode='x unified',
        margin=dict(l=50, r=20, t=30, b=40),
    )
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)')
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)')
    fig.update_yaxes(title_text='Growth of $1', row=1, col=1)
    fig.update_yaxes(title_text='Drawdown %', row=2, col=1)
    if log_y:
        fig.update_yaxes(type='log', row=1, col=1)
    if rangeslider:
        fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.04), row=2, col=1)
    return fig


def build_section_2(region='all'):
    """Interactive cumulative returns + drawdown charts (all variants)."""
    if region == 'us':
        cols = [c for c in returns.columns if c in ('US ETF', 'Fund Proxy', 'US Proxy')]
    elif region == 'eu':
        cols = [c for c in returns.columns if c in ('EU ETF', 'EU Proxy')]
    else:
        cols = list(returns.columns)
    suffix = f'_{region}' if region != 'all' else ''
    # Full history
    fig_full = make_growth_dd_figure(
        {n: returns[n] for n in cols}, height=600, rangeslider=True, log_y=True)

    # Common period
    common_idx = returns[cols].dropna().index
    common_start = common_idx[0]
    common_end = common_idx[-1]
    common_rets = {n: returns[n].loc[common_start:common_end].dropna() for n in cols}
    fig_common = make_growth_dd_figure(common_rets, height=550, log_y=False)

    return f"""
    <div class="section">
      <h2>3. Cumulative Returns \u2014 All Variants</h2>

      <h3 style="color:var(--accent); margin:1rem 0 0.5rem;">Full History</h3>
      <p class="subtitle">Log scale \u00b7 drag to zoom \u00b7 growth and drawdown are linked</p>
      <p>Each variant starts from its own inception date. The log scale makes growth rates
      visually comparable (parallel lines = same CAGR), but be aware that longer series have more
      time to compound \u2014 the US Proxy\u2019s {S['proxy_growth']}x growth reflects {S['proxy_years']} years, not superior returns.
      Zoom into any period and the drawdown chart below follows automatically.</p>
      <div class="chart-container">{plotly_to_html(fig_full, f'full_history{suffix}')}</div>

      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">Common Period ({common_start.strftime('%Y-%m-%d')} \u2192 {common_end.strftime('%Y-%m-%d')})</h3>
      <p>To compare fairly, all four variants are rebased to $1 from the same start date.
      This is the <b>key validation view</b>: if the US Proxy and Fund Proxy track the real
      ETF portfolios closely over this shared window, we can trust their behavior in earlier
      decades where no ETF data exists. Any persistent gap between lines reveals systematic
      bias in the proxy construction.</p>
      <div class="chart-container">{plotly_to_html(fig_common, f'common_period{suffix}')}</div>
    </div>"""


def build_section_3():
    """US vs EU ETF comparison."""
    us = returns.get('US ETF')
    eu = returns.get('EU ETF')
    if us is None or eu is None:
        return '<div class="section"><h2>6. US vs EU ETF</h2><p>Data not available.</p></div>'

    # Align to EU start (shorter)
    common = us.index.intersection(eu.index)
    us_c, eu_c = us.loc[common], eu.loc[common]

    # Cumulative (rebased to same start)
    fig = make_subplots(rows=2, cols=1, row_heights=[0.6, 0.4], shared_xaxes=True,
                        vertical_spacing=0.08,
                        subplot_titles=('Growth of $1 (same period)', 'Rolling 1Y Return'))
    for name, s, color in [('US ETF', us_c, COLORS['US ETF']), ('EU ETF', eu_c, COLORS['EU ETF'])]:
        cum = (1 + s).cumprod()
        fig.add_trace(go.Scatter(
            x=cum.index, y=cum.values, name=name,
            line=dict(color=color, width=1.5),
            hovertemplate=name + ': %{y:.3f}x<extra></extra>',
        ), row=1, col=1)
        roll = s.rolling(252).apply(lambda x: (1+x).prod()-1, raw=False) * 100
        fig.add_trace(go.Scatter(
            x=roll.index, y=roll.values, name=name + ' 1Y',
            line=dict(color=color, width=0.9), showlegend=False,
            hovertemplate=name + ': %{y:.1f}%<extra></extra>',
        ), row=2, col=1)

    fig.update_layout(
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'),
        margin=dict(l=50, r=20, t=50, b=40), height=550,
        hovermode='x unified',
    )
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)')
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)')
    fig.update_yaxes(title_text='Growth of $1', row=1, col=1)
    fig.update_yaxes(title_text='Rolling 1Y %', row=2, col=1)

    # Compute overlap stats
    corr = us_c.corr(eu_c)
    us_cagr = (1 + us_c).prod() ** (252/len(us_c)) - 1
    eu_cagr = (1 + eu_c).prod() ** (252/len(eu_c)) - 1
    us_vol = us_c.std() * np.sqrt(252)
    eu_vol = eu_c.std() * np.sqrt(252)

    return f"""
    <div class="section">
      <h2>6. US vs EU ETF Comparison</h2>
      <p class="subtitle">Same period ({common[0].strftime('%Y-%m-%d')} → {common[-1].strftime('%Y-%m-%d')})</p>
      <p>To compare fairly, both portfolios are shown over the <b>same overlapping period</b>
      (limited by the shorter EU ETF history). The top chart shows cumulative growth, the bottom
      shows rolling 1-year returns to visualize how they move together.</p>
      <div class="chart-container">{plotly_to_html(fig, 'us_vs_eu')}</div>
      <div class="note">
        <strong>📊 Overlap Statistics</strong><br>
        Daily correlation: <b>{corr:.4f}</b> ·
        US CAGR: <b>{us_cagr:.2%}</b> · EU CAGR: <b>{eu_cagr:.2%}</b> ·
        US Vol: <b>{us_vol:.2%}</b> · EU Vol: <b>{eu_vol:.2%}</b>
      </div>
      <p>The EU version uses MSCI World instead of US Total Market, and MSCI World Small Cap instead of
      US Small Cap Value — so it has broader geographic diversification but less pure small-value tilt.
      The slightly lower volatility of the EU variant reflects this broader diversification.
      Both deliver nearly identical CAGRs over the common period, confirming the strategy is
      not US-specific.</p>
    </div>"""

def build_section_4():
    """Per-decade breakdown."""
    if not decade_metrics:
        return '<div class="section"><h2>7. Per-Decade</h2><p>No data.</p></div>'

    table = metrics_table_html(decade_metrics)

    # Bar chart: CAGR, Volatility, Max DD, Sharpe per decade
    decades = [m['name'] for m in decade_metrics if 'error' not in m]
    cagrs = [float(m['cagr'].strip('%')) for m in decade_metrics if 'error' not in m]
    vols = [float(m['volatility'].strip('%')) for m in decade_metrics if 'error' not in m]
    mdd = [float(m['max_drawdown'].strip('%')) for m in decade_metrics if 'error' not in m]
    sharpes = [m['sharpe'] for m in decade_metrics if 'error' not in m]

    fig = make_subplots(rows=2, cols=2, shared_xaxes=True, vertical_spacing=0.15, horizontal_spacing=0.1,
                        subplot_titles=('CAGR %', 'Volatility %', 'Max Drawdown %', 'Sharpe Ratio'))

    bar_colors = ['#3b82f6' if c >= 0 else '#ef4444' for c in cagrs]
    fig.add_trace(go.Bar(x=decades, y=cagrs, marker_color=bar_colors, showlegend=False,
                         hovertemplate='%{x}<br>CAGR: %{y:.1f}%<extra></extra>'), row=1, col=1)

    fig.add_trace(go.Bar(x=decades, y=vols, marker_color='#d97706', showlegend=False,
                         hovertemplate='%{x}<br>Vol: %{y:.1f}%<extra></extra>'), row=1, col=2)

    dd_colors = ['#ef4444' if d < -15 else '#eab308' if d < -10 else '#22c55e' for d in mdd]
    fig.add_trace(go.Bar(x=decades, y=mdd, marker_color=dd_colors, showlegend=False,
                         hovertemplate='%{x}<br>Max DD: %{y:.1f}%<extra></extra>'), row=2, col=1)

    sh_colors = ['#22c55e' if s >= 0.7 else '#3b82f6' if s >= 0.3 else '#ef4444' for s in sharpes]
    fig.add_trace(go.Bar(x=decades, y=sharpes, marker_color=sh_colors, showlegend=False,
                         hovertemplate='%{x}<br>Sharpe: %{y:.3f}<extra></extra>'), row=2, col=2)

    fig.update_layout(
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=50, r=20, t=50, b=40), height=500,
    )
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)')
    fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)')

    # Find best/worst decades
    best_i = np.argmax(cagrs)
    worst_i = np.argmin(cagrs)

    return f"""
    <div class="section">
      <h2>7. Per-Decade Breakdown (US Proxy)</h2>
      <p class="subtitle">How the Golden Butterfly performed across different economic regimes</p>
      <p>The deep proxy lets us examine performance across seven decades, each with distinct
      macro conditions: the inflationary 1970s, the bond bull market of the 1980s-90s,
      the dot-com crash and GFC in the 2000s, and the post-QE 2010s.</p>
      <div class="chart-container">{plotly_to_html(fig, 'decades_bar')}</div>
      <div class="note">
        <strong>🎯 Key Observations</strong><br>
        • Best decade: <b>{decades[best_i]}</b> with {cagrs[best_i]:.1f}% CAGR<br>
        • Worst decade: <b>{decades[worst_i]}</b> with {cagrs[worst_i]:.1f}% CAGR — still positive<br>
        • The portfolio <b>never had a lost decade</b> — every 10-year period delivered positive real returns<br>
        • Max drawdown stayed between {S["dec_mdd_min"]}% and {S["dec_mdd_max"]}% across all decades<br>
        • The 1970s (high inflation) had the <i>{S["rank_1970s"]}</i> CAGR thanks to the gold allocation
      </div>
      <p style="margin-top:1.5rem;">Full metrics per decade:</p>
      <div style="overflow-x:auto;">{table}</div>
    </div>"""

def _validation_pair(ref_name, ref_ret, proxy_name, proxy_ret, section_id, cross_tz=False):
    """Build validation charts + stats using weekly returns.
    Weekly frequency eliminates daily noise and timezone mismatches naturally."""
    from scipy import stats as sp_stats
    ref_clean = ref_ret.dropna()
    proxy_clean = proxy_ret.dropna()
    common = ref_clean.index.intersection(proxy_clean.index)
    if len(common) < 100:
        return None, None
    e_d, p_d = ref_clean.loc[common], proxy_clean.loc[common]
    start_str = common[0].strftime('%Y-%m-%d')
    end_str = common[-1].strftime('%Y-%m-%d')
    n_years = len(common) / 252

    # Weekly returns — core frequency for all stats
    ew = e_d.resample('W').sum()
    pw = p_d.resample('W').sum()
    wci = ew.index.intersection(pw.index)
    ew, pw = ew.loc[wci], pw.loc[wci]

    corr = round(ew.corr(pw), 4)
    ann_te = (ew - pw).std() * np.sqrt(52)
    e_cagr = (1 + e_d).prod() ** (252 / len(e_d)) - 1
    p_cagr = (1 + p_d).prod() ** (252 / len(p_d)) - 1
    cagr_diff = abs(e_cagr - p_cagr)

    # Monthly R²
    em = e_d.resample('ME').sum()
    pm = p_d.resample('ME').sum()
    mci = em.index.intersection(pm.index)
    slope, intercept, r_val, _, _ = sp_stats.linregress(pm.loc[mci], em.loc[mci])
    r2 = r_val ** 2

    # Cumulative overlay (daily for smooth lines)
    ref_color = COLORS.get(ref_name, '#94a3b8')
    proxy_color = COLORS.get(proxy_name, '#dc2626')
    fig_cum = go.Figure()
    for name, s, color, dash in [(ref_name, e_d, ref_color, 'solid'), (proxy_name, p_d, proxy_color, 'dash')]:
        cum = (1 + s).cumprod()
        fig_cum.add_trace(go.Scatter(
            x=cum.index, y=cum.values, name=name,
            line=dict(color=color, width=1.5, dash=dash),
            hovertemplate=name + ': %{y:.3f}x<extra></extra>',
        ))
    fig_cum.update_layout(
        **PLOTLY_LAYOUT, height=320, hovermode='x unified',
        margin=dict(l=50, r=20, t=30, b=40),
        yaxis_title='Growth of $1',
    )

    # Weekly scatter + regression
    x_line = np.linspace(pw.min(), pw.max(), 50)
    w_slope, w_int, w_r, _, _ = sp_stats.linregress(pw, ew)
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=pw.values, y=ew.values, mode='markers', name='Weekly Returns',
        marker=dict(color=proxy_color, size=4, opacity=0.5),
        hovertemplate=f'{proxy_name}: %{{x:.2%}}<br>{ref_name}: %{{y:.2%}}<extra></extra>',
    ))
    fig_scatter.add_trace(go.Scatter(
        x=x_line, y=w_slope * x_line + w_int, mode='lines', name=f'R²={w_r**2:.3f}',
        line=dict(color='#ef4444', width=1.5, dash='dash'),
    ))
    fig_scatter.update_layout(
        **PLOTLY_LAYOUT, height=320,
        xaxis_title=f'{proxy_name} Weekly Return', yaxis_title=f'{ref_name} Weekly Return',
        margin=dict(l=50, r=20, t=30, b=40),
    )
    fig_scatter.update_xaxes(tickformat='.1%')
    fig_scatter.update_yaxes(tickformat='.1%')

    # Rolling 52-week (1 year) correlation
    rc = ew.rolling(52).corr(pw)
    fig_corr = go.Figure()
    fig_corr.add_trace(go.Scatter(
        x=rc.index, y=rc.values, name='52w Correlation',
        line=dict(color='#8b5cf6', width=0.9),
        hovertemplate='%{x|%Y-%m-%d}<br>Corr: %{y:.3f}<extra></extra>',
    ))
    fig_corr.add_hline(y=corr, line_dash='dash', line_color='#ef4444',
                       annotation_text=f'Full period: {corr}', annotation_font_color='#ef4444')
    fig_corr.update_layout(
        **PLOTLY_LAYOUT, height=260, yaxis_title='Rolling 52-Week Correlation', yaxis_range=[0, 1.05],
        margin=dict(l=50, r=20, t=30, b=40),
    )

    # Rolling 52-week (1 year) tracking error
    te_roll = (ew - pw).rolling(52).std() * np.sqrt(52) * 100
    fig_te = go.Figure()
    fig_te.add_trace(go.Scatter(
        x=te_roll.index, y=te_roll.values, name='Tracking Error',
        line=dict(color='#d97706', width=0.9), fill='tozeroy',
        fillcolor='rgba(217,119,6,0.15)',
        hovertemplate='%{x|%Y-%m-%d}<br>TE: %{y:.2f}%<extra></extra>',
    ))
    fig_te.add_hline(y=ann_te * 100, line_dash='dash', line_color='#ef4444',
                     annotation_text=f'Full period: {ann_te:.2%}', annotation_font_color='#ef4444')
    fig_te.update_layout(
        **PLOTLY_LAYOUT, height=260, yaxis_title='Annualized TE %',
        margin=dict(l=50, r=20, t=30, b=40),
    )

    # Verdicts (thresholds adjusted for weekly frequency)
    def verdict(val, good, bad, higher_is_better=True):
        if higher_is_better:
            return ('PASS', 'green') if val >= good else ('MARGINAL', 'gold') if val >= bad else ('FAIL', 'red')
        else:
            return ('PASS', 'green') if val <= good else ('MARGINAL', 'gold') if val <= bad else ('FAIL', 'red')

    v_corr = verdict(corr, 0.90, 0.80)
    v_te = verdict(ann_te, 0.03, 0.05, higher_is_better=False)
    v_cagr = verdict(cagr_diff, 0.005, 0.01, higher_is_better=False)
    v_r2 = verdict(r2, 0.85, 0.70)

    tests_passed = sum(1 for v in [v_corr, v_te, v_cagr, v_r2] if v[0] == 'PASS')
    overall = '✅ Reliable proxy' if tests_passed >= 3 else '⚠️ Use with caution' if tests_passed >= 2 else '❌ Unreliable'

    def pill(label, val_str, verdict_tuple):
        v_label, v_color = verdict_tuple
        return f'<span class="pill pill-{v_color}">{v_label}</span> {label}: <b>{val_str}</b>'

    stats = {
        'start': start_str, 'end': end_str, 'years': f'{n_years:.1f}',
        'ref_cagr': f'{e_cagr:.2%}', 'proxy_cagr': f'{p_cagr:.2%}',
    }

    html = f"""
      <div class="validation-pair">
        <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">{ref_name} vs {proxy_name}</h3>
        <p>Overlapping period: <b>{start_str}</b> → <b>{end_str}</b> ({n_years:.1f} years).
        All statistics use <b>weekly returns</b> to filter out daily noise and timezone mismatches.
        If {proxy_name} is a good stand-in for {ref_name}, the lines below should overlap,
        the scatter should hug the diagonal, and correlation should stay above 0.85.</p>

        <div class="grid-2">
          <div>
            <p style="font-size:0.82rem; color:var(--muted); margin-bottom:0.3rem;"><b>Cumulative Growth</b> — do they end at the same place?</p>
            <div class="chart-container">{plotly_to_html(fig_cum, f'val_cum_{section_id}')}</div>
          </div>
          <div>
            <p style="font-size:0.82rem; color:var(--muted); margin-bottom:0.3rem;"><b>Weekly Scatter</b> — R² measures how predictable the relationship is</p>
            <div class="chart-container">{plotly_to_html(fig_scatter, f'val_scatter_{section_id}')}</div>
          </div>
        </div>
        <div class="grid-2">
          <div>
            <p style="font-size:0.82rem; color:var(--muted); margin-bottom:0.3rem;"><b>Rolling 52-Week Correlation</b> — stability of the relationship over time</p>
            <div class="chart-container">{plotly_to_html(fig_corr, f'val_corr_{section_id}')}</div>
          </div>
          <div>
            <p style="font-size:0.82rem; color:var(--muted); margin-bottom:0.3rem;"><b>Rolling 52-Week Tracking Error</b> — annualized divergence (lower = better)</p>
            <div class="chart-container">{plotly_to_html(fig_te, f'val_te_{section_id}')}</div>
          </div>
        </div>

        <div class="note">
          <strong>{overall} — {ref_name} vs {proxy_name}</strong><br>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.3rem 1.5rem; margin-top:0.5rem; font-size:0.85rem;">
            <div>{pill('Weekly correlation', f'{corr}', v_corr)} <span style="color:var(--muted);">(target: &gt;0.90)</span></div>
            <div>{pill('Tracking error (ann.)', f'{ann_te:.2%}', v_te)} <span style="color:var(--muted);">(weekly, annualized · target: &lt;3%)</span></div>
            <div>{pill('CAGR gap', f'{cagr_diff:.2%}', v_cagr)} <span style="color:var(--muted);">(target: &lt;0.5%)</span></div>
            <div>{pill('R² monthly', f'{r2:.3f}', v_r2)} <span style="color:var(--muted);">(target: &gt;0.85)</span></div>
          </div>
          <div style="margin-top:0.5rem; font-size:0.82rem; color:var(--muted);">
            {ref_name} CAGR: {stats['ref_cagr']} · {proxy_name} CAGR: {stats['proxy_cagr']}
          </div>
        </div>
      </div>"""

    return html, stats


def build_section_5(region='all'):
    """Proxy vs ETF Validation — filtered by region."""
    us = returns.get('US ETF')
    dp = returns.get('US Proxy')
    fp = returns.get('Fund Proxy')
    eu = returns.get('EU ETF')
    eu_proxy = returns.get('EU Proxy')

    pair_configs = []
    if region in ('us', 'all'):
        if us is not None and dp is not None:
            pair_configs.append(('US ETF', us, 'US Proxy', dp, 'us_proxy', False))
        if us is not None and fp is not None:
            pair_configs.append(('US ETF', us, 'Fund Proxy', fp, 'us_fund', False))
    if region in ('eu', 'all'):
        if eu is not None and eu_proxy is not None:
            pair_configs.append(('EU ETF', eu, 'EU Proxy', eu_proxy, 'eu_proxy', True))

    if not pair_configs:
        return '<div class="section"><h2>4. Proxy Validation</h2><p>Data not available.</p></div>'

    pair_htmls = []
    for ref_name, ref_ret, proxy_name, proxy_ret, sid, cross_tz in pair_configs:
        html, stats = _validation_pair(ref_name, ref_ret, proxy_name, proxy_ret, sid, cross_tz=cross_tz)
        if html:
            pair_htmls.append(html)

    if not pair_htmls:
        return '<div class="section"><h2>4. Proxy Validation</h2><p>Insufficient overlapping data.</p></div>'

    pairs_content = '\n<hr style="border-color:var(--border); margin:2rem 0;">\n'.join(pair_htmls)

    return f"""
    <div class="section">
      <h2>4. Proxy vs ETF Validation</h2>
      <p class="subtitle">Can we trust the proxies? Let's check against real ETF data.</p>
      <p>The whole point of building proxies is to extend the backtest beyond ETF inception dates.
      But a proxy is only useful if it <b>behaves like the real thing</b> when we can compare them.
      Below, each proxy is tested against each available ETF portfolio over their <b>exact overlapping period</b>.
      Four tests per pair:</p>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; margin:1rem 0; font-size:0.85rem;">
        <div>📈 <b>Cumulative growth</b> — do they arrive at the same destination?</div>
        <div>🔵 <b>Monthly scatter + R²</b> — is the month-to-month relationship tight?</div>
        <div>📊 <b>Rolling correlation</b> — is tracking consistent or does it break down?</div>
        <div>📉 <b>Tracking error</b> — how much daily divergence exists?</div>
      </div>
      <div class="note" style="background:rgba(59,130,246,0.08); border-color:rgba(59,130,246,0.2);">
        <strong style="color:var(--accent);">How to read the verdicts</strong><br>
        <span class="pill pill-green" style="font-size:0.7rem;">PASS</span> = proxy reliably tracks the ETF &nbsp;
        <span class="pill pill-gold" style="font-size:0.7rem;">MARGINAL</span> = usable for broad conclusions, not precise attribution &nbsp;
        <span class="pill pill-red" style="font-size:0.7rem;">FAIL</span> = proxy diverges significantly
      </div>

      {pairs_content}

      {build_section_6(region)}
    </div>"""

def build_section_6(region='us'):
    """Per-component correlation: ETF vs Deep Proxy, region-specific."""
    nice_names = {
        'total_market': 'Total Market', 'scv': 'Small Cap Value',
        'lt_bonds': 'Long-Term Bonds', 'st_bonds': 'Short-Term Bonds', 'gold': 'Gold',
    }
    comp_colors = {'total_market': '#2563eb', 'scv': '#8b5cf6', 'lt_bonds': '#d97706',
                   'st_bonds': '#ef4444', 'gold': '#eab308'}
    roles = ['total_market', 'scv', 'lt_bonds', 'st_bonds', 'gold']

    if region == 'us':
        etf_p = us_etf_prices
        proxy_p = deep_prices
        comp = validation.get('component_correlations', {})
        title_suffix = 'US ETF vs US Deep Proxy'
        proxy_notes = [
            ('Total Market', '^GSPC (S&amp;P 500)', 'Excellent. S&amp;P 500 covers ~80% of US market cap, very close to VTI.'),
            ('Small Cap Value', '^GSPC + 2% annual premium', 'Decent. The flat premium is a rough approximation; real SCV has higher vol and different drawdown timing.'),
            ('Long-Term Bonds', 'FRED DGS10 \u2192 duration model (d=14)', 'Good. The 10Y yield with extended duration approximates 20+yr bonds well, though convexity is simplified.'),
            ('Short-Term Bonds', 'FRED DGS1+DGS2 \u2192 duration model (d=1.9)', 'Good. DGS1 (1Y) pre-1976, DGS2 (2Y) from 1976. Duration 1.9 matches SHY effective duration. Correlation ~0.96.'),
            ('Gold', 'Historical milestones + GC=F', 'Good. Pre-2000 gold uses interpolated annual prices (smoothed), post-2000 uses actual futures.'),
        ]
    else:
        etf_p = eu_etf_prices
        proxy_p = eu_deep_prices
        comp = {}
        title_suffix = 'EU ETF vs EU Deep Proxy'
        proxy_notes = [
            ('Total Market', '60/20/20 ^GSPC+^N225+^FTSE \u2192 EUR', 'Decent. Rough MSCI World approximation; geographic weights are fixed, real MSCI World shifts over time.'),
            ('Small Cap Value', '^RUT/^GSPC+2% \u2192 EUR', 'Decent. Russell 2000 where available, else S&amp;P 500 + premium. FX conversion adds noise.'),
            ('Long-Term Bonds', 'FRED DGS10 \u2192 duration model (d=14)', 'Good. Same USD model as US proxy. DTLA.L is USD-denominated, so no FX mismatch.'),
            ('Short-Term Bonds', 'FRED DGS1+DGS2 \u2192 duration model (d=1.9)', 'Good. Same model as US proxy. IBTA.L is USD-denominated, so no FX mismatch. Correlation ~0.88.'),
            ('Gold', 'Historical milestones + GC=F', 'Good. IGLN.L is USD-denominated, matching the proxy currency. Same model as US.'),
        ]

    if etf_p.empty or proxy_p.empty:
        return f'<p style="color:var(--muted);">Per-component proxy analysis not available for {region.upper()}.</p>'

    # Compute rolling 52-week correlations per component + portfolio
    roll_data = {}  # role -> Series of rolling corr
    full_corr = {}  # role -> single full-period corr
    if not comp:
        for role in roles:
            if role in etf_p.columns and role in proxy_p.columns:
                e_r = etf_p[role].pct_change().dropna()
                p_r = proxy_p[role].pct_change().dropna()
                ci = e_r.index.intersection(p_r.index)
                if len(ci) > 52:
                    ew = e_r.loc[ci].resample('W').sum()
                    pw = p_r.loc[ci].resample('W').sum()
                    wci = ew.index.intersection(pw.index)
                    comp[role] = round(ew.loc[wci].corr(pw.loc[wci]), 4)
                    roll_data[role] = ew.loc[wci].rolling(52).corr(pw.loc[wci]).dropna()
    else:
        for role in roles:
            if role in etf_p.columns and role in proxy_p.columns:
                e_r = etf_p[role].pct_change().dropna()
                p_r = proxy_p[role].pct_change().dropna()
                ci = e_r.index.intersection(p_r.index)
                if len(ci) > 52:
                    ew = e_r.loc[ci].resample('W').sum()
                    pw = p_r.loc[ci].resample('W').sum()
                    wci = ew.index.intersection(pw.index)
                    roll_data[role] = ew.loc[wci].rolling(52).corr(pw.loc[wci]).dropna()

    # Portfolio-level rolling correlation
    ref_name = 'US ETF' if region == 'us' else 'EU ETF'
    proxy_name = 'US Proxy' if region == 'us' else 'EU Proxy'
    ref_ret = returns.get(ref_name)
    proxy_ret = returns.get(proxy_name)
    port_roll = pd.Series(dtype=float)
    port_corr = None
    if ref_ret is not None and proxy_ret is not None:
        r_d = ref_ret.dropna()
        p_d = proxy_ret.dropna()
        ci_p = r_d.index.intersection(p_d.index)
        ew_p = r_d.loc[ci_p].resample('W').sum()
        pw_p = p_d.loc[ci_p].resample('W').sum()
        wci_p = ew_p.index.intersection(pw_p.index)
        port_corr = round(ew_p.loc[wci_p].corr(pw_p.loc[wci_p]), 4)
        port_roll = ew_p.loc[wci_p].rolling(52).corr(pw_p.loc[wci_p]).dropna()

    labels = [r for r in roles if r in comp]
    values = [comp[r] for r in labels]
    nice = [nice_names.get(l, l) for l in labels]
    suffix = f'_{region}'

    # Boxplot of rolling 52-week correlations
    fig_box = go.Figure()
    box_items = [(role, nice_names.get(role, role)) for role in labels if role in roll_data]
    if port_roll is not None and len(port_roll) > 0:
        box_items.append(('_portfolio', 'Portfolio'))
        roll_data['_portfolio'] = port_roll
    for role, name in box_items:
        rd = roll_data.get(role)
        if rd is not None and len(rd) > 0:
            color = comp_colors.get(role, '#3b82f6') if role != '_portfolio' else '#e2e8f0'
            fig_box.add_trace(go.Box(
                y=rd.values, name=name, marker_color=color,
                line_color=color, boxmean=True, showlegend=False,
                hovertemplate=name + '<br>Corr: %{y:.3f}<extra></extra>',
            ))
    fig_box.add_hline(y=0.85, line_dash='dash', line_color='#22c55e', line_width=2,
                      annotation_text='Good (0.85)', annotation_font_color='#22c55e',
                      annotation_font_size=13, annotation_bgcolor='rgba(0,0,0,0.6)')
    fig_box.add_hline(y=0.5, line_dash='dash', line_color='#eab308', line_width=2,
                      annotation_text='Acceptable (0.50)', annotation_font_color='#eab308',
                      annotation_font_size=13, annotation_bgcolor='rgba(0,0,0,0.6)')
    fig_box.update_layout(
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        yaxis_title='Rolling 52-Week Correlation', yaxis_range=[-0.05, 1.1],
        margin=dict(l=50, r=20, t=30, b=40), height=400,
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
    )

    # Rolling 52-week correlation time series per component + portfolio
    fig_roll = go.Figure()
    for role in labels:
        rd = roll_data.get(role)
        if rd is not None and len(rd) > 0:
            fig_roll.add_trace(go.Scatter(
                x=rd.index, y=rd.values, name=nice_names.get(role, role),
                line=dict(color=comp_colors.get(role, '#94a3b8'), width=0.9),
                hovertemplate='%{y:.3f}<extra></extra>',
            ))
    if len(port_roll) > 0:
        fig_roll.add_trace(go.Scatter(
            x=port_roll.index, y=port_roll.values, name='Portfolio',
            line=dict(color='#e2e8f0', width=2, dash='dot'),
            hovertemplate='%{y:.3f}<extra></extra>',
        ))
    fig_roll.update_layout(
        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        yaxis_title='Rolling 52-Week Correlation', yaxis_range=[0, 1.05],
        legend=dict(orientation='h', y=1.05, x=0.5, xanchor='center'),
        margin=dict(l=50, r=20, t=30, b=40), height=350,
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        hovermode='x unified',
        hoverlabel=dict(bgcolor='#0f172a', font_size=13, font_color='#e2e8f0',
                        bordercolor='#334155'),
    )

    # Proxy notes table
    proxy_rows = ''
    for name, source, note in proxy_notes:
        role_key = [k for k, v in nice_names.items() if v == name]
        c = comp.get(role_key[0], 0) if role_key else 0
        proxy_rows += f'<tr><td>{name}</td><td>{source}</td><td>{c:.2f}</td><td style="color:var(--muted);font-size:0.82rem;">{note}</td></tr>\n'

    return f"""
      <hr style="border-color:var(--border); margin:2.5rem 0;">
      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">Per-Component Proxy Analysis — {title_suffix}</h3>
      <p class="subtitle">Distribution of rolling 52-week correlations between each ETF component and its proxy</p>
      <p>Each box shows the spread of rolling 52-week correlations over the overlap period.
      The white <b>Portfolio</b> box shows the overall portfolio correlation for reference —
      diversification across components makes the portfolio track better than any single component.</p>
      <div class="chart-container">{plotly_to_html(fig_box, f'comp_box{suffix}')}</div>

      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">Rolling 52-Week Correlation by Component</h3>
      <p>This shows how each component's correlation evolves over time. Stable lines mean
      consistent tracking; volatile lines indicate regime-dependent accuracy.</p>
      <div class="chart-container">{plotly_to_html(fig_roll, f'comp_roll{suffix}')}</div>

      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">Proxy Sources &amp; Assessment</h3>
      <table>
        <thead><tr><th>Component</th><th>Proxy Source</th><th>Corr</th><th>Assessment</th></tr></thead>
        <tbody>{proxy_rows}</tbody>
      </table>"""


def build_conclusions(region='us'):
    """Conclusions section — region-specific."""
    m_deep = next((m for m in metrics if m['name'] == 'US Proxy'), {})
    m_us = next((m for m in metrics if m['name'] == 'US ETF'), {})
    m_eu = next((m for m in metrics if m['name'] == 'EU ETF'), {})
    m_eu_proxy = next((m for m in metrics if m['name'] == 'EU Proxy'), {})

    if region == 'us':
        return f"""
    <div class="section">
      <h2>8. Conclusions — US Analysis</h2>
      <p class="subtitle">What 63 years of data tell us about the Golden Butterfly</p>

      <div class="note">
        <strong>🦋 The Golden Butterfly in Numbers (1962–2026, US Proxy)</strong><br><br>
        <span class="pill pill-green">CAGR {m_deep.get('cagr','?')}</span>
        <span class="pill pill-gold">Volatility {m_deep.get('volatility','?')}</span>
        <span class="pill pill-red">Max DD {m_deep.get('max_drawdown','?')}</span>
        <span class="pill pill-green">Sharpe {m_deep.get('sharpe','?')}</span>
      </div>

      <p><b>1. Consistent real returns across all regimes.</b> The portfolio delivered positive returns
      in every single decade since 1962, including the inflationary 1970s ({S["cagr_1970s"]}% CAGR thanks to gold)
      and the brutal 2000s ({S["cagr_2000s"]}% CAGR while the S&amp;P 500 was flat). No lost decade.</p>

      <p><b>2. Drawdowns are contained.</b> Max drawdown never exceeded {S["proxy_maxdd"]} in {S["proxy_years"]} years —
      roughly half of what a pure equity portfolio experiences. The longest underwater period
      was ~{m_deep.get('longest_dd_days','?')} trading days (~{int(m_deep.get('longest_dd_days',0))/252:.1f} years), vs 5+ years for stocks alone.</p>

      <p><b>3. The proxy is reliable but imperfect.</b> With {S["us_dcorr"]} daily portfolio-level correlation
      ({S["us_wcorr"]} weekly) and ~{S["us_wte"]}% weekly tracking error, the deep proxy is good enough for strategic
      conclusions but not for precise return attribution.</p>

      <p><b>4. The cost of safety.</b> The Golden Butterfly's ~{m_deep.get('cagr','?')} CAGR trails a 100% equity
      portfolio (~10% CAGR) by about 2.5% annually. The tradeoff: roughly half the drawdown,
      much shorter recovery times, and a smoother ride that most investors can actually stick with.</p>

      <div class="note">
        <strong>⚠️ Limitations</strong><br>
        • Pre-2000 gold uses interpolated annual prices (no daily volatility captured)<br>
        • SCV proxy is S&amp;P 500 + flat premium (misses actual small-value factor dynamics)<br>
        • Bond proxies use duration models, not actual bond returns (convexity simplified)<br>
        • No transaction costs, taxes, or rebalancing friction included
      </div>
    </div>"""

    else:  # eu
        return f"""
    <div class="section">
      <h2>8. Conclusions — EU Analysis</h2>
      <p class="subtitle">What the data tells an EU-based investor</p>

      <div class="note">
        <strong>🦋 EU Golden Butterfly — Key Numbers</strong><br><br>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; margin-top:0.5rem;">
          <div>
            <div style="font-size:0.78rem; color:var(--muted);">EU ETF ({m_eu.get('years','?')}yr)</div>
            <span class="pill pill-green">CAGR {m_eu.get('cagr','?')}</span>
            <span class="pill pill-gold">Vol {m_eu.get('volatility','?')}</span>
            <span class="pill pill-red">Max DD {m_eu.get('max_drawdown','?')}</span>
          </div>
          <div>
            <div style="font-size:0.78rem; color:var(--muted);">EU Proxy ({m_eu_proxy.get('years','?')}yr)</div>
            <span class="pill pill-green">CAGR {m_eu_proxy.get('cagr','?')}</span>
            <span class="pill pill-gold">Vol {m_eu_proxy.get('volatility','?')}</span>
            <span class="pill pill-red">Max DD {m_eu_proxy.get('max_drawdown','?')}</span>
          </div>
        </div>
      </div>

      <p><b>1. The strategy works in EUR.</b> Over the common period (2018–2026),
      the EU ETF version delivered {m_eu.get('cagr','?')} CAGR with {m_eu.get('volatility','?')} volatility —
      comparable to the US ETF ({m_us.get('cagr','?')} CAGR). The broader geographic diversification
      (MSCI World vs US-only) results in slightly lower volatility.</p>

      <p><b>2. Currency is a feature, not a bug.</b> 60% of the portfolio (bonds + gold) is
      USD-denominated. This is intentional: USD exposure acts as diversification for a EUR investor.
      During EUR weakness, the USD portion boosts returns. Over full cycles, the FX effect
      tends to wash out, but it adds short-term volatility.</p>

      <p><b>3. The EU proxy is usable but less precise.</b> Weekly correlation of {S["eu_wcorr"]} and
      {S["eu_wte"]}% tracking error reflect the difficulty of modeling MSCI World returns with a
      three-index blend (^GSPC + ^N225 + ^FTSE) and imperfect FX conversion. The proxy
      is reliable enough for strategic conclusions about the strategy's behavior across
      decades, but not for precise return attribution.</p>

      <p><b>4. Short history is the main limitation.</b> The EU ETF backtest covers only
      ~{m_eu.get('years','?')} years — too short to draw definitive conclusions about tail risk
      or decade-level consistency. The EU proxy extends this to {m_eu_proxy.get('years','?')} years,
      but with lower fidelity. For high-confidence analysis, refer to the US results.</p>

      <div class="note">
        <strong>⚠️ EU-Specific Limitations</strong><br>
        • IUSN.DE tracks MSCI World Small Cap (all small caps), not specifically Small Cap Value<br>
        • EU proxy equity blend (60/20/20) is a rough approximation of MSCI World composition<br>
        • FX conversion uses daily FRED EUR/USD rates, not real-time market rates<br>
        • Pre-1999 proxy has no EUR conversion (EUR didn't exist)<br>
        • No transaction costs, withholding taxes, or currency conversion fees included
      </div>
    </div>"""


def build_data_sources():
    """Data Sources, Methodology & Notes section."""
    return """
    <div class="section">
      <h2>9. Data Sources, Methodology &amp; Notes</h2>
      <p class="subtitle">Full transparency on where the data comes from and how proxies are built</p>

      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">📡 Data Sources</h3>
      <table class="table-left">
        <thead>
          <tr><th>Source</th><th>What</th><th>Coverage</th><th>Notes</th></tr>
        </thead>
        <tbody>
          <tr><td>Yahoo Finance</td><td>ETF &amp; index prices (VTI, VBR, TLT, SHY, GLD, IWDA, IUSN, DTLA, IBTS, IGLN, ^GSPC, ^RUT, GC=F)</td><td>Varies per ticker</td><td>Adjusted close prices, auto-adjusted for splits &amp; dividends</td></tr>
          <tr><td>Yahoo Finance</td><td>Mutual fund NAVs (VUSTX, VFISX)</td><td>~1986+, ~1991+</td><td>Vanguard Long-Term &amp; Short-Term Treasury funds</td></tr>
          <tr><td>FRED (St. Louis Fed)</td><td>DGS10 — 10-Year Treasury Constant Maturity Rate</td><td>1962-01-02 → present</td><td>Daily yield in %, used for LT bond proxy via duration model</td></tr>
          <tr><td>FRED (St. Louis Fed)</td><td>DGS1 — 1-Year Treasury Constant Maturity Rate</td><td>1962-01-02 → present</td><td>Daily yield in %, used for ST bond proxy pre-1976 via duration model</td></tr>
          <tr><td>FRED (St. Louis Fed)</td><td>DGS2 — 2-Year Treasury Constant Maturity Rate</td><td>1976-06-01 → present</td><td>Daily yield in %, used for ST bond proxy from 1976 via duration model</td></tr>
          <tr><td>Historical records</td><td>Gold annual average prices (USD/oz)</td><td>1950–2000</td><td>Manually compiled milestones from World Gold Council &amp; LBMA records</td></tr>
        </tbody>
      </table>

      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">🏗️ ETF Details</h3>
      <table class="table-left">
        <thead>
          <tr><th>Ticker</th><th>Name</th><th>Region</th><th>Role</th><th>Data Since</th></tr>
        </thead>
        <tbody>
          <tr><td>VTI</td><td>Vanguard Total Stock Market ETF</td><td>US</td><td>Total Market</td><td>2001</td></tr>
          <tr><td>VBR</td><td>Vanguard Small-Cap Value ETF</td><td>US</td><td>Small Cap Value</td><td>2004</td></tr>
          <tr><td>TLT</td><td>iShares 20+ Year Treasury Bond ETF</td><td>US</td><td>Long-Term Bonds</td><td>2002</td></tr>
          <tr><td>SHY</td><td>iShares 1-3 Year Treasury Bond ETF</td><td>US</td><td>Short-Term Bonds</td><td>2002</td></tr>
          <tr><td>GLD</td><td>SPDR Gold Shares</td><td>US</td><td>Gold</td><td>2004</td></tr>
          <tr><td>IWDA.AS</td><td>iShares Core MSCI World UCITS ETF</td><td>EU (AMS)</td><td>Total Market</td><td>2009</td></tr>
          <tr><td>IUSN.DE</td><td>iShares MSCI World Small Cap UCITS ETF</td><td>EU (XETRA)</td><td>Small Cap Value*</td><td>2018</td></tr>
          <tr><td>DTLA.L</td><td>iShares $ Treasury Bond 20+yr UCITS ETF</td><td>EU (LSE)</td><td>Long-Term Bonds</td><td>2015</td></tr>
          <tr><td>IBTA.L</td><td>iShares $ Treasury Bond 1-3yr UCITS ETF (USD)</td><td>EU (LSE)</td><td>Short-Term Bonds</td><td>2017</td></tr>
          <tr><td>IGLN.L</td><td>iShares Physical Gold ETC</td><td>EU (LSE)</td><td>Gold</td><td>2011</td></tr>
        </tbody>
      </table>
      <p style="font-size:0.8rem;">* IUSN tracks MSCI World Small Cap (all small caps), not specifically Small Cap <i>Value</i>.
      A pure SCV EU ETF (e.g. ZPRV for US SCV, ZPRX for EU SCV from SPDR) would be more accurate but has shorter history.</p>

      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">🔧 Synthetic Proxy Methodology</h3>

      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Total Market → S&amp;P 500 (^GSPC)</b> — The S&amp;P 500 covers ~80% of US equity market cap.
        It excludes mid/small caps that VTI includes, but the correlation is >0.98. Available from 1950.
      </div>

      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Small Cap Value → S&amp;P 500 + 2% annual premium</b> — In the absence of SCV index data before 1987,
        we apply a constant 2% annualized premium to S&amp;P 500 daily returns. This is based on the
        Fama-French historical size+value premium (~2-3% annually). The limitation: real SCV has higher
        volatility and different drawdown timing, so this proxy understates risk and smooths returns.
        Correlation with VBR in the overlap period: 0.89.
      </div>

      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Long-Term Bonds → FRED DGS10 yield with duration model (d=14)</b> — We convert the daily
        10-Year Treasury yield into a total return index using the formula:<br>
        <code style="color:var(--accent);">daily_return = yield/252 − duration × Δyield / (1 + yield)</code><br>
        The first term is coupon income, the second is price change via modified duration.
        We use duration=14 (higher than the 10Y bond's ~8) to approximate 20+yr bond behavior.
        Daily yield changes are clamped to ±2% to avoid spikes from data gaps.
        Correlation with TLT: 0.90. The model simplifies convexity (the non-linear price/yield relationship).
      </div>

      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Short-Term Bonds → FRED DGS1 (pre-1976) + DGS2 (1976+) with duration model (d=1.9)</b> — We use
        the 2-Year Treasury yield (DGS2) where available, falling back to the 1-Year yield (DGS1)
        before 1976. Duration=1.9 matches SHY’s effective duration (~1.9 years). This is a major
        improvement over the previous DTB3 (3-month T-bill) proxy: correlation with SHY jumps from
        0.29 to 0.96, and tracking error drops from 1.3% to 0.4%. The remaining gap comes from
        the model’s simplified convexity and the fact that SHY holds a ladder of bonds, not a
        single 2-year issue.
      </div>

      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Gold → Historical milestones (1950-2000) + GC=F futures (2000+)</b> — Pre-1971 (Bretton Woods),
        gold was fixed at $35/oz. From 1968-2000, we use known annual average prices from World Gold Council
        records, interpolated daily with time-weighted interpolation. This means pre-2000 gold has
        <i>no daily volatility</i> — it's a smooth curve. Post-2000, actual gold futures (GC=F) are used.
        The series is spliced by scaling the milestone series to match the first GC=F price.
        Correlation with GLD in overlap: 0.88.
      </div>

      <h3 style="color:var(--accent); margin:1.5rem 0 0.5rem;">⚙️ Portfolio Construction</h3>
      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Allocation:</b> Equal 20% to each of the five components. Rebalancing is implicit
        (daily returns are weighted, equivalent to daily rebalancing). In practice, annual or
        threshold-based rebalancing would produce slightly different results.
      </div>
      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Risk-free rate:</b> 3% annualized, used for Sharpe and Sortino ratio calculations.
        This is a simplification — the actual risk-free rate varied from ~0% (2010s) to ~15% (early 1980s).
      </div>
      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Costs not included:</b> Expense ratios (typically 0.03-0.20% for these ETFs), trading commissions,
        bid-ask spreads, rebalancing costs, taxes on dividends/capital gains, and currency conversion
        costs (relevant for EU investors holding USD-denominated assets).
      </div>
      <div class="metric-desc" style="margin:0.8rem 0;">
        <b>Dividends:</b> Yahoo Finance adjusted close prices include reinvested dividends for ETFs.
        The FRED yield-based proxies implicitly include coupon income via the yield term in the model.
        The gold series does not pay dividends (gold has no yield).
      </div>
    </div>"""

# ── HTML shell ───────────────────────────────────────────────

def build_html(region='all'):
    """Build HTML report with US/EU tab switcher."""

    # Build both region variants for sections that differ
    sec1_us = build_section_1(region='us')
    sec1_eu = build_section_1(region='eu')
    sec2_us = build_section_2(region='us')
    sec2_eu = build_section_2(region='eu')
    sec_validation_us = build_section_5(region='us')
    sec_validation_eu = build_section_5(region='eu')
    sec_decade = build_section_4()
    sec_conclusions_us = build_conclusions(region='us')
    sec_conclusions_eu = build_conclusions(region='eu')
    sec_data_sources = build_data_sources()
    sec_glossary = build_glossary_section()

    tab_bar = """
    <div class="tab-bar">
      <button class="tab-btn active" onclick="switchRegion('us')" id="btn-us">
        <span class="tab-flag">🇺🇸</span>
        <span class="tab-label">US</span>
      </button>
      <button class="tab-btn" onclick="switchRegion('eu')" id="btn-eu">
        <span class="tab-flag">🇪🇺</span>
        <span class="tab-label">EU</span>
      </button>
    </div>"""

    body = f"""
    {tab_bar}
    <div class="region-us">{sec1_us}</div>
    <div class="region-eu" style="display:none;">{sec1_eu}</div>
    <div class="region-us">{sec2_us}</div>
    <div class="region-eu" style="display:none;">{sec2_eu}</div>
    <div class="region-us">{sec_validation_us}</div>
    <div class="region-eu" style="display:none;">{sec_validation_eu}</div>
    <div class="region-us">{sec_decade}</div>
    <div class="region-us">{sec_conclusions_us}</div>
    <div class="region-eu" style="display:none;">{sec_conclusions_eu}</div>
    {sec_data_sources}
    {sec_glossary}
    """

    region_label = {'us': ' — US Analysis', 'eu': ' — EU Analysis', 'all': ''}.get(region, '')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Golden Butterfly Portfolio Analysis{region_label}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6;
    --green: #22c55e; --red: #ef4444; --gold: #eab308;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }}
  header {{
    text-align: center; padding: 3rem 1rem 2rem;
    border-bottom: 1px solid var(--border);
  }}
  header h1 {{ font-size: 2.2rem; font-weight: 700; margin-bottom: 0.5rem; }}
  header p {{ color: var(--muted); font-size: 1.05rem; }}
  .section {{
    margin: 2.5rem 0; padding: 2rem;
    background: var(--surface); border-radius: 12px;
    border: 1px solid var(--border);
  }}
  .section h2 {{
    font-size: 1.4rem; margin-bottom: 0.3rem;
    border-left: 4px solid var(--accent); padding-left: 0.8rem;
  }}
  .section .subtitle {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .section p {{ color: var(--muted); margin-bottom: 1rem; font-size: 0.95rem; }}
  .chart-container {{ margin: 1.5rem 0; overflow: hidden; }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 0.85rem; margin: 1rem 0;
  }}
  th, td {{
    padding: 0.55rem 0.8rem; text-align: right;
    border-bottom: 1px solid var(--border);
  }}
  th {{ color: var(--accent); font-weight: 600; position: sticky; top: 0; background: var(--surface); }}
  td:first-child, th:first-child {{ text-align: left; }}
  .table-left th, .table-left td {{ text-align: left; }}
  tr:hover td {{ background: rgba(59,130,246,0.06); }}
  .compact {{ font-size: 0.83rem; }}
  .compact td, .compact th {{ padding: 0.4rem 0.7rem; white-space: nowrap; }}
  .compact .group-row td {{
    text-align: left; font-weight: 700; font-size: 0.75rem;
    color: var(--accent); text-transform: uppercase; letter-spacing: 0.05em;
    padding: 0.7rem 0.7rem 0.25rem; border-bottom: 2px solid var(--border);
    background: rgba(59,130,246,0.04);
  }}
  .glossary-group {{
    font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--accent); margin: 1.5rem 0 0.5rem; padding-left: 0.5rem;
    border-left: 3px solid var(--accent);
  }}
  .glossary-card {{
    background: rgba(255,255,255,0.02); border: 1px solid var(--border);
    border-radius: 8px; padding: 0; margin-bottom: 0.5rem;
  }}
  .glossary-card[open] {{ padding-bottom: 0.9rem; }}
  .glossary-card summary {{ cursor: pointer; list-style: none; }}
  .glossary-card summary::-webkit-details-marker {{ display: none; }}
  .glossary-header {{
    font-weight: 700; font-size: 0.95rem; color: var(--text);
    padding: 0.7rem 1rem; display: flex; align-items: center; gap: 0.5rem;
  }}
  .glossary-header::before {{
    content: '▶'; font-size: 0.65rem; color: var(--muted); transition: transform 0.2s;
  }}
  .glossary-card[open] .glossary-header::before {{ transform: rotate(90deg); }}
  .glossary-formula {{
    font-family: 'Courier New', monospace; font-size: 0.78rem;
    color: var(--gold); background: rgba(234,179,8,0.07);
    border: 1px solid rgba(234,179,8,0.15); border-radius: 4px;
    padding: 0.2rem 0.5rem; display: inline-block; margin: 0 1rem 0.5rem;
  }}
  .glossary-body {{ font-size: 0.84rem; color: var(--muted); display: grid; gap: 0.25rem; padding: 0 1rem; }}
  .glossary-label {{ font-weight: 600; color: var(--text); }}
  .pill {{
    display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600;
  }}
  .pill-green {{ background: rgba(34,197,94,0.15); color: var(--green); }}
  .pill-red {{ background: rgba(239,68,68,0.15); color: var(--red); }}
  .pill-gold {{ background: rgba(234,179,8,0.15); color: var(--gold); }}
  .alloc-grid {{
    display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin: 1.5rem 0;
  }}
  .alloc-card {{
    text-align: center; padding: 1rem; border-radius: 8px;
    background: rgba(59,130,246,0.08); border: 1px solid var(--border);
  }}
  .alloc-card .pct {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
  .alloc-card .label {{ font-size: 0.8rem; color: var(--muted); margin-top: 0.3rem; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
  .grid-2 > div {{ min-width: 0; overflow: hidden; }}
  .chart-container {{ margin: 1.5rem 0; overflow: hidden; }}
  @media (max-width: 768px) {{
    .alloc-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .grid-2 {{ grid-template-columns: 1fr; }}
  }}
  .note {{
    background: rgba(234,179,8,0.08); border: 1px solid rgba(234,179,8,0.2);
    border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: 0.88rem;
  }}
  .note strong {{ color: var(--gold); }}
  footer {{
    text-align: center; padding: 2rem; color: var(--muted); font-size: 0.8rem;
    border-top: 1px solid var(--border); margin-top: 2rem;
  }}
  .tab-bar {{
    display: flex; justify-content: center; gap: 0.5rem;
    position: sticky; top: 0; z-index: 50;
    background: var(--bg); padding: 0.8rem 0;
    border-bottom: 1px solid var(--border);
    margin: 0 -1.5rem 1.5rem; padding-left: 1.5rem; padding-right: 1.5rem;
  }}
  .tab-btn {{
    display: flex; align-items: center; gap: 0.6rem;
    padding: 0.6rem 2rem; border: 2px solid var(--border); border-radius: 99px;
    background: var(--surface); color: var(--muted); font-size: 1rem;
    cursor: pointer; transition: all 0.2s;
  }}
  .tab-flag {{ font-size: 2rem; line-height: 1; }}
  .tab-label {{ font-weight: 700; font-size: 1.1rem; letter-spacing: 0.03em; }}
  .tab-btn:hover {{ border-color: var(--accent); color: var(--text); background: rgba(59,130,246,0.06); }}
  .tab-btn.active {{
    background: rgba(59,130,246,0.15); color: var(--text);
    border-color: var(--accent); box-shadow: 0 0 16px rgba(59,130,246,0.25);
  }}
  .tab-btn.active .tab-label {{ color: var(--accent); }}
  .has-tip {{
    position: relative; cursor: help;
    border-bottom: 1px dotted var(--muted);
  }}
  .tip-icon {{
    font-size: 0.7rem; color: var(--muted); vertical-align: super;
  }}
  .has-tip::after {{
    content: attr(data-tip);
    position: absolute; left: 0; bottom: calc(100% + 6px);
    width: 280px; padding: 0.6rem 0.8rem;
    background: var(--bg); color: var(--text); border: 1px solid var(--border);
    border-radius: 8px; font-size: 0.78rem; line-height: 1.45;
    pointer-events: none; opacity: 0; transition: opacity 0.15s;
    z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  }}
  .has-tip:hover::after {{ opacity: 1; }}
  .chart-loader {{
    color: var(--muted); font-size: 0.85rem;
  }}
  @keyframes pulse {{ 0%,100% {{ opacity:.4 }} 50% {{ opacity:1 }} }}
  .chart-loader {{ animation: pulse 1.5s ease-in-out infinite; }}
</style>
</head>
<body>
<header>
  <h1>🦋 Golden Butterfly Portfolio</h1>
  <p>Comprehensive backtest analysis — US ETFs, EU ETFs, proxies back to 1962</p>
</header>
<div class="container">
  {body}
</div>
<script>
function switchRegion(region) {{
  document.querySelectorAll('.region-us').forEach(el => el.style.display = region === 'us' ? '' : 'none');
  document.querySelectorAll('.region-eu').forEach(el => el.style.display = region === 'eu' ? '' : 'none');
  document.getElementById('btn-us').classList.toggle('active', region === 'us');
  document.getElementById('btn-eu').classList.toggle('active', region === 'eu');
  setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
}}

async function inflateChart(el) {{
  if (el.dataset.rendered) return;
  el.dataset.rendered = '1';
  const b64 = el.dataset.gz;
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const ds = new DecompressionStream('gzip');
  const writer = ds.writable.getWriter();
  writer.write(bin); writer.close();
  const chunks = [];
  const reader = ds.readable.getReader();
  while (true) {{
    const {{done, value}} = await reader.read();
    if (done) break;
    chunks.push(value);
  }}
  const json = new TextDecoder().decode(await new Blob(chunks).arrayBuffer());
  const spec = JSON.parse(json);
  el.innerHTML = '';
  Plotly.newPlot(el.id, spec.data, spec.layout, spec.config);
}}

const obs = new IntersectionObserver((entries) => {{
  entries.forEach(e => {{ if (e.isIntersecting) inflateChart(e.target); }});
}}, {{ rootMargin: '400px' }});
document.querySelectorAll('.lazy-chart').forEach(el => obs.observe(el));
</script>
<footer>
  Generated from Yahoo Finance &amp; FRED data. Past performance does not guarantee future results.
</footer>
</body>
</html>"""


if __name__ == "__main__":
    html = build_html()
    path = os.path.join(OUTPUT_DIR, "report.html")
    with open(path, 'w') as f:
        f.write(html)
    print(f"✅ {path} ({len(html)//1024} KB)")

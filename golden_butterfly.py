"""
Golden Butterfly Portfolio Analysis
====================================
Allocation: 20% Total Market, 20% SCV, 20% LT Bonds, 20% ST Bonds, 20% Gold

Phase 1: US & EU ETF backtests with comprehensive metrics
Phase 2: Deep proxy back to ~1962 using FRED yields + synthetic gold
Phase 3: Proxy vs ETF validation on overlapping period
"""

import yfinance as yf
import pandas as pd
import numpy as np
import io, requests, json, os, warnings
from datetime import datetime
warnings.filterwarnings('ignore')

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOC = {'total_market': 0.20, 'scv': 0.20, 'lt_bonds': 0.20, 'st_bonds': 0.20, 'gold': 0.20}

US_ETFS = {'total_market': 'VTI', 'scv': 'VBR', 'lt_bonds': 'TLT', 'st_bonds': 'SHY', 'gold': 'GLD'}
EU_ETFS = {
    'total_market': 'IWDA.AS',  # iShares MSCI World (EUR)
    'scv': 'IUSN.DE',           # iShares MSCI World Small Cap (EUR)
    'lt_bonds': 'DTLA.L',       # iShares $ Treasury 20+yr (USD)
    'st_bonds': 'IBTA.L',       # iShares $ Treasury 1-3yr (USD)
    'gold': 'IGLN.L',           # iShares Physical Gold (USD)
}
PROXY_TICKERS = {
    'total_market': '^GSPC', 'scv': '^RUT',
    'lt_bonds': 'VUSTX', 'st_bonds': 'VFISX', 'gold': 'GC=F',
}

# ── Helpers ──────────────────────────────────────────────────

def yf_download(tickers_dict, start="1900-01-01", end=None):
    end = end or datetime.now().strftime("%Y-%m-%d")
    frames = {}
    for role, ticker in tickers_dict.items():
        print(f"  {ticker:12s} ({role})")
        try:
            df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            s = df['Close'].rename(role)
            s.index = s.index.tz_localize(None) if s.index.tz else s.index
            frames[role] = s
        except Exception as e:
            print(f"    ERROR: {e}")
    if not frames: return pd.DataFrame()
    return pd.concat(frames.values(), axis=1).dropna()


def fred_csv(series_id, start="1950-01-01"):
    """Download a FRED series as CSV."""
    url = (f"https://fred.stlouisfed.org/graph/fredgraph.csv"
           f"?bgcolor=%23e1e9f0&fo=open+sans&ts=12&tts=12"
           f"&id={series_id}&cosd={start}&fq=Daily")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), parse_dates=[0], index_col=0, na_values='.')
    return df.dropna().iloc[:, 0]


def yield_to_total_return(yield_pct, duration, freq=252):
    """Convert yield series (%) to total return index via duration approximation.
    Clamp daily yield changes to avoid extreme outliers from data gaps."""
    y = yield_pct / 100.0
    dy = y.diff().clip(-0.02, 0.02)  # clamp ±2% daily change
    coupon = y.shift(1) / freq
    price_chg = -duration * dy / (1 + y.shift(1))  # modified duration
    daily_ret = (coupon + price_chg).fillna(0).clip(-0.10, 0.10)
    return (1 + daily_ret).cumprod()


def build_gold_series(start="1950-01-01"):
    """Build gold price series: $35 pre-1968, interpolated 1968-2000, GC=F after."""
    # Known gold price milestones (annual avg USD/oz)
    milestones = {
        1950: 35, 1960: 35, 1968: 39, 1970: 36, 1971: 41, 1972: 58,
        1973: 97, 1974: 159, 1975: 161, 1976: 125, 1977: 148, 1978: 193,
        1979: 306, 1980: 615, 1981: 460, 1982: 376, 1983: 424, 1984: 361,
        1985: 317, 1986: 368, 1987: 447, 1988: 437, 1989: 381, 1990: 383,
        1991: 362, 1992: 344, 1993: 360, 1994: 384, 1995: 384, 1996: 388,
        1997: 331, 1998: 294, 1999: 279, 2000: 279,
    }
    # Build daily from milestones
    idx = pd.bdate_range(start, "2000-08-29")
    ms = pd.Series(milestones)
    ms.index = pd.to_datetime(ms.index.astype(str) + "-07-01")
    ms = ms.reindex(idx).interpolate(method='time').ffill().bfill()

    # Append GC=F
    gc = yf.download("GC=F", start="2000-08-30", auto_adjust=True, progress=False)
    if isinstance(gc.columns, pd.MultiIndex):
        gc.columns = gc.columns.get_level_values(0)
    gc_s = gc['Close']
    gc_s.index = gc_s.index.tz_localize(None) if gc_s.index.tz else gc_s.index

    # Splice: scale milestone series to match GC=F start
    ratio = gc_s.iloc[0] / ms.iloc[-1]
    ms = ms * ratio
    gold = pd.concat([ms, gc_s]).sort_index()
    gold = gold[~gold.index.duplicated(keep='last')]
    return gold.rename('gold')


def _download_clean(ticker, start="1950-01-01"):
    """Download a ticker and return clean price series."""
    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    s = df['Close']
    s.index = s.index.tz_localize(None) if s.index.tz else s.index
    return s


def build_deep_proxies():
    """Build US-centric proxy price series from ~1962 onward."""
    print("\n=== Building Deep History Proxies ===")

    # S&P 500 (total market proxy)
    print("  ^GSPC (total_market)")
    total_mkt = _download_clean("^GSPC").rename('total_market')

    # SCV proxy: S&P 500 + 2% annual small-value premium
    scv_ret = total_mkt.pct_change().fillna(0) + ((1.02)**(1/252) - 1)
    scv = (1 + scv_ret).cumprod() * total_mkt.iloc[0]
    scv = scv.rename('scv')

    # Long-term bonds from FRED DGS10 (1962+)
    print("  FRED DGS10 (lt_bonds)")
    dgs10 = fred_csv("DGS10", "1950-01-01")
    lt_bonds = yield_to_total_return(dgs10, duration=14.0).rename('lt_bonds')

    # Short-term bonds: DGS1 (1962+) spliced with DGS2 (1976+), duration=1.9
    # DGS2 matches SHY's 1-3yr maturity range much better than DTB3 (3-month)
    print("  FRED DGS1+DGS2 (st_bonds)")
    dgs1 = fred_csv("DGS1", "1950-01-01")
    dgs2 = fred_csv("DGS2", "1950-01-01")
    splice_date = dgs2.index[0]
    st_yield = pd.concat([dgs1.loc[:splice_date].iloc[:-1], dgs2.loc[splice_date:]])
    st_bonds = yield_to_total_return(st_yield, duration=1.9).rename('st_bonds')

    # Gold
    print("  Gold (synthetic + GC=F)")
    gold = build_gold_series("1950-01-01")

    frames = [total_mkt, scv, lt_bonds, st_bonds, gold]
    for f in frames:
        if f.index.tz is not None:
            f.index = f.index.tz_localize(None)

    prices = pd.concat(frames, axis=1).dropna()
    print(f"  Deep proxy range: {prices.index[0].date()} to {prices.index[-1].date()} ({len(prices)} days)")
    return prices


def build_eu_deep_proxies(deep_prices):
    """Build EU-oriented proxy with currency modeling.

    The EU ETF portfolio uses:
    - IWDA.AS (EUR): MSCI World → proxy = global equity blend converted USD→EUR
    - IUSN.DE (EUR): MSCI World SC → proxy = ^RUT/blend converted USD→EUR
    - DTLA.L (USD): 20+yr Treasury → proxy = bond model (USD, no conversion)
    - IBTA.L (USD): 1-3yr Treasury → proxy = bond model (USD, no conversion)
    - IGLN.L (USD): Gold → proxy = gold (USD, no conversion)

    Currency: equity components are EUR-denominated (include USD/EUR FX implicitly).
    Bond and gold components are USD-denominated (EU investor holds USD exposure).
    The proxy converts equity returns USD→EUR using FRED EUR/USD data (1999+).
    Pre-1999: no EUR conversion (EUR didn't exist, returns are in USD).
    """
    print("\n=== Building EU Deep Proxy (global equity + FX) ===")

    print("  ^GSPC, ^N225, ^FTSE (total_market blend)")
    sp_p = _download_clean("^GSPC")
    nk_p = _download_clean("^N225")
    ft_p = _download_clean("^FTSE")

    sp_r = sp_p.pct_change()
    nk_r = nk_p.pct_change()
    ft_r = ft_p.pct_change()

    # Blended total market returns (USD)
    eu_tm_r = pd.Series(dtype=float)
    for d in sp_r.dropna().index:
        s = sp_r.get(d)
        if s is None or pd.isna(s):
            continue
        n = nk_r.get(d) if d in nk_r.index else None
        f = ft_r.get(d) if d in ft_r.index else None
        has_n = n is not None and pd.notna(n)
        has_f = f is not None and pd.notna(f)
        if has_n and has_f:
            eu_tm_r[d] = 0.60 * s + 0.20 * n + 0.20 * f
        elif has_n:
            eu_tm_r[d] = 0.70 * s + 0.30 * n
        else:
            eu_tm_r[d] = s

    # SCV (USD): ^RUT where available, else ^GSPC + premium
    print("  ^RUT + ^GSPC fallback (scv)")
    rut_p = _download_clean("^RUT")
    rut_r = rut_p.pct_change()
    premium = (1.02) ** (1 / 252) - 1
    eu_scv_r = pd.Series(dtype=float)
    for d in sp_r.dropna().index:
        r = rut_r.get(d) if d in rut_r.index else None
        s = sp_r.get(d)
        if r is not None and pd.notna(r):
            eu_scv_r[d] = r
        elif s is not None and pd.notna(s):
            eu_scv_r[d] = s + premium

    # FX data — only EUR/USD needed (no more GBP)
    print("  FRED DEXUSEU (EUR/USD)")
    eurusd = fred_csv("DEXUSEU", "1999-01-01").pct_change().dropna()
    for s in [eurusd]:
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
    print(f"    EUR/USD: {eurusd.index[0].date()} → {eurusd.index[-1].date()}")

    # Bond & gold returns from deep proxy (USD)
    deep_r = deep_prices.pct_change().dropna()
    common = eu_tm_r.index.intersection(eu_scv_r.index).intersection(deep_r.index)

    # Build portfolio returns with currency conversions
    port_r = pd.Series(dtype=float)
    for d in common:
        tm = eu_tm_r[d]
        scv = eu_scv_r[d]
        lt = deep_r['lt_bonds'].get(d, 0)
        st = deep_r['st_bonds'].get(d, 0)
        gold = deep_r['gold'].get(d, 0)

        # Equity → EUR (USD return - EUR/USD appreciation)
        eur_fx = eurusd.get(d) if d in eurusd.index else None
        if eur_fx is not None and pd.notna(eur_fx):
            tm -= eur_fx
            scv -= eur_fx

        # Bonds and gold stay in USD (matching DTLA.L, IBTA.L, IGLN.L)

        port_r[d] = 0.20 * tm + 0.20 * scv + 0.20 * lt + 0.20 * st + 0.20 * gold

    port_r = port_r.dropna()
    print(f"  EU Deep Proxy range: {common[0].date()} to {common[-1].date()} ({len(port_r)} days)")

    # Also build component prices for per-component analysis
    # Equity components: convert USD returns to EUR (matching IWDA.AS / IUSN.DE)
    eu_tm_r_eur = eu_tm_r.copy()
    eu_scv_r_eur = eu_scv_r.copy()
    for d in eu_tm_r_eur.index:
        fx = eurusd.get(d) if d in eurusd.index else None
        if fx is not None and pd.notna(fx):
            eu_tm_r_eur[d] -= fx
            eu_scv_r_eur[d] -= fx
    eu_tm_p = (1 + eu_tm_r_eur).cumprod()
    eu_tm_p = (eu_tm_p / eu_tm_p.iloc[0]).rename('total_market')
    eu_scv_p = (1 + eu_scv_r_eur).cumprod()
    eu_scv_p = (eu_scv_p / eu_scv_p.iloc[0]).rename('scv')
    # Bonds + gold stay in USD (matching DTLA.L, IBTA.L, IGLN.L)
    frames = [eu_tm_p, eu_scv_p,
              deep_prices['lt_bonds'], deep_prices['st_bonds'], deep_prices['gold']]
    prices = pd.concat(frames, axis=1).dropna()

    return prices, port_r


def portfolio_returns(prices, alloc=ALLOC):
    return (prices.pct_change().dropna() * pd.Series(alloc)).sum(axis=1)


def compute_metrics(daily_returns, name="Portfolio", rf_annual=0.03):
    dr = daily_returns.dropna()
    if len(dr) < 252:
        return {"name": name, "error": "insufficient data (<1yr)"}

    total_ret = (1 + dr).prod() - 1
    n_years = len(dr) / 252
    cagr = (1 + total_ret) ** (1 / n_years) - 1
    ann_vol = dr.std() * np.sqrt(252)
    rf_daily = (1 + rf_annual) ** (1/252) - 1
    sharpe = (dr.mean() - rf_daily) / dr.std() * np.sqrt(252) if dr.std() > 0 else 0

    downside_std = dr[dr < 0].std() * np.sqrt(252)
    sortino = (cagr - rf_annual) / downside_std if downside_std > 0 else 0

    cum = (1 + dr).cumprod()
    dd = cum / cum.cummax() - 1
    max_dd = dd.min()
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    underwater = dd < 0
    longest_dd = underwater.groupby((~underwater).cumsum()).sum().max() if underwater.any() else 0

    roll_1y = dr.rolling(252).sum()

    var95 = dr.quantile(0.05)
    cvar95 = dr[dr <= var95].mean()

    return {
        "name": name,
        "period": f"{dr.index[0].strftime('%Y-%m-%d')} → {dr.index[-1].strftime('%Y-%m-%d')}",
        "years": round(n_years, 1),
        "total_return": f"{total_ret:.1%}",
        "cagr": f"{cagr:.1%}",
        "volatility": f"{ann_vol:.1%}",
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "calmar": round(calmar, 2),
        "max_drawdown": f"{max_dd:.1%}",
        "longest_dd_days": int(longest_dd),
        "best_1y": f"{roll_1y.max():.1%}",
        "worst_1y": f"{roll_1y.min():.1%}",
        "VaR_95": f"{var95:.2%}",
        "CVaR_95": f"{cvar95:.2%}",
        "skewness": round(dr.skew(), 3),
        "kurtosis": round(dr.kurtosis(), 3),
        "daily_win_rate": f"{(dr > 0).mean():.2%}",
        "ulcer_index": round(np.sqrt((dd**2).mean()), 4),
    }


def print_table(metrics_list):
    metrics_list = [m for m in metrics_list if 'error' not in m]
    if not metrics_list: return
    keys = [k for k in metrics_list[0] if k != 'name']
    cw = max(22, *(len(m['name']) + 2 for m in metrics_list))
    hdr = f"{'Metric':<22}" + "".join(f"{m['name']:>{cw}}" for m in metrics_list)
    print(hdr)
    print("─" * len(hdr))
    for k in keys:
        print(f"{k:<22}" + "".join(f"{str(m.get(k,'')):>{cw}}" for m in metrics_list))
    print()



# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    all_ret, all_met = {}, []

    # PHASE 1a: US ETFs
    print("=" * 60)
    print("PHASE 1a: US ETF Golden Butterfly")
    print("=" * 60)
    us_p = yf_download(US_ETFS)
    if not us_p.empty:
        r = portfolio_returns(us_p)
        m = compute_metrics(r, "US ETF")
        all_ret["US ETF"], all_met = r, all_met + [m]
        print_table([m])

    # PHASE 1b: EU ETFs
    print("=" * 60)
    print("PHASE 1b: EU ETF Golden Butterfly")
    print("=" * 60)
    eu_p = yf_download(EU_ETFS)
    if not eu_p.empty:
        r = portfolio_returns(eu_p)
        m = compute_metrics(r, "EU ETF")
        all_ret["EU ETF"], all_met = r, all_met + [m]
        print_table([m])

    # PHASE 1c: Fund Proxy (mutual funds/indices)
    print("=" * 60)
    print("PHASE 1c: Fund Proxy (Funds/Indices)")
    print("=" * 60)
    px_p = yf_download(PROXY_TICKERS)
    if not px_p.empty:
        r = portfolio_returns(px_p)
        m = compute_metrics(r, "Fund Proxy")
        all_ret["Fund Proxy"], all_met = r, all_met + [m]
        print_table([m])

    # PHASE 2: US Proxy (deep synthetic history)
    print("=" * 60)
    print("PHASE 2: US Proxy (Deep History)")
    print("=" * 60)
    deep_p = build_deep_proxies()
    if not deep_p.empty:
        r = portfolio_returns(deep_p)
        m = compute_metrics(r, "US Proxy")
        all_ret["US Proxy"], all_met = r, all_met + [m]
        print_table([m])

        # Per-decade
        print("── Per-Decade (US Proxy) ──")
        dec_met = []
        for ds in range(r.index[0].year // 10 * 10, r.index[-1].year, 10):
            dr = r[(r.index.year >= ds) & (r.index.year < ds + 10)]
            if len(dr) > 200:
                dec_met.append(compute_metrics(dr, f"{ds}s"))
        if dec_met:
            print_table(dec_met)

    # PHASE 2b: EU Deep Proxy (global equity blend)
    eu_deep_p = None
    if not deep_p.empty:
        print("=" * 60)
        print("PHASE 2b: EU Deep Proxy (Global Equity + FX)")
        print("=" * 60)
        eu_deep_p, eu_proxy_ret = build_eu_deep_proxies(deep_p)
        if eu_proxy_ret is not None and len(eu_proxy_ret) > 252:
            m = compute_metrics(eu_proxy_ret, "EU Proxy")
            all_ret["EU Proxy"], all_met = eu_proxy_ret, all_met + [m]
            print_table([m])

    # PHASE 3: Validation
    print("=" * 60)
    print("PHASE 3: Proxy vs ETF Validation")
    print("=" * 60)
    if "US ETF" in all_ret and "US Proxy" in all_ret:
        common = all_ret["US ETF"].index.intersection(all_ret["US Proxy"].index)
        if len(common) > 100:
            e, p = all_ret["US ETF"].loc[common], all_ret["US Proxy"].loc[common]
            print(f"  Overlap:     {common[0].date()} → {common[-1].date()}")
            print(f"  Correlation: {e.corr(p):.4f}")
            print(f"  Ann. TE:     {(e-p).std()*np.sqrt(252):.2%}")
            print(f"  ETF CAGR:    {((1+e).prod()**(252/len(e))-1):.2%}")
            print(f"  Proxy CAGR:  {((1+p).prod()**(252/len(p))-1):.2%}")

    # Also validate individual components
    if not us_p.empty and not deep_p.empty:
        print("\n── Per-Component Correlation (daily returns, overlap) ──")
        for role in ALLOC:
            if role in us_p.columns and role in deep_p.columns:
                e_r = us_p[role].pct_change().dropna()
                p_r = deep_p[role].pct_change().dropna()
                ci = e_r.index.intersection(p_r.index)
                if len(ci) > 100:
                    corr = e_r.loc[ci].corr(p_r.loc[ci])
                    print(f"  {role:15s} corr={corr:.4f}  (n={len(ci)})")

    # Full comparison
    print("\n" + "=" * 60)
    print("FULL COMPARISON")
    print("=" * 60)
    print_table(all_met)

    with open(os.path.join(OUTPUT_DIR, "metrics.json"), 'w') as f:
        json.dump(all_met, f, indent=2)

    # Save returns for HTML report
    ret_df = pd.DataFrame(all_ret)
    ret_df.to_pickle(os.path.join(OUTPUT_DIR, "returns.pkl"))

    # Save component prices
    for label, prices in [("us_etf_prices", us_p), ("eu_etf_prices", eu_p), ("deep_proxy_prices", deep_p),
                          ("eu_deep_proxy_prices", eu_deep_p)]:
        if prices is not None and not prices.empty:
            prices.to_pickle(os.path.join(OUTPUT_DIR, f"{label}.pkl"))

    # Save decade metrics
    if dec_met:
        with open(os.path.join(OUTPUT_DIR, "decade_metrics.json"), 'w') as f:
            json.dump(dec_met, f, indent=2)

    # Save validation stats
    if "US ETF" in all_ret and "US Proxy" in all_ret:
        common = all_ret["US ETF"].index.intersection(all_ret["US Proxy"].index)
        if len(common) > 100:
            e, p = all_ret["US ETF"].loc[common], all_ret["US Proxy"].loc[common]
            val = {
                "overlap_start": str(common[0].date()),
                "overlap_end": str(common[-1].date()),
                "correlation": round(e.corr(p), 4),
                "ann_te": round((e-p).std()*np.sqrt(252), 4),
                "etf_cagr": round((1+e).prod()**(252/len(e))-1, 4),
                "proxy_cagr": round((1+p).prod()**(252/len(p))-1, 4),
            }
            # Per-component
            comp_corr = {}
            for role in ALLOC:
                if role in us_p.columns and role in deep_p.columns:
                    e_r = us_p[role].pct_change().dropna()
                    p_r = deep_p[role].pct_change().dropna()
                    ci = e_r.index.intersection(p_r.index)
                    if len(ci) > 100:
                        comp_corr[role] = round(e_r.loc[ci].corr(p_r.loc[ci]), 4)
            val["component_correlations"] = comp_corr
            with open(os.path.join(OUTPUT_DIR, "validation.json"), 'w') as f:
                json.dump(val, f, indent=2)

    print(f"\n✅ Done. Charts & data in {OUTPUT_DIR}/")

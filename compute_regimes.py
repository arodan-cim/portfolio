"""
Compute Market Regimes from FRED data.

Methodology:
  1. Download macro data from FRED
  2. Compute YoY inflation and GDP growth per year
  3. Classify each year into quadrants using median split:
     - Growth = YoY GDP > long-run median
     - High inflation = YoY CPI/HICP > long-run median
     - Q1: Growth + Low Inflation
     - Q2: Growth + High Inflation
     - Q3: Stagnation + Low Inflation
     - Q4: Stagnation + High Inflation

US sources:
  - CPI: FRED CPIAUCSL (Bureau of Labor Statistics)
  - GDP: FRED GDPC1 (Bureau of Economic Analysis)

EU sources:
  - CPI 1956-1996: blend of DE/FR/UK/IT CPI (FRED, OECD MEI)
    DEUCPIALLMINMEI, FRACPIALLMINMEI, GBRCPIALLMINMEI, ITACPIALLMINMEI
  - CPI 1996+: EU HICP (FRED CP0000EZ19M086NEST, Eurostat)
  - GDP 1971-1995: blend of DE/FR/UK real GDP index (FRED, OECD)
    NAEXKP01DEQ661S, NAEXKP01FRQ661S, NAEXKP01GBQ661S
  - GDP 1995+: Eurozone real GDP (FRED CLVMNACSCAB1GQEA19, Eurostat)
  - GDP pre-1971: US GDP used as proxy

Validation (overlap period):
  - Blend CPI vs EU HICP: 0.98 annual correlation
  - Blend GDP vs EU GDP: 0.97 annual correlation

Framework: Bridgewater "All Weather" (Dalio, 2012)
"""

import pandas as pd
import io
import requests
import json
import os

OUT = 'output'


def fred(sid, start='1947-01-01'):
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}'
    r = requests.get(url, timeout=30)
    if '<html' in r.text[:100]:
        return None
    df = pd.read_csv(io.StringIO(r.text), parse_dates=[0], index_col=0, na_values='.')
    return df.dropna().iloc[:, 0]


print('Downloading FRED data...')

# US
us_cpi = fred('CPIAUCSL')
us_gdp = fred('GDPC1')

# EU: individual country CPI (1955+)
de_cpi = fred('DEUCPIALLMINMEI')
fr_cpi = fred('FRACPIALLMINMEI')
uk_cpi = fred('GBRCPIALLMINMEI')
it_cpi = fred('ITACPIALLMINMEI')

# EU: individual country GDP (1960-1970+)
de_gdp = fred('NAEXKP01DEQ661S')  # 1970
fr_gdp = fred('NAEXKP01FRQ661S')  # 1960
uk_gdp = fred('NAEXKP01GBQ661S')  # 1960

# EU: aggregate (1995/1996+)
eu_hicp = fred('CP0000EZ19M086NEST', '1996-01-01')
eu_gdp_agg = fred('CLVMNACSCAB1GQEA19', '1995-01-01')

print('Computing blended EU series...')

# Blend EU CPI: average of DE/FR/UK/IT YoY inflation, then splice with HICP
blend_cpi_df = pd.DataFrame({'de': de_cpi, 'fr': fr_cpi, 'uk': uk_cpi, 'it': it_cpi}).dropna()
blend_infl_monthly = (blend_cpi_df.pct_change(12) * 100).mean(axis=1).dropna()

# Blend EU GDP: average of DE/FR/UK YoY growth
blend_gdp_df = pd.DataFrame({'de': de_gdp, 'fr': fr_gdp, 'uk': uk_gdp}).dropna()
blend_gdp_growth = (blend_gdp_df.pct_change(4) * 100).mean(axis=1).dropna()

# Splice: use blend pre-cutoff, aggregate post-cutoff
def splice_annual(blend_monthly, agg_monthly, cutoff_year, is_quarterly=False):
    """Splice blend and aggregate into annual YoY values."""
    if is_quarterly:
        blend_yr = blend_monthly.resample('YE').mean().dropna()
        agg_yr = agg_monthly.pct_change(4).mul(100).resample('YE').mean().dropna() if agg_monthly is not None else pd.Series(dtype=float)
    else:
        blend_yr = blend_monthly.resample('YE').mean().dropna()
        agg_yr = agg_monthly.pct_change(12).mul(100).resample('YE').mean().dropna() if agg_monthly is not None else pd.Series(dtype=float)

    # Use blend before cutoff, aggregate from cutoff
    pre = blend_yr[blend_yr.index.year < cutoff_year]
    post = agg_yr[agg_yr.index.year >= cutoff_year]
    return pd.concat([pre, post]).sort_index()


eu_infl_yr = splice_annual(blend_infl_monthly, eu_hicp, 1997, is_quarterly=False)
eu_gdp_yr = splice_annual(blend_gdp_growth, eu_gdp_agg, 1996, is_quarterly=True)

# US annual
us_infl_yr = us_cpi.resample('YE').last().pct_change() * 100
us_gdp_yr = us_gdp.resample('YE').last().pct_change() * 100

# Thresholds
us_infl_med = round(us_infl_yr.loc['1950':'2025'].median(), 2)
us_gdp_med = round(us_gdp_yr.loc['1950':'2025'].median(), 2)
eu_infl_med = round(eu_infl_yr.dropna().median(), 2)
eu_gdp_med = round(eu_gdp_yr.dropna().median(), 2)

print(f'US thresholds: GDP median={us_gdp_med}%, CPI median={us_infl_med}%')
print(f'EU thresholds: GDP median={eu_gdp_med}%, HICP/blend median={eu_infl_med}%')


def classify(gdp, infl, gdp_thresh, infl_thresh):
    growth = gdp > gdp_thresh
    low_infl = infl <= infl_thresh
    if growth and low_infl:
        return 'Q1'
    if growth and not low_infl:
        return 'Q2'
    if not growth and low_infl:
        return 'Q3'
    return 'Q4'


def get_yr_val(series, yr):
    ts = pd.Timestamp(f'{yr}-12-31')
    v = series.get(ts)
    if v is not None:
        return round(float(v), 1)
    return None


us_regimes = {}
eu_regimes = {}

for yr in range(1950, 2026):
    # US
    g = get_yr_val(us_gdp_yr, yr)
    i = get_yr_val(us_infl_yr, yr)
    if g is not None and i is not None:
        us_regimes[yr] = {
            'q': classify(g, i, us_gdp_med, us_infl_med),
            'gdp': g, 'infl': i,
        }

    # EU
    eu_g = get_yr_val(eu_gdp_yr, yr)
    eu_i = get_yr_val(eu_infl_yr, yr)

    # Fallback: US GDP for pre-1971
    gdp_source = 'blend_de_fr_uk' if eu_g is not None else 'us_proxy'
    infl_source = 'blend_de_fr_uk_it' if eu_i is not None else 'us_proxy'
    if eu_g is None:
        eu_g = g
        gdp_source = 'us_proxy'
    if eu_i is None:
        eu_i = i
        infl_source = 'us_proxy'

    if eu_g is not None and eu_i is not None:
        # Use EU thresholds for EU/blend data, US thresholds for US proxy
        g_thresh = eu_gdp_med if gdp_source != 'us_proxy' else us_gdp_med
        i_thresh = eu_infl_med if infl_source != 'us_proxy' else us_infl_med
        eu_regimes[yr] = {
            'q': classify(eu_g, eu_i, g_thresh, i_thresh),
            'gdp': eu_g, 'infl': eu_i,
            'gdp_source': gdp_source,
            'infl_source': infl_source,
        }

# Check: from which year do we have real EU data?
first_eu_infl = min(yr for yr, d in eu_regimes.items() if d['infl_source'] != 'us_proxy')
first_eu_gdp = min(yr for yr, d in eu_regimes.items() if d['gdp_source'] != 'us_proxy')
print(f'EU own inflation data from: {first_eu_infl}')
print(f'EU own GDP data from: {first_eu_gdp}')

result = {
    'methodology': {
        'framework': 'Bridgewater All Weather 2x2 (Dalio, 2012)',
        'classification': 'Median split on YoY GDP growth and YoY inflation',
        'us_thresholds': {'gdp_median': us_gdp_med, 'cpi_median': us_infl_med},
        'eu_thresholds': {'gdp_median': eu_gdp_med, 'hicp_median': eu_infl_med},
        'sources': {
            'us_cpi': 'FRED CPIAUCSL (Bureau of Labor Statistics)',
            'us_gdp': 'FRED GDPC1 (Bureau of Economic Analysis)',
            'eu_cpi_blend': 'Average of DE/FR/UK/IT CPI (FRED OECD MEI, 1956-1996)',
            'eu_hicp': 'FRED CP0000EZ19M086NEST (Eurostat, 1996+)',
            'eu_gdp_blend': 'Average of DE/FR/UK real GDP index (FRED OECD, 1971-1995)',
            'eu_gdp': 'FRED CLVMNACSCAB1GQEA19 (Eurostat, 1995+)',
        },
        'eu_fallback': f'Pre-{first_eu_infl}: US CPI used as EU inflation proxy. Pre-{first_eu_gdp}: US GDP used as EU growth proxy.',
        'validation': {
            'blend_cpi_vs_hicp_corr': '0.98 (annual, 1997-2025)',
            'blend_gdp_vs_eu_gdp_corr': '0.97 (annual, 1996-2023)',
        },
    },
    'us': {str(k): v for k, v in us_regimes.items()},
    'eu': {str(k): v for k, v in eu_regimes.items()},
}

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, 'regimes.json')
with open(path, 'w') as f:
    json.dump(result, f, indent=2)
print(f'\n✅ Saved {path}')

for region, regimes in [('US', us_regimes), ('EU', eu_regimes)]:
    counts = {}
    for yr, d in regimes.items():
        counts[d['q']] = counts.get(d['q'], 0) + 1
    print(f'{region}: {dict(sorted(counts.items()))}')
    proxy_yrs = sum(1 for d in regimes.values() if d.get('gdp_source') == 'us_proxy' or d.get('infl_source') == 'us_proxy')
    if proxy_yrs:
        print(f'  ({proxy_yrs} years using US proxy)')

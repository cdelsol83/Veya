"""Stress-test the strategy across every market, crash and market regime since 2004.

    python market_study.py            # writes reports/MARKETS.md + chart
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import backtest as bt
import config as C
import markets as M
from data import load_prices

OUT = Path(__file__).parent / "reports"
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
# Validated categorical slots 1-3; same entity -> same color as the charts in REPORT.md.
COLORS = {"Stocks+crypto strategy": "#2a78d6", "SPY buy & hold": "#eb6834", "All-markets strategy": "#1baf7a"}

STRESS = [
    ("2008 financial crisis", "2007-10-09", "2009-03-09"),
    ("2010 euro crisis / flash crash", "2010-04-23", "2010-07-02"),
    ("2011 US downgrade", "2011-04-29", "2011-10-03"),
    ("2015-16 China & oil crash", "2015-05-21", "2016-02-11"),
    ("2018 crypto winter", "2018-01-01", "2018-12-31"),
    ("2018 Q4 rate scare", "2018-09-20", "2018-12-24"),
    ("2020 Covid crash", "2020-02-19", "2020-03-23"),
    ("2022 inflation & rate hikes", "2022-01-03", "2022-10-12"),
    ("2025 tariff shock", "2025-02-19", "2025-04-08"),
    ("Recovery: Mar 2009 - Mar 2010", "2009-03-09", "2010-03-09"),
    ("Recovery: Covid rebound 2020", "2020-03-23", "2020-12-31"),
    ("Sideways: 2015", "2015-01-01", "2015-12-31"),
]


def pct(v):
    return "" if pd.isna(v) else f"{v:.1%}"


def md_table(df, fmts=None):
    fmts = fmts or {}
    lines = ["| " + " | ".join([df.index.name or ""] + list(df.columns)) + " |",
             "|---" * (len(df.columns) + 1) + "|"]
    for idx, row in df.iterrows():
        cells = [fmts.get(c, pct)(v) if not isinstance(v, str) else v for c, v in row.items()]
        lines.append(f"| {idx} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def per_market(prices):
    """Each market alone: buy & hold vs. the same market with only the trend filter applied."""
    rows = []
    for group, tickers in M.MARKETS.items():
        for t in tickers:
            is_crypto = t in M.CRYPTO
            cfg = bt.make_cfg(STOCKS=[] if is_crypto else [t], OTHER=[], CRYPTO=[t] if is_crypto else [],
                           TARGET_VOL=10.0, MAX_ASSET_WEIGHT=1.0, CRYPTO_CAP=1.0)
            p = prices[[t, C.CASH]]
            first = p[t].first_valid_index()
            start = p.index[p.index.get_loc(first) + cfg.TREND_LOOKBACK + 1]
            trend = bt.run(p, cfg)[0]
            trend = trend[trend.index >= start] / trend[trend.index >= start].iloc[0]
            hold = p[t][p.index >= start] / p[t][p.index >= start].iloc[0]
            mh, mt = bt.metrics(hold, prices[C.CASH]), bt.metrics(trend, prices[C.CASH])
            rows.append({
                "Class": group, "Market": f"{M.NAMES[t]} ({t})", "Since": f"{start:%Y}",
                "Hold: return/yr": mh["CAGR"], "Hold: worst drop": mh["Max drawdown"],
                "Trend: return/yr": mt["CAGR"], "Trend: worst drop": mt["Max drawdown"],
                "Sharpe hold → trend": f"{mh['Sharpe']:.2f} → {mt['Sharpe']:.2f}",
                "_better_sharpe": mt["Sharpe"] > mh["Sharpe"],
                "_smaller_dd": mt["Max drawdown"] > mh["Max drawdown"],
            })
    return pd.DataFrame(rows)


def portfolios(prices):
    sc = bt.run(prices, bt.make_cfg())[0]
    am = bt.run(prices, bt.make_cfg(**M.ALL_MARKETS_PORTFOLIO))[0]
    am_eq = bt.equal_weight(prices, bt.make_cfg(**M.ALL_MARKETS_PORTFOLIO))
    sixty = bt.run(prices, bt.make_cfg(STOCKS=["SPY"], OTHER=["IEF"], CRYPTO=[]),
                   weight_fn=lambda h: pd.Series({"SPY": 0.6, "IEF": 0.4, C.CASH: 0.0}))[0]
    return {
        "All-markets strategy": am,
        "Stocks+crypto strategy": sc,
        "SPY buy & hold": bt.buy_and_hold(prices, "SPY"),
        "60/40 SPY/IEF": sixty,
        "All markets, equal weight, no rules": am_eq,
    }


def period_return(eq, start, end):
    s = eq.dropna()
    s = s[(s.index >= start) & (s.index <= end)]
    return s.iloc[-1] / s.iloc[0] - 1 if len(s) > 1 else np.nan


def rolling_consistency(eq, years):
    e = eq.dropna()
    n = int(252 * years)
    r = (e / e.shift(n) - 1).dropna()
    return r


def regime_table(results, prices):
    spy_m = prices["SPY"].resample("ME").last().pct_change().dropna()
    buckets = pd.cut(spy_m, [-1, -0.03, 0.03, 1], labels=["Falling (SPY < -3%)", "Flat (±3%)", "Rising (SPY > +3%)"])
    rows = {}
    for name, eq in results.items():
        m = eq.resample("ME").last().pct_change().reindex(spy_m.index)
        rows[name] = m.groupby(buckets, observed=True).mean()
    df = pd.DataFrame(rows).T
    counts = buckets.value_counts()
    df.columns = [f"{c} — {counts[c]} months" for c in df.columns]
    df.index.name = "Avg monthly return when the stock market is…"
    return df


def chart(results, path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1.3]}, facecolor=SURFACE)
    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        ax.grid(color=GRID, linewidth=0.8)
        ax.tick_params(colors=INK_2)
        for s in ax.spines.values():
            s.set_visible(False)
    for name, eq in results.items():
        c = COLORS[name]
        v = eq * 10000
        ax1.plot(v.index, v, color=c, lw=2, label=name)
        ax1.annotate(f"${v.iloc[-1]:,.0f}", (v.index[-1], v.iloc[-1]), xytext=(6, 0),
                     textcoords="offset points", va="center", color=INK, fontsize=9)
        ax2.plot(eq.index, eq / eq.cummax() - 1, color=c, lw=2)
    ax1.set_yscale("log")
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax1.set_ylabel("Value of $10,000 (log scale)", color=INK_2)
    ax1.set_title("All-markets vs. stocks+crypto strategy vs. S&P 500", color=INK, loc="left", fontsize=13)
    ax1.legend(frameon=False, labelcolor=INK)
    ax2.set_ylabel("Drawdown", color=INK_2)
    ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    prices = load_prices(M.ALL + [C.CASH], C.START)
    cash = prices[C.CASH]

    pm = per_market(prices)
    helped_sharpe, helped_dd = pm["_better_sharpe"].sum(), pm["_smaller_dd"].sum()
    pm_view = pm.drop(columns=["_better_sharpe", "_smaller_dd"]).set_index("Market")
    pm_view.index.name = "Market"

    results = portfolios(prices)
    summary = pd.DataFrame({k: bt.metrics(v, cash) for k, v in results.items()}).T
    summary.index.name = "Portfolio"
    num = {"Sharpe": "{:.2f}", "Sortino": "{:.2f}", "Calmar": "{:.2f}", "Longest drawdown (days)": "{:,.0f}"}
    sfmt = {c: (lambda f: (lambda v: f.format(v)))(num[c]) if c in num else pct for c in summary.columns}

    stress = pd.DataFrame({name: {k: period_return(v, s, e) for k, v in results.items()}
                           for name, s, e in STRESS}).T
    stress.index.name = "Period"

    roll = {}
    for k, v in results.items():
        r3, r5, r1 = rolling_consistency(v, 3), rolling_consistency(v, 5), rolling_consistency(v, 1)
        roll[k] = {"1-yr windows positive": (r1 > 0).mean(), "Worst 1 yr": r1.min(),
                   "3-yr windows positive": (r3 > 0).mean(), "Worst 3 yrs": r3.min(),
                   "5-yr windows positive": (r5 > 0).mean(), "Worst 5 yrs": r5.min()}
    roll = pd.DataFrame(roll).T
    roll.index.name = "Portfolio"

    yearly = pd.DataFrame({k: bt.yearly_returns(v) for k, v in results.items()})
    yearly.index.name = "Year"

    chart({k: results[k] for k in ["All-markets strategy", "Stocks+crypto strategy", "SPY buy & hold"]},
          OUT / "equity_all_markets.png")

    report = f"""# All-markets stress test

Data through **{prices.index[-1]:%Y-%m-%d}**. Research only, not financial advice; past results
do not predict future ones. Costs and next-day fills are included as in `REPORT.md`.

## 1. Every market on its own: does the trend filter help?

For each market: just holding it vs. holding it only while it's above its {C.TREND_LOOKBACK}-day
average (otherwise cash). The trend filter **improved risk-adjusted return (Sharpe) in
{helped_sharpe} of {len(pm)} markets** and **reduced the worst drop in {helped_dd} of {len(pm)}**.

{md_table(pm_view)}

## 2. Portfolios, full history

The **all-markets strategy** uses the same rules on {len(M.ALL_MARKETS_PORTFOLIO['STOCKS']) + len(M.ALL_MARKETS_PORTFOLIO['OTHER']) + len(M.ALL_MARKETS_PORTFOLIO['CRYPTO'])} markets:
stocks {', '.join(M.ALL_MARKETS_PORTFOLIO['STOCKS'])}; bonds/commodities/real estate
{', '.join(M.ALL_MARKETS_PORTFOLIO['OTHER'])}; crypto {', '.join(M.ALL_MARKETS_PORTFOLIO['CRYPTO'])};
max {M.ALL_MARKETS_PORTFOLIO['MAX_ASSET_WEIGHT']:.0%} per asset.

![All markets](equity_all_markets.png)

{md_table(summary, sfmt)}

## 3. Crashes, recoveries and sideways markets

Total return over each period (blank = portfolio not yet running).

{md_table(stress)}

## 4. By market regime

Average monthly return, grouping every month since {prices.index[0]:%Y} by what the S&P 500 did.

{md_table(regime_table(results, prices))}

## 5. Consistency: how often was a holding period profitable?

Share of all rolling 1-, 3- and 5-year windows (start on any day) that ended in profit.

{md_table(roll)}

## 6. Calendar years

{md_table(yearly)}
"""
    (OUT / "MARKETS.md").write_text(report)
    print(md_table(summary, sfmt))
    print()
    print(md_table(stress))
    print()
    print(md_table(roll))
    print(f"\nTrend filter helped Sharpe in {helped_sharpe}/{len(pm)}, drawdown in {helped_dd}/{len(pm)}")


if __name__ == "__main__":
    main()

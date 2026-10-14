"""Run the backtest and write reports/REPORT.md plus charts.

    python run_backtest.py            # uses cached data if present
    python run_backtest.py --refresh  # re-download prices
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import backtest as bt
import config as C
from data import load_prices

OUT = Path(__file__).parent / "reports"
# Categorical slots 1-3 of the validated reference palette (light mode).
COLORS = {"Strategy": "#2a78d6", "SPY buy & hold": "#eb6834", "Equal weight, no rules": "#1baf7a"}
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def fmt(k, v):
    if isinstance(v, str):
        return v
    if k in ("Sharpe", "Sortino", "Calmar"):
        return f"{v:.2f}"
    if k.startswith("Longest"):
        return f"{int(v):,}"
    return f"{v:.1%}"


def table(results, cash):
    rows = {name: bt.metrics(eq, cash) for name, eq in results.items()}
    df = pd.DataFrame(rows)
    lines = ["| Metric | " + " | ".join(df.columns) + " |", "|---" * (len(df.columns) + 1) + "|"]
    for k in df.index:
        lines.append(f"| {k} | " + " | ".join(fmt(k, df.loc[k, c]) for c in df.columns) + " |")
    return "\n".join(lines)


def rebase(series, start):
    s = series[series.index >= start].dropna()
    return s / s.iloc[0]


def chart(results, path, title):
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
        ax1.plot(eq.index, eq * 10000, color=c, lw=2, label=name)
        ax1.annotate(f"${eq.iloc[-1] * 10000:,.0f}", (eq.index[-1], eq.iloc[-1] * 10000), xytext=(6, 0),
                     textcoords="offset points", va="center", color=INK, fontsize=9)
        ax2.plot(eq.index, eq / eq.cummax() - 1, color=c, lw=2)
    ax1.set_yscale("log")
    ax1.set_ylabel("Value of $10,000 (log scale)", color=INK_2)
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax1.set_title(title, color=INK, loc="left", fontsize=13)
    ax1.legend(frameon=False, labelcolor=INK)
    ax2.set_ylabel("Drawdown", color=INK_2)
    ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def sensitivity(prices):
    rows = []
    for lb in (100, 150, 200, 250):
        for tv in (0.08, 0.12, 0.16):
            cfg = bt.make_cfg(TREND_LOOKBACK=lb, TARGET_VOL=tv)
            m = bt.metrics(bt.run(prices, cfg)[0], prices[C.CASH])
            rows.append(f"| {lb} | {tv:.0%} | {m['CAGR']:.1%} | {m['Max drawdown']:.1%} | {m['Sharpe']:.2f} | {m['Worst year']:.1%} |")
    head = "| Trend lookback | Target vol | CAGR | Max drawdown | Sharpe | Worst year |\n|---|---|---|---|---|---|"
    return head + "\n" + "\n".join(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    prices = load_prices(bt.risky_assets(C) + [C.CASH], C.START, refresh=args.refresh)
    strat, weights, turnover = bt.run(prices)
    results = {
        "Strategy": strat,
        "SPY buy & hold": bt.buy_and_hold(prices, "SPY"),
        "Equal weight, no rules": bt.equal_weight(prices),
    }
    cash = prices[C.CASH]

    crypto_start = pd.Timestamp("2016-01-01")  # first full year with crypto in the signal
    crypto_era = {k: rebase(v, crypto_start) for k, v in results.items()}
    crypto_era_tbl = dict(crypto_era, **{"BTC buy & hold": rebase(bt.buy_and_hold(prices, "BTC-USD"), crypto_start)})

    chart(results, OUT / "equity_full.png", f"Full history, {strat.index[0]:%Y}–{strat.index[-1]:%Y}")
    chart(crypto_era, OUT / "equity_crypto_era.png", f"Crypto era, {crypto_start:%Y}–{strat.index[-1]:%Y}")

    yearly = pd.DataFrame({k: bt.yearly_returns(v) for k, v in results.items()})
    yearly["BTC buy & hold"] = bt.yearly_returns(bt.buy_and_hold(prices, "BTC-USD"))
    ytbl = ["| Year | " + " | ".join(yearly.columns) + " |", "|---" * (len(yearly.columns) + 1) + "|"]
    for y, row in yearly.iterrows():
        ytbl.append(f"| {y} | " + " | ".join("" if pd.isna(v) else f"{v:.1%}" for v in row) + " |")

    avg_w = weights.mean().sort_values(ascending=False)
    exposure = "\n".join(f"| {k} | {v:.1%} |" for k, v in avg_w.items())
    latest = weights.iloc[-1]
    current = "\n".join(f"| {k} | {v:.1%} |" for k, v in latest[latest > 0.0005].sort_values(ascending=False).items())

    report = f"""# Backtest report

Generated from data through **{strat.index[-1]:%Y-%m-%d}**. Past performance does not predict
future results. This is a research tool, not financial advice.

Strategy settings: trend filter {C.TREND_LOOKBACK}-day SMA, inverse-volatility weights
({C.VOL_LOOKBACK}-day), target volatility {C.TARGET_VOL:.0%}, crypto cap {C.CRYPTO_CAP:.0%},
single-asset cap {C.MAX_ASSET_WEIGHT:.0%}, no leverage, costs {C.COST_BPS['stock']} bps stocks /
{C.COST_BPS['crypto']} bps crypto per trade, fills at next day's close.

## Full history

![Full history](equity_full.png)

{table(results, cash)}

## Crypto era (since {crypto_start:%Y})

![Crypto era](equity_crypto_era.png)

{table(crypto_era_tbl, cash)}

## Calendar-year returns

{chr(10).join(ytbl)}

## Robustness: does it only work with one lucky setting?

Each row reruns the full history with different parameters. If results collapsed away
from the default (200 days, 12%), the strategy would be curve-fit.

{sensitivity(prices)}

## How the money was usually allocated

Average weight over all rebalances (cash = {C.CASH}):

| Asset | Avg weight |
|---|---|
{exposure}

Average monthly turnover: {turnover.mean():.1%} of the portfolio.

## Most recent allocation ({weights.index[-1]:%Y-%m-%d})

| Asset | Weight |
|---|---|
{current}
"""
    (OUT / "REPORT.md").write_text(report)
    print(table(results, cash))
    print(f"\nReport written to {OUT / 'REPORT.md'}")


if __name__ == "__main__":
    main()

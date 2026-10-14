# Stocks + crypto trend & risk-balanced strategy

A rules-based, monthly-rebalanced portfolio across stock ETFs and crypto, with a
backtester so you can see how it behaved through 2008, 2018, 2020 and 2022 before
risking money. **Research tool, not financial advice. No strategy wins in every market.**

## The rules

Once a month, at the month-end close (orders filled at the next day's close):

1. **Universe** – SPY, QQQ, IWM, EFA, EEM (stocks) and BTC, ETH (crypto). Cash = SHY.
2. **Trend filter** – hold an asset only if its price is above its 200-day average.
   Anything in a downtrend gets 0%.
3. **Risk balance** – weight the survivors by 1 / volatility (60-day), so a volatile
   asset like Bitcoin gets a smaller slice than SPY.
4. **Limits** – crypto ≤ 20% of the portfolio in total, any single asset ≤ 35%, no leverage.
5. **Volatility target** – if the mix is expected to swing more than 12%/year, scale
   it down and put the rest in SHY.

All settings are in `config.py`.

## Usage

```bash
pip install -r requirements.txt
python run_backtest.py --refresh     # download data, write reports/REPORT.md + charts
python signals.py --value 10000      # what to hold right now for a $10k account
python -m pytest -q tests            # sanity checks, incl. no look-ahead bias
```

## What the backtest shows (2004 – Oct 2026)

See [`reports/REPORT.md`](reports/REPORT.md) for full tables and charts.

| | Strategy | SPY buy & hold |
|---|---|---|
| Annual return | 8.6% | 10.9% |
| Worst drawdown | **-21.6%** | -55.2% |
| Worst year | **-15.3%** | -36.8% (2008) |
| Longest time underwater | **566 days** | 1,223 days |
| Return per unit of drawdown (Calmar) | **0.40** | 0.20 |

**The honest read:**
- It does **not** beat the S&P 500 on raw return. It gives up ~2%/year for losses
  roughly *less than half as deep*. In 2008 it lost 6.6% while SPY lost 37%.
- It **does** lose money in some years (2010–11, 2015, 2018, 2022). Choppy,
  trendless markets are its weak spot: it gets whipsawed in and out.
- Those deeper-loss-avoidance results hold across trend lengths of 100–250 days and
  vol targets of 8–16% (see the robustness table), so it isn't one lucky setting.
- Want more return? Raise `TARGET_VOL` (16% ≈ 9.7%/yr, -27% max drawdown) or
  `CRYPTO_CAP`. More return always comes with bigger drawdowns.
- "Equal weight, no rules" returned far more, almost entirely from holding ~29%
  in crypto during its 2016–2021 boom, with -57% drawdowns. Don't assume that repeats.

## Limitations

- Backtests flatter results: ETFs and coins listed today are the survivors.
- Crypto history is short (mostly one long bull run plus two crashes).
- Taxes are ignored; monthly rebalancing in a taxable account creates short-term gains.
- Costs are modeled at 5 bps (stocks) / 25 bps (crypto) per trade; yours may differ.

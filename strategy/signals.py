"""Print what the strategy would hold today, given the latest closes.

    python signals.py --value 10000
"""
import argparse

import backtest as bt
import config as C
from data import load_prices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--value", type=float, default=10_000, help="account size in dollars")
    args = ap.parse_args()
    prices = load_prices(bt.risky_assets(C) + [C.CASH], C.START, refresh=True)
    w = bt.target_weights(prices)
    print(f"Signals as of {prices.index[-1]:%Y-%m-%d} close (rebalance once a month):\n")
    risky = bt.risky_assets(C)
    sma = prices[risky].iloc[-C.TREND_LOOKBACK:].mean()
    for t in risky + [C.CASH]:
        trend = "" if t == C.CASH else ("uptrend" if prices[t].iloc[-1] > sma[t] else "downtrend -> 0%")
        print(f"  {t:8s} {w[t]:6.1%}   ${w[t] * args.value:>10,.0f}   {trend}")


if __name__ == "__main__":
    main()

"""Paper trading: run the strategy forward on real prices with a simulated account.

    python paper.py init                # open the paper accounts ($100,000 each)
    python paper.py update              # mark to market; rebalance on the first run of a new month
    python paper.py status              # print positions and performance

Each account lives in paper/<name>/ (account.json, trades.csv, equity.csv) and the summary
in paper/STATUS.md, so the whole history is versioned in git. Fills use the latest daily
close plus the same trading costs as the backtest. No real orders are ever sent.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path

import pandas as pd

import backtest as bt
import config as C
import markets as M
from data import load_prices

ROOT = Path(__file__).parent / "paper"
PROFILES = {
    "stocks_crypto": {"label": "Stocks + crypto", "overrides": {}},
    "all_markets": {"label": "All markets", "overrides": M.ALL_MARKETS_PORTFOLIO},
}
START_VALUE = 100_000.0


def cfg_for(name):
    return bt.make_cfg(**PROFILES[name]["overrides"])


def tickers_for(cfg):
    return sorted(set(bt.risky_assets(cfg) + [cfg.CASH, "SPY"]))


def fetch(cfg, refresh=True):
    return load_prices(tickers_for(cfg), C.START, refresh=refresh)


def account_dir(name):
    return ROOT / name


def load_account(name):
    return json.loads((account_dir(name) / "account.json").read_text())


def save_account(name, acct):
    (account_dir(name) / "account.json").write_text(json.dumps(acct, indent=2, sort_keys=True) + "\n")


def market_value(acct, last):
    return acct["cash_usd"] + sum(sh * last[t] for t, sh in acct["positions"].items())


def rebalance(name, acct, prices, cfg):
    """Trade to the strategy's target weights at the latest close, paying costs."""
    last = prices.iloc[-1]
    day = prices.index[-1]
    value = market_value(acct, last)
    target = bt.target_weights(prices, cfg)
    cost_rate = {t: cfg.COST_BPS["crypto" if t in cfg.CRYPTO else "stock"] / 1e4 for t in target.index}
    current = {t: acct["positions"].get(t, 0.0) * last[t] for t in target.index}
    costs = {t: abs(value * target[t] - current[t]) * cost_rate[t] for t in target.index}
    investable = value - sum(costs.values())

    trades = []
    new_positions = {}
    for t in target.index:
        dollars = investable * target[t]
        shares = dollars / last[t] if dollars > 0 else 0.0
        delta = shares - acct["positions"].get(t, 0.0)
        if abs(delta * last[t]) >= 1:
            trades.append({
                "date": f"{day:%Y-%m-%d}", "ticker": t, "side": "BUY" if delta > 0 else "SELL",
                "shares": round(abs(delta), 6), "price": round(float(last[t]), 4),
                "value": round(abs(delta) * last[t], 2),
                "cost": round(costs[t], 2),
            })
        if shares > 0:
            new_positions[t] = shares
    acct["positions"] = new_positions
    acct["cash_usd"] = 0.0
    acct["last_rebalance"] = f"{day:%Y-%m}"
    acct["target_weights"] = {t: round(float(w), 4) for t, w in target.items() if w > 0}

    path = account_dir(name) / "trades.csv"
    new_file = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "ticker", "side", "shares", "price", "value", "cost"])
        if new_file:
            w.writeheader()
        w.writerows(trades)
    return trades


def record_equity(name, acct, prices):
    last = prices.iloc[-1]
    day = f"{prices.index[-1]:%Y-%m-%d}"
    path = account_dir(name) / "equity.csv"
    rows = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["date", "value", "spy_value"])
    rows = rows[rows["date"] != day]
    row = {"date": day, "value": round(market_value(acct, last), 2),
           "spy_value": round(acct["spy_shares"] * last["SPY"], 2)}
    rows = pd.concat([rows, pd.DataFrame([row])], ignore_index=True)
    rows.to_csv(path, index=False)


def init(names, force=False):
    for name in names:
        d = account_dir(name)
        if (d / "account.json").exists() and not force:
            print(f"{name}: already exists (use --force to restart it)")
            continue
        d.mkdir(parents=True, exist_ok=True)
        for f in ("trades.csv", "equity.csv"):
            (d / f).unlink(missing_ok=True)
        cfg = cfg_for(name)
        prices = fetch(cfg)
        acct = {"profile": name, "opened": f"{prices.index[-1]:%Y-%m-%d}", "start_value": START_VALUE,
                "cash_usd": START_VALUE, "positions": {}, "last_rebalance": None,
                "spy_shares": START_VALUE / prices["SPY"].iloc[-1]}
        trades = rebalance(name, acct, prices, cfg)
        save_account(name, acct)
        record_equity(name, acct, prices)
        print(f"{name}: opened with ${START_VALUE:,.0f}, {len(trades)} trades on {acct['opened']}")


def update(names):
    for name in names:
        cfg = cfg_for(name)
        acct = load_account(name)
        prices = fetch(cfg)
        month = f"{prices.index[-1]:%Y-%m}"
        if month != acct["last_rebalance"]:
            trades = rebalance(name, acct, prices, cfg)
            print(f"{name}: monthly rebalance, {len(trades)} trades")
        save_account(name, acct)
        record_equity(name, acct, prices)
        print(f"{name}: marked to market at {prices.index[-1]:%Y-%m-%d}")
    write_status(names)


def summarize(name):
    acct = load_account(name)
    eq = pd.read_csv(account_dir(name) / "equity.csv", parse_dates=["date"]).set_index("date")
    value, spy = eq["value"].iloc[-1], eq["spy_value"].iloc[-1]
    dd = (eq["value"] / eq["value"].cummax() - 1).min()
    return acct, eq, {
        "value": value, "ret": value / acct["start_value"] - 1, "spy_ret": spy / acct["start_value"] - 1,
        "max_dd": dd, "days": len(eq),
    }


def write_status(names):
    lines = ["# Paper trading status", "",
             "Simulated accounts running the strategy on real daily closes. No real money or orders.",
             f"Updated {date.today():%Y-%m-%d}.", "",
             "| Account | Opened | Value | Return | SPY over same period | Worst drop | Days tracked |",
             "|---|---|---|---|---|---|---|"]
    holdings = []
    for name in names:
        acct, eq, s = summarize(name)
        lines.append(f"| {PROFILES[name]['label']} | {acct['opened']} | ${s['value']:,.0f} | {s['ret']:+.2%} | "
                     f"{s['spy_ret']:+.2%} | {s['max_dd']:.2%} | {s['days']} |")
        holdings += ["", f"## {PROFILES[name]['label']}: target weights (last rebalance {acct['last_rebalance']})", "",
                     "| Asset | Weight |", "|---|---|"]
        holdings += [f"| {t} | {w:.1%} |" for t, w in sorted(acct["target_weights"].items(), key=lambda x: -x[1])]
    lines += holdings
    lines += ["", "Full ledgers: `paper/<account>/trades.csv` and `paper/<account>/equity.csv`.",
              "A paper record needs many months, and ideally a few years including a downturn, before it says much."]
    (ROOT / "STATUS.md").write_text("\n".join(lines) + "\n")


def status(names):
    for name in names:
        acct, eq, s = summarize(name)
        print(f"\n{PROFILES[name]['label']} (opened {acct['opened']})")
        print(f"  Value ${s['value']:,.2f}  return {s['ret']:+.2%}  vs SPY {s['spy_ret']:+.2%}  "
              f"worst drop {s['max_dd']:.2%}")
        for t, w in sorted(acct["target_weights"].items(), key=lambda x: -x[1]):
            print(f"    {t:8s} {w:6.1%}  {acct['positions'].get(t, 0):12.4f} sh")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["init", "update", "status"])
    ap.add_argument("--account", choices=list(PROFILES), help="default: all accounts")
    ap.add_argument("--force", action="store_true", help="init: wipe and restart an existing account")
    args = ap.parse_args()
    names = [args.account] if args.account else list(PROFILES)
    if args.command == "init":
        init(names, args.force)
        write_status(names)
    elif args.command == "update":
        update(names)
    else:
        status(names)


if __name__ == "__main__":
    main()

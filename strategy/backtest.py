"""Trend-filtered, risk-balanced, volatility-targeted portfolio of stocks and crypto.

Each month-end:
  1. Keep only assets trading above their moving average (trend filter).
  2. Weight survivors by inverse volatility so each contributes similar risk.
  3. Cap single assets and the crypto sleeve.
  4. Scale the whole book to a target volatility; the rest goes to cash (SHY).
Orders are computed at the month-end close and filled at the NEXT day's close,
so the backtest never trades on information it wouldn't have had.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

import config as C

TRADING_DAYS = 252


def cap_weights(w, cap):
    """Clip weights at `cap`, handing the excess to uncapped names. Leftover stays unallocated."""
    w = w.copy()
    for _ in range(len(w)):
        over = w > cap + 1e-12
        if not over.any():
            break
        excess = (w[over] - cap).sum()
        w[over] = cap
        free = ~over & (w < cap)
        if not free.any():
            break
        w[free] += excess * w[free] / w[free].sum()
    return w


def make_cfg(**overrides):
    """A copy of config.py's settings with some values replaced."""
    base = {k: v for k, v in vars(C).items() if k.isupper()}
    base.update(overrides)
    return SimpleNamespace(**base)


def risky_assets(cfg):
    return cfg.STOCKS + cfg.OTHER + cfg.CRYPTO


def target_weights(hist, cfg=C):
    """Target weights (risky assets + cash) from price history up to and including today."""
    risky = risky_assets(cfg)
    window = hist[risky]
    enough = window.notna().sum() > max(cfg.TREND_LOOKBACK, cfg.VOL_LOOKBACK)
    last = window.iloc[-1]
    sma = window.iloc[-cfg.TREND_LOOKBACK:].mean()
    uptrend = enough & (last > sma)
    picks = [t for t in risky if uptrend[t]]

    w = pd.Series(0.0, index=risky + [cfg.CASH])
    if not picks:
        w[cfg.CASH] = 1.0
        return w

    rets = window[picks].pct_change().iloc[-cfg.VOL_LOOKBACK:]
    vol = rets.std() * np.sqrt(TRADING_DAYS)
    raw = (1 / vol) / (1 / vol).sum()

    crypto = [t for t in picks if t in cfg.CRYPTO]
    stocks = [t for t in picks if t not in cfg.CRYPTO]
    if crypto and raw[crypto].sum() > cfg.CRYPTO_CAP:
        excess = raw[crypto].sum() - cfg.CRYPTO_CAP
        raw[crypto] *= cfg.CRYPTO_CAP / raw[crypto].sum()
        if stocks:
            raw[stocks] += excess * raw[stocks] / raw[stocks].sum()
    raw = cap_weights(raw, cfg.MAX_ASSET_WEIGHT)
    if crypto:  # per-asset capping can push money back into crypto; re-enforce the sleeve cap
        raw[crypto] *= min(1.0, cfg.CRYPTO_CAP / raw[crypto].sum())

    cov = rets.cov() * TRADING_DAYS
    port_vol = float(np.sqrt(raw @ cov @ raw))
    # Only ever scale down: scaling up would break the caps above (MAX_GROSS still bounds the total).
    scale = min(1.0, cfg.MAX_GROSS / raw.sum(), cfg.TARGET_VOL / port_vol if port_vol > 0 else 1.0)
    w[picks] = raw * scale
    w[cfg.CASH] = 1.0 - w[picks].sum()
    return w


def month_ends(index):
    s = pd.Series(index, index=index)
    return set(s.groupby([index.year, index.month]).last())


def run(prices, cfg=C, weight_fn=None):
    """Daily simulation with drifting weights, monthly rebalances, next-day fills and costs.

    Returns (equity Series, weights DataFrame recorded at each fill, turnover Series).
    """
    weight_fn = weight_fn or (lambda h: target_weights(h, cfg))
    assets = risky_assets(cfg) + [cfg.CASH]
    prices = prices[assets]
    rets = prices.pct_change().fillna(0.0)
    cost = pd.Series({a: cfg.COST_BPS["crypto" if a in cfg.CRYPTO else "stock"] / 1e4 for a in assets})
    rebal_days = month_ends(prices.index)

    w = pd.Series(0.0, index=assets)
    w[cfg.CASH] = 1.0
    value, pending = 1.0, None
    equity, fills, turnover = [], {}, {}
    for i, day in enumerate(prices.index):
        if i > 0:
            r = rets.iloc[i]
            growth = float((w * (1 + r)).sum())
            value *= growth
            w = w * (1 + r) / growth
        if pending is not None:
            trade = (pending - w).abs()
            value *= 1 - float((trade * cost).sum())
            turnover[day] = float(trade.sum()) / 2
            w = pending
            fills[day] = pending
            pending = None
        if day in rebal_days and i >= 1:
            pending = weight_fn(prices.iloc[: i + 1])
        equity.append(value)
    return (
        pd.Series(equity, index=prices.index, name="equity"),
        pd.DataFrame(fills).T,
        pd.Series(turnover, name="turnover"),
    )


def buy_and_hold(prices, ticker):
    p = prices[ticker].dropna()
    return p / p.iloc[0]


def equal_weight(prices, cfg=C):
    """Same universe, equal weight, rebalanced monthly, no trend filter or vol targeting."""
    risky = risky_assets(cfg)

    def fn(hist):
        live = [t for t in risky if hist[t].notna().sum() > 1]
        w = pd.Series(0.0, index=risky + [cfg.CASH])
        w[live] = 1 / len(live)
        return w

    return run(prices, cfg, weight_fn=fn)[0]


def metrics(equity, cash_equity=None):
    e = equity.dropna()
    r = e.pct_change().dropna()
    years = (e.index[-1] - e.index[0]).days / 365.25
    cagr = (e.iloc[-1] / e.iloc[0]) ** (1 / years) - 1
    vol = r.std() * np.sqrt(TRADING_DAYS)
    rf = cash_equity.reindex(e.index).pct_change().dropna() if cash_equity is not None else 0.0
    excess = r - (rf.reindex(r.index).fillna(0) if cash_equity is not None else 0.0)
    sharpe = excess.mean() / r.std() * np.sqrt(TRADING_DAYS) if r.std() > 0 else np.nan
    downside = r[r < 0].std() * np.sqrt(TRADING_DAYS)
    dd = e / e.cummax() - 1
    underwater = (dd < 0).astype(int)
    longest = underwater.groupby((underwater == 0).cumsum()).sum().max()
    yearly = e.resample("YE").last().pct_change()
    yearly.iloc[0] = e.resample("YE").last().iloc[0] / e.iloc[0] - 1
    monthly = e.resample("ME").last().pct_change().dropna()
    return {
        "CAGR": cagr,
        "Volatility": vol,
        "Sharpe": sharpe,
        "Sortino": (r.mean() * TRADING_DAYS) / downside if downside > 0 else np.nan,
        "Max drawdown": dd.min(),
        "Longest drawdown (days)": int(longest),
        "Calmar": cagr / abs(dd.min()) if dd.min() < 0 else np.nan,
        "Worst year": yearly.min(),
        "Best year": yearly.max(),
        "Positive years": (yearly > 0).mean(),
        "Positive months": (monthly > 0).mean(),
    }


def yearly_returns(equity):
    e = equity.dropna()
    ye = e.resample("YE").last()
    out = ye.pct_change()
    out.iloc[0] = ye.iloc[0] / e.iloc[0] - 1
    out.index = out.index.year
    return out

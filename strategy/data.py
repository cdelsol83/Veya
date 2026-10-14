"""Download and align daily prices. Results are cached locally so reruns are fast."""
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).parent / "data_cache"


def load_prices(tickers, start, refresh=False):
    """Adjusted closes on the US stock-market calendar.

    Crypto trades every day; it is aligned to stock trading days by taking the
    last available price, so weekend moves show up in Monday's return.
    """
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"prices_{start}_{'_'.join(sorted(tickers))}.csv"
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)

    import yfinance as yf

    raw = yf.download(list(tickers), start=start, auto_adjust=True, progress=False)["Close"]
    raw = raw[list(tickers)]
    calendar = raw["SPY"].dropna().index
    prices = raw.ffill().reindex(calendar)
    # Don't forward-fill an asset before its first real price.
    for t in tickers:
        first = raw[t].first_valid_index()
        if first is not None:
            prices.loc[prices.index < first, t] = float("nan")
    prices.to_csv(path)
    return prices

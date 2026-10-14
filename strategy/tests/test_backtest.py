import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backtest as bt  # noqa: E402
import config as C  # noqa: E402


@pytest.fixture
def prices():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2015-01-01", periods=900)
    assets = C.STOCKS + C.CRYPTO + [C.CASH]
    vols = {a: (0.04 if a in C.CRYPTO else 0.01) for a in assets}
    vols[C.CASH] = 0.0005
    data = {a: 100 * np.cumprod(1 + rng.normal(0.0004, vols[a], len(idx))) for a in assets}
    df = pd.DataFrame(data, index=idx)
    df.loc[df.index[:300], "ETH-USD"] = np.nan  # asset listed later
    return df


def test_weights_respect_limits(prices):
    for end in range(250, len(prices), 21):
        w = bt.target_weights(prices.iloc[:end])
        assert w.min() >= -1e-12
        assert w.sum() == pytest.approx(1.0)
        assert w[C.CRYPTO].sum() <= C.CRYPTO_CAP + 1e-9
        assert w[C.STOCKS + C.CRYPTO].max() <= C.MAX_ASSET_WEIGHT + 1e-9


def test_asset_without_history_gets_no_weight(prices):
    w = bt.target_weights(prices.iloc[:400])  # ETH has only 100 days of history here
    assert w["ETH-USD"] == 0


def test_downtrend_goes_to_cash(prices):
    crash = prices.copy()
    risky = C.STOCKS + C.CRYPTO
    crash.loc[crash.index[-60:], risky] *= np.linspace(1, 0.5, 60)[:, None]
    assert bt.target_weights(crash)[C.CASH] == pytest.approx(1.0)


def test_no_lookahead(prices):
    cut = prices.index[600]
    altered = prices.copy()
    altered.loc[altered.index > cut] *= 3.0  # wildly different future
    a, _, _ = bt.run(prices)
    b, _, _ = bt.run(altered)
    pd.testing.assert_series_equal(a[:cut], b[:cut])


def test_cap_weights_redistributes():
    w = bt.cap_weights(pd.Series([0.7, 0.2, 0.1]), 0.5)
    assert w.max() <= 0.5 + 1e-12
    assert w.sum() == pytest.approx(1.0)

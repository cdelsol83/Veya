import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paper  # noqa: E402


def fake_prices(n=400, seed=1):
    rng = np.random.default_rng(seed)
    cfg = paper.cfg_for("stocks_crypto")
    idx = pd.bdate_range("2024-01-01", periods=n)
    cols = paper.tickers_for(cfg)
    return pd.DataFrame({t: 100 * np.cumprod(1 + rng.normal(0.0005, 0.01, n)) for t in cols}, index=idx)


def test_rebalance_conserves_value_minus_costs(tmp_path, monkeypatch):
    monkeypatch.setattr(paper, "ROOT", tmp_path)
    (tmp_path / "stocks_crypto").mkdir()
    prices = fake_prices()
    cfg = paper.cfg_for("stocks_crypto")
    acct = {"cash_usd": 100_000.0, "positions": {}, "last_rebalance": None, "spy_shares": 0}
    trades = paper.rebalance("stocks_crypto", acct, prices, cfg)
    costs = sum(t["cost"] for t in trades)
    after = paper.market_value(acct, prices.iloc[-1])
    assert after == pytest.approx(100_000 - costs, abs=0.05)
    weights = {t: sh * prices.iloc[-1][t] / after for t, sh in acct["positions"].items()}
    assert sum(w for t, w in weights.items() if t in cfg.CRYPTO) <= cfg.CRYPTO_CAP + 1e-9
    assert acct["last_rebalance"] == f"{prices.index[-1]:%Y-%m}"

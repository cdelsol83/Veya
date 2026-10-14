"""Strategy settings. Edit these to experiment; re-run run_backtest.py to see the effect."""

STOCKS = ["SPY", "QQQ", "IWM", "EFA", "EEM"]  # US large, US tech, US small, developed intl, emerging
CRYPTO = ["BTC-USD", "ETH-USD"]
CASH = "SHY"  # 1-3y Treasuries: where money sits when nothing is in an uptrend

START = "2004-01-01"

TREND_LOOKBACK = 200      # trading days for the moving-average trend filter
VOL_LOOKBACK = 60         # trading days used to estimate volatility / correlation
TARGET_VOL = 0.12         # annualized portfolio volatility target
MAX_GROSS = 1.0           # never use leverage
CRYPTO_CAP = 0.20         # crypto may never exceed 20% of the portfolio
MAX_ASSET_WEIGHT = 0.35   # no single asset above 35%

COST_BPS = {"stock": 5, "crypto": 25}  # one-way trading cost + slippage, basis points

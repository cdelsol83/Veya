"""Every market the study covers, grouped by asset class."""

MARKETS = {
    "US stocks": {"SPY": "S&P 500", "QQQ": "Nasdaq 100", "IWM": "Russell 2000 small caps"},
    "International stocks": {"EFA": "Developed ex-US", "EEM": "Emerging markets",
                             "VGK": "Europe", "EWJ": "Japan"},
    "Bonds": {"TLT": "20+yr Treasuries", "IEF": "7-10yr Treasuries", "TIP": "Inflation-linked Treasuries",
              "LQD": "Investment-grade corporates", "HYG": "High-yield corporates"},
    "Commodities": {"GLD": "Gold", "SLV": "Silver", "DBC": "Broad commodities",
                    "USO": "Crude oil", "DBA": "Agriculture"},
    "Real estate": {"VNQ": "US REITs"},
    "Currencies": {"UUP": "US dollar index", "FXE": "Euro", "FXY": "Japanese yen"},
    "Crypto": {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "SOL-USD": "Solana"},
}

ALL = [t for group in MARKETS.values() for t in group]
CRYPTO = list(MARKETS["Crypto"])
NAMES = {t: n for group in MARKETS.values() for t, n in group.items()}

# The diversified "all markets" portfolio: one or two liquid funds per asset class.
ALL_MARKETS_PORTFOLIO = {
    "STOCKS": ["SPY", "QQQ", "IWM", "EFA", "EEM"],
    "OTHER": ["IEF", "TLT", "TIP", "LQD", "GLD", "DBC", "VNQ"],
    "CRYPTO": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "MAX_ASSET_WEIGHT": 0.25,
}

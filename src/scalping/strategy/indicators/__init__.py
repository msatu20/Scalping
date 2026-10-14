"""Technical indicators, each in two bit-identical flavours.

- Batch (lower-case functions): numpy array in -> array out, NaN during warm-up. For backtests.
- Incremental (classes): ``update(x)`` per closed candle/tick, ``peek(x)`` for an
  uncommitted intra-candle value, ``None`` during warm-up. For live trading.
"""

from scalping.strategy.indicators.bollinger import (
    BollingerArrays,
    BollingerBands,
    BollingerValue,
    bollinger,
)
from scalping.strategy.indicators.moving_average import EMA, SMA, ema, sma
from scalping.strategy.indicators.rsi import RSI, rsi

__all__ = [
    "EMA",
    "RSI",
    "SMA",
    "BollingerArrays",
    "BollingerBands",
    "BollingerValue",
    "bollinger",
    "ema",
    "rsi",
    "sma",
]

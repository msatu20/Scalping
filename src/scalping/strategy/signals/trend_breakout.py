"""TREND_BREAKOUT: channel breakout in the direction of the trend (ADR-0010).

On every closed candle of ``params.interval``:

- channel = highest high / lowest low of the previous ``channel`` candles (current excluded);
- long if ``close > channel high`` and ``close > EMA(trend_ema)``;
  short if ``close < channel low`` and ``close < EMA(trend_ema)``;
- stop = ``atr_mult`` x ATR(``atr_period``) from the close; target = ``target_r`` x risk;
- the signal expires when the next candle closes (taker entry on the next price).

Time comes only from the injected clock.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from scalping.core.clock import Clock
from scalping.core.models import Kline, KlineInterval, MarketEvent, Side, Signal, StrategyType
from scalping.strategy.indicators import ATR, EMA
from scalping.strategy.signals.base import SignalHandler


@dataclass(frozen=True, slots=True)
class TrendBreakoutParams:
    interval: KlineInterval = KlineInterval.H1
    channel: int = 20
    trend_ema: int = 200
    atr_period: int = 14
    atr_mult: float = 2.0
    target_r: float = 2.0

    def __post_init__(self) -> None:
        if self.channel < 2 or self.trend_ema < 2 or self.atr_period < 1:
            raise ValueError("channel >= 2, trend_ema >= 2 and atr_period >= 1 required")
        if self.atr_mult <= 0 or self.target_r <= 0:
            raise ValueError("atr_mult and target_r must be > 0")


@dataclass(slots=True)
class _State:
    symbol: str
    highs: deque[float]
    lows: deque[float]
    ema: EMA
    atr: ATR
    stats: dict[str, int] = field(default_factory=dict)


class TrendBreakoutStrategy:
    def __init__(
        self,
        symbols: Sequence[str],
        clock: Clock,
        params: TrendBreakoutParams | None = None,
        on_signal: SignalHandler | None = None,
    ) -> None:
        self.params = p = params or TrendBreakoutParams()
        self._clock = clock
        self._on_signal = on_signal
        self._states = {
            s: _State(s, deque(maxlen=p.channel), deque(maxlen=p.channel), EMA(p.trend_ema),
                      ATR(p.atr_period))
            for s in symbols
        }  # fmt: skip

    def stats(self, symbol: str) -> dict[str, int]:
        return dict(self._states[symbol].stats)

    def on_event(self, event: MarketEvent) -> Signal | None:
        st = self._states.get(event.symbol)
        if st is None or not isinstance(event, Kline):
            return None
        if not event.is_closed or event.interval is not self.params.interval:
            return None
        signal = self._on_candle(st, event)
        if signal is not None and self._on_signal is not None:
            self._on_signal(signal)
        return signal

    def _on_candle(self, st: _State, k: Kline) -> Signal | None:
        p = self.params
        high, low, close = float(k.high), float(k.low), float(k.close)
        trend = st.ema.update(close)
        atr = st.atr.update(high, low, close)
        full = len(st.highs) == p.channel
        channel_high = max(st.highs) if full else None
        channel_low = min(st.lows) if full else None
        st.highs.append(high)
        st.lows.append(low)
        if channel_high is None or channel_low is None or trend is None or atr is None:
            return None

        if close > channel_high and close > trend:
            side = Side.BUY
        elif close < channel_low and close < trend:
            side = Side.SELL
        else:
            return None
        risk = p.atr_mult * atr
        if risk <= 0:
            return self._count(st, "rejected_zero_atr")
        long = side is Side.BUY
        stop = close - risk if long else close + risk
        target = close + p.target_r * risk if long else close - p.target_r * risk
        if stop <= 0 or target <= 0:
            return self._count(st, "rejected_levels")
        now = self._clock.now_ms()
        self._count(st, "signals")
        level = channel_high if long else channel_low
        return Signal(
            symbol=st.symbol,
            side=side,
            strategy=StrategyType.TREND_BREAKOUT,
            reference_price=_dec(close),
            stop_loss=_dec(stop),
            take_profit=_dec(target),
            created_at=now,
            reason=(f"{p.interval} close {'above' if long else 'below'} {p.channel}-bar "
                    f"{'high' if long else 'low'} with trend (EMA{p.trend_ema})"),
            confidence=None,
            expires_at=now + p.interval.ms,
            features={
                "channel_level": level,
                "ema": trend,
                "atr": atr,
                "risk_bps": risk / close * 10_000,
                "breakout_bps": abs(close - level) / close * 10_000,
                "reward_risk": p.target_r,
            },
        )  # fmt: skip

    @staticmethod
    def _count(st: _State, key: str) -> None:
        st.stats[key] = st.stats.get(key, 0) + 1


def _dec(x: float) -> Decimal:
    return Decimal(repr(x))

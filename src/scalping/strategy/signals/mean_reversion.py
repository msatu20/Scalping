"""MEAN_REVERSION signal: RSI + Bollinger Bands with re-entry confirmation.

Long (short is symmetric):

1. **Setup** on a closed candle: ``close < lower band`` and ``RSI <= rsi_oversold``.
   While armed, the extreme (lowest low / trade price) and the most extreme RSI are tracked.
   Another qualifying close re-arms (resets the bar counter); after ``max_setup_bars``
   closed candles without a trigger the setup is dropped.
2. **Trigger** when price re-enters the band (``price > lower``):
   - ``TriggerMode.CLOSE``: evaluated on closed candles with committed indicators.
   - ``TriggerMode.TICK``: evaluated on every aggTrade with ``peek()`` (hypothetical
     candle close at the trade price); at most one signal per candle.
3. **Levels**: take profit = middle band (the mean); stop loss = setup extreme minus
   ``sl_buffer_bps``, widened to at least ``min_stop_bps`` from the entry (stops tighter
   than a few round-trip costs make fees dominate, K8). Rejected unless the target clears
   ``min_target_bps`` (fees, K8) and reward/risk >= ``min_reward_risk``.
   Optional regime filter: skip when the trend is strong, i.e.
   ``|EMA(trend_fast) - EMA(trend_slow)| / price > max_trend_bps``.
4. **Output**: ``Signal`` with ``created_at`` from the injected clock, ``expires_at =
   created_at + expiry_ms``, ``confidence`` in [0, 1] (heuristic: half RSI extremity,
   half band penetration) and the indicator ``features``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from scalping.core.clock import Clock
from scalping.core.models import (
    AggregatedTrade,
    Kline,
    KlineInterval,
    MarketEvent,
    Side,
    Signal,
    StrategyType,
)
from scalping.strategy.indicators import EMA, RSI, BollingerBands, BollingerValue
from scalping.strategy.signals.base import SignalHandler

# RSI points beyond the threshold that count as "maximally extreme" for confidence.
_RSI_SCORE_SPAN = 15.0


class TriggerMode(StrEnum):
    CLOSE = "close"
    TICK = "tick"


@dataclass(frozen=True, slots=True)
class MeanReversionParams:
    interval: KlineInterval = KlineInterval.M1
    rsi_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    max_setup_bars: int = 5
    sl_buffer_bps: float = 5.0
    min_target_bps: float = 12.0  # > taker round trip (10 bps, ADR-0003)
    min_reward_risk: float = 1.0
    expiry_ms: int = 60_000
    trigger: TriggerMode = TriggerMode.CLOSE
    min_stop_bps: float = 0.0  # 0 = structural stop only
    max_trend_bps: float | None = None  # None = no regime filter
    trend_fast: int = 50
    trend_slow: int = 200

    def __post_init__(self) -> None:
        if not 0 < self.rsi_oversold < 50 < self.rsi_overbought < 100:
            raise ValueError("require 0 < rsi_oversold < 50 < rsi_overbought < 100")
        if self.max_setup_bars < 1 or self.expiry_ms <= 0:
            raise ValueError("max_setup_bars and expiry_ms must be positive")
        if self.sl_buffer_bps < 0 or self.min_target_bps < 0 or self.min_reward_risk < 0:
            raise ValueError("buffers and filters must be >= 0")
        if self.min_stop_bps < 0 or (self.max_trend_bps is not None and self.max_trend_bps <= 0):
            raise ValueError("min_stop_bps must be >= 0 and max_trend_bps > 0")
        if not 0 < self.trend_fast < self.trend_slow:
            raise ValueError("require 0 < trend_fast < trend_slow")


@dataclass(slots=True)
class _Setup:
    side: Side
    extreme_price: float  # lowest low (long) / highest high (short)
    extreme_rsi: float
    bars: int = 0


@dataclass(slots=True)
class _SymbolState:
    symbol: str
    rsi: RSI
    bands: BollingerBands
    ema_fast: EMA
    ema_slow: EMA
    setup: _Setup | None = None
    last_rsi: float | None = None
    last_bands: BollingerValue | None = None
    signalled_candle: int | None = None  # open_time of the candle that already signalled
    stats: dict[str, int] = field(default_factory=dict)


class MeanReversionStrategy:
    def __init__(
        self,
        symbols: Sequence[str],
        clock: Clock,
        params: MeanReversionParams | None = None,
        on_signal: SignalHandler | None = None,
    ) -> None:
        self.params = params or MeanReversionParams()
        self._clock = clock
        self._on_signal = on_signal
        self._interval_ms = self.params.interval.ms
        self._states = {
            s: _SymbolState(
                s,
                RSI(self.params.rsi_period),
                BollingerBands(self.params.bb_period, self.params.bb_std),
                EMA(self.params.trend_fast),
                EMA(self.params.trend_slow),
            )
            for s in symbols
        }

    def on_event(self, event: MarketEvent) -> Signal | None:
        state = self._states.get(event.symbol)
        if state is None:
            return None
        signal: Signal | None = None
        if isinstance(event, Kline):
            if event.is_closed and event.interval is self.params.interval:
                signal = self._on_closed_kline(state, event)
        elif isinstance(event, AggregatedTrade) and self.params.trigger is TriggerMode.TICK:
            signal = self._on_trade(state, event)
        if signal is not None and self._on_signal is not None:
            self._on_signal(signal)
        return signal

    def setup_side(self, symbol: str) -> Side | None:
        setup = self._states[symbol].setup
        return setup.side if setup else None

    # ------------------------------------------------------------------ closed candles

    def _on_closed_kline(self, st: _SymbolState, k: Kline) -> Signal | None:
        close, low, high = float(k.close), float(k.low), float(k.high)
        rsi = st.rsi.update(close)
        bands = st.bands.update(close)
        st.ema_fast.update(close)
        st.ema_slow.update(close)
        st.last_rsi, st.last_bands = rsi, bands
        if rsi is None or bands is None:
            return None

        signal = None
        if st.setup is not None and self.params.trigger is TriggerMode.CLOSE:
            signal = self._try_trigger(st, close, rsi, bands, k.open_time)
        if signal is None:
            self._update_setup(st, close, low, high, rsi, bands)
        return signal

    def _update_setup(
        self,
        st: _SymbolState,
        close: float,
        low: float,
        high: float,
        rsi: float,
        bands: BollingerValue,
    ) -> None:
        p = self.params
        if close < bands.lower and rsi <= p.rsi_oversold:
            if st.setup is None or st.setup.side is not Side.BUY:
                st.setup = _Setup(Side.BUY, low, rsi)
            else:
                st.setup.extreme_price = min(st.setup.extreme_price, low)
                st.setup.extreme_rsi = min(st.setup.extreme_rsi, rsi)
                st.setup.bars = 0
        elif close > bands.upper and rsi >= p.rsi_overbought:
            if st.setup is None or st.setup.side is not Side.SELL:
                st.setup = _Setup(Side.SELL, high, rsi)
            else:
                st.setup.extreme_price = max(st.setup.extreme_price, high)
                st.setup.extreme_rsi = max(st.setup.extreme_rsi, rsi)
                st.setup.bars = 0
        elif st.setup is not None:
            if st.setup.side is Side.BUY:
                st.setup.extreme_price = min(st.setup.extreme_price, low)
            else:
                st.setup.extreme_price = max(st.setup.extreme_price, high)
            st.setup.bars += 1
            if st.setup.bars >= p.max_setup_bars:
                st.setup = None

    # ------------------------------------------------------------------ ticks

    def _on_trade(self, st: _SymbolState, t: AggregatedTrade) -> Signal | None:
        if st.setup is None or not st.bands.ready:
            return None
        price = float(t.price)
        candle = t.trade_time - t.trade_time % self._interval_ms
        if st.signalled_candle == candle:
            return None
        if st.setup.side is Side.BUY:
            st.setup.extreme_price = min(st.setup.extreme_price, price)
        else:
            st.setup.extreme_price = max(st.setup.extreme_price, price)
        rsi, bands = st.rsi.peek(price), st.bands.peek(price)
        if rsi is None or bands is None:
            return None
        return self._try_trigger(st, price, rsi, bands, candle)

    # ------------------------------------------------------------------ trigger

    def _try_trigger(
        self, st: _SymbolState, price: float, rsi: float, bands: BollingerValue, candle: int
    ) -> Signal | None:
        setup = st.setup
        assert setup is not None
        p = self.params
        buffer = p.sl_buffer_bps / 10_000
        if setup.side is Side.BUY:
            if price <= bands.lower:
                return None
            target, stop = bands.middle, setup.extreme_price * (1 - buffer)
            reward, risk = target - price, price - stop
            rsi_score = (p.rsi_oversold - setup.extreme_rsi) / _RSI_SCORE_SPAN
            half_width = bands.middle - bands.lower
            penetration = (bands.lower - setup.extreme_price) / half_width if half_width else 0.0
        else:
            if price >= bands.upper:
                return None
            target, stop = bands.middle, setup.extreme_price * (1 + buffer)
            reward, risk = price - target, stop - price
            rsi_score = (setup.extreme_rsi - p.rsi_overbought) / _RSI_SCORE_SPAN
            half_width = bands.upper - bands.middle
            penetration = (setup.extreme_price - bands.upper) / half_width if half_width else 0.0

        min_stop = price * p.min_stop_bps / 10_000
        if risk < min_stop:
            stop = price - min_stop if setup.side is Side.BUY else price + min_stop
            risk = min_stop

        if reward <= 0 or risk <= 0:
            return self._reject(st, "levels")
        if p.max_trend_bps is not None:
            fast, slow = st.ema_fast.value, st.ema_slow.value
            if fast is None or slow is None:
                return self._reject(st, "trend_warmup")
            if abs(fast - slow) / price * 10_000 > p.max_trend_bps:
                return self._reject(st, "trend")
        if reward / price * 10_000 < p.min_target_bps:
            return self._reject(st, "target_below_fees")
        if reward / risk < p.min_reward_risk:
            return self._reject(st, "reward_risk")

        now = self._clock.now_ms()
        confidence = round((_clip01(rsi_score) + _clip01(penetration)) / 2, 4)
        signal = Signal(
            symbol=st.symbol,
            side=setup.side,
            strategy=StrategyType.MEAN_REVERSION,
            reference_price=_dec(price),
            stop_loss=_dec(stop),
            take_profit=_dec(target),
            created_at=now,
            reason=(
                f"{'oversold' if setup.side is Side.BUY else 'overbought'} band re-entry "
                f"({p.trigger}), extreme RSI {setup.extreme_rsi:.1f}"
            ),
            confidence=confidence,
            expires_at=now + p.expiry_ms,
            features={
                "rsi": rsi,
                "extreme_rsi": setup.extreme_rsi,
                "bb_lower": bands.lower,
                "bb_middle": bands.middle,
                "bb_upper": bands.upper,
                "bandwidth": bands.bandwidth,
                "percent_b": bands.percent_b(price),
                "reward_risk": reward / risk,
                "target_bps": reward / price * 10_000,
                "setup_bars": float(setup.bars),
            },
        )
        st.setup = None
        st.signalled_candle = candle
        st.stats["signals"] = st.stats.get("signals", 0) + 1
        return signal

    def _reject(self, st: _SymbolState, reason: str) -> Signal | None:
        # The setup stays armed: a later price may still produce valid levels.
        key = f"rejected_{reason}"
        st.stats[key] = st.stats.get(key, 0) + 1
        return None

    def stats(self, symbol: str) -> dict[str, int]:
        return dict(self._states[symbol].stats)


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, x))


def _dec(x: float) -> Decimal:
    # Exchange tick rounding happens in execution (exchangeInfo filters), not here.
    return Decimal(repr(x))

"""STOP_HUNT_REBOUND: liquidity sweep + aggressive burst + fast reclaim (order flow).

Hypothesis (T18, ADR-0009): a sweep beyond a recent swing extreme, driven by a burst of
aggressive flow in the sweep direction and quickly reclaimed, marks stop-run exhaustion;
price tends to revert into the prior range.

Long setup (short is symmetric):

1. **Level** = lowest low of the last ``lookback_min`` closed 1m candles (fixed when the
   sweep starts).
2. **Sweep** starts when a trade prints below ``level * (1 - sweep_bps)``. Only one sweep at
   a time per symbol; a new one needs price back at/above the level first (re-arm).
3. **Burst**: at some point during the sweep, aggressive selling in the last
   ``burst_window_s`` >= ``burst_k`` x its average per window over ``baseline_s``.
4. **Breakdown filter**: if the sweep extends beyond ``max_depth_bps`` it is a breakdown,
   not a hunt -> dropped.
5. **Reclaim** within ``reclaim_s`` of the sweep start: a trade above
   ``level * (1 + reclaim_bps)`` -> BUY at that trade price (tick-level signal).
6. **Levels**: stop = sweep extreme - ``sl_buffer_bps``, widened to >= ``min_stop_bps``;
   target = entry + ``target_r`` x risk. Cool-down of ``cooldown_s`` per side.

Time comes only from the injected clock; candles only from closed 1m klines.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

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
from scalping.strategy.orderflow import AggressionTracker
from scalping.strategy.signals.base import SignalHandler


@dataclass(frozen=True, slots=True)
class StopHuntParams:
    lookback_min: int = 30
    burst_window_s: int = 10
    baseline_s: int = 3600
    burst_k: float = 4.0
    sweep_bps: float = 3.0
    reclaim_bps: float = 1.0
    reclaim_s: int = 60
    max_depth_bps: float = 100.0
    sl_buffer_bps: float = 5.0
    min_stop_bps: float = 25.0
    target_r: float = 1.5
    min_target_bps: float = 12.0
    cooldown_s: int = 300
    expiry_ms: int = 30_000

    def __post_init__(self) -> None:
        if self.lookback_min < 2 or self.reclaim_s <= 0 or self.expiry_ms <= 0:
            raise ValueError("lookback_min >= 2, reclaim_s > 0 and expiry_ms > 0 required")
        if self.burst_k <= 0 or self.target_r <= 0 or self.max_depth_bps <= self.sweep_bps:
            raise ValueError("burst_k > 0, target_r > 0 and max_depth_bps > sweep_bps required")


@dataclass(slots=True)
class _Sweep:
    side: Side  # side of the trade we would take (BUY after a downside sweep)
    level: float
    start_ms: int
    extreme: float
    burst_ratio: float  # max ratio seen during the sweep


@dataclass(slots=True)
class _State:
    symbol: str
    lows: deque[float]
    highs: deque[float]
    flow: AggressionTracker
    level_low: float | None = None
    level_high: float | None = None
    sweep: _Sweep | None = None
    armed_low: bool = True
    armed_high: bool = True
    cooldown_until: dict[Side, int] = field(default_factory=lambda: {Side.BUY: 0, Side.SELL: 0})
    stats: dict[str, int] = field(default_factory=dict)


class StopHuntReboundStrategy:
    def __init__(
        self,
        symbols: Sequence[str],
        clock: Clock,
        params: StopHuntParams | None = None,
        on_signal: SignalHandler | None = None,
    ) -> None:
        self.params = p = params or StopHuntParams()
        self._clock = clock
        self._on_signal = on_signal
        self._states = {
            s: _State(s, deque(maxlen=p.lookback_min), deque(maxlen=p.lookback_min),
                      AggressionTracker(p.burst_window_s, p.baseline_s))
            for s in symbols
        }  # fmt: skip

    def stats(self, symbol: str) -> dict[str, int]:
        return dict(self._states[symbol].stats)

    def on_event(self, event: MarketEvent) -> Signal | None:
        st = self._states.get(event.symbol)
        if st is None:
            return None
        signal = None
        if isinstance(event, AggregatedTrade):
            signal = self._on_trade(st, event)
        elif isinstance(event, Kline) and event.is_closed and event.interval is KlineInterval.M1:
            st.lows.append(float(event.low))
            st.highs.append(float(event.high))
            if len(st.lows) == self.params.lookback_min:
                st.level_low, st.level_high = min(st.lows), max(st.highs)
        if signal is not None and self._on_signal is not None:
            self._on_signal(signal)
        return signal

    # ------------------------------------------------------------------ trades

    def _on_trade(self, st: _State, t: AggregatedTrade) -> Signal | None:
        p = self.params
        price = float(t.price)
        now = t.trade_time
        st.flow.update(now, price * float(t.qty), t.aggressor_side)
        if st.level_low is None or st.level_high is None or not st.flow.ready:
            return None

        sweep = st.sweep
        if sweep is not None:
            return self._on_sweep_trade(st, sweep, price, now)

        low_trigger = st.level_low * (1 - p.sweep_bps / 10_000)
        high_trigger = st.level_high * (1 + p.sweep_bps / 10_000)
        if price < low_trigger and st.armed_low and now >= st.cooldown_until[Side.BUY]:
            st.sweep = _Sweep(Side.BUY, st.level_low, now, price, st.flow.burst_ratio(Side.SELL))
            st.armed_low = False
            self._count(st, "sweeps")
        elif price > high_trigger and st.armed_high and now >= st.cooldown_until[Side.SELL]:
            st.sweep = _Sweep(Side.SELL, st.level_high, now, price, st.flow.burst_ratio(Side.BUY))
            st.armed_high = False
            self._count(st, "sweeps")
        if price >= st.level_low:
            st.armed_low = True
        if price <= st.level_high:
            st.armed_high = True
        return None

    def _on_sweep_trade(self, st: _State, sw: _Sweep, price: float, now: int) -> Signal | None:
        p = self.params
        if now - sw.start_ms > p.reclaim_s * 1000:
            st.sweep = None
            return self._count(st, "expired")
        long = sw.side is Side.BUY
        sw.extreme = min(sw.extreme, price) if long else max(sw.extreme, price)
        if abs(sw.extreme - sw.level) / sw.level * 10_000 > p.max_depth_bps:
            st.sweep = None
            return self._count(st, "breakdown")
        aggressor = Side.SELL if long else Side.BUY
        sw.burst_ratio = max(sw.burst_ratio, st.flow.burst_ratio(aggressor))
        reclaim = sw.level * (1 + p.reclaim_bps / 10_000 if long else 1 - p.reclaim_bps / 10_000)
        if (long and price <= reclaim) or (not long and price >= reclaim):
            return None
        st.sweep = None
        if sw.burst_ratio < p.burst_k:
            return self._count(st, "reclaimed_without_burst")
        return self._emit(st, sw, price, now)

    def _emit(self, st: _State, sw: _Sweep, price: float, now: int) -> Signal | None:
        p = self.params
        long = sw.side is Side.BUY
        buffer = p.sl_buffer_bps / 10_000
        stop = sw.extreme * (1 - buffer) if long else sw.extreme * (1 + buffer)
        min_risk = price * p.min_stop_bps / 10_000
        risk = max(abs(price - stop), min_risk)
        stop = price - risk if long else price + risk
        target = price + p.target_r * risk if long else price - p.target_r * risk
        if p.target_r * risk / price * 10_000 < p.min_target_bps:
            return self._count(st, "rejected_target_below_fees")
        st.cooldown_until[sw.side] = now + p.cooldown_s * 1000
        created = self._clock.now_ms()
        depth_bps = abs(sw.extreme - sw.level) / sw.level * 10_000
        sweep_s = (now - sw.start_ms) / 1000
        self._count(st, "signals")
        return Signal(
            symbol=st.symbol,
            side=sw.side,
            strategy=StrategyType.STOP_HUNT_REBOUND,
            reference_price=_dec(price),
            stop_loss=_dec(stop),
            take_profit=_dec(target),
            created_at=created,
            reason=(f"{'low' if long else 'high'} swept {depth_bps:.1f} bps with "
                    f"{sw.burst_ratio:.1f}x aggression, reclaimed in {sweep_s:.1f}s"),
            confidence=round(min(1.0, sw.burst_ratio / (3 * p.burst_k)), 4),
            expires_at=created + p.expiry_ms,
            features={
                "level": sw.level,
                "extreme": sw.extreme,
                "depth_bps": depth_bps,
                "burst_ratio": sw.burst_ratio,
                "sweep_ms": float(now - sw.start_ms),
                "risk_bps": risk / price * 10_000,
                "reward_risk": p.target_r,
            },
        )  # fmt: skip

    @staticmethod
    def _count(st: _State, key: str) -> None:
        st.stats[key] = st.stats.get(key, 0) + 1


def _dec(x: float) -> Decimal:
    return Decimal(repr(x))

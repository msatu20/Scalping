"""Backtest engine: ReplayFeed -> SimBroker + strategy, with fixed-fractional sizing.

Per event: the broker processes it first (fills/exits for orders submitted *earlier*),
then the strategy sees it and may emit a signal; the resulting order can only be filled
by later events. Time comes from the replay clock.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, Decimal

from scalping.backtest.funding import FundingSchedule
from scalping.backtest.metrics import BacktestMetrics, compute_metrics
from scalping.backtest.replay import ReplayFeed
from scalping.backtest.sim_broker import ClosedTrade, CostModel, PriceSource, SimBroker
from scalping.backtest.store import HistoricalStore
from scalping.core.clock import Clock
from scalping.core.models import (
    ExecutionStyle,
    KlineInterval,
    MarketEvent,
    OrderIntent,
    Side,
    Signal,
)
from scalping.strategy.signals.base import SignalGenerator, SignalHandler

type StrategyFactory = Callable[[Clock, SignalHandler], SignalGenerator]


@dataclass(frozen=True, slots=True)
class SizingParams:
    initial_equity: Decimal = Decimal("10000")
    risk_per_trade: Decimal = Decimal("0.005")  # 0.5 % of equity lost if the stop is hit
    max_leverage: int = 3
    qty_step: Decimal = Decimal("0.001")  # BTCUSDT/ETHUSDT stepSize; real filters: T15
    compounding: bool = True  # False: size from initial equity (research in R units)


def position_size(
    signal: Signal, entry_price: Decimal, equity: Decimal, p: SizingParams
) -> Decimal:
    """Fixed fractional: risk / stop distance, capped by leverage, rounded down to step."""
    stop_distance = abs(entry_price - signal.stop_loss)
    if stop_distance == 0 or equity <= 0:
        return Decimal(0)
    qty = min(equity * p.risk_per_trade / stop_distance, equity * p.max_leverage / entry_price)
    return qty.quantize(p.qty_step, rounding=ROUND_DOWN)


@dataclass(slots=True)
class BacktestResult:
    metrics: BacktestMetrics
    trades: list[ClosedTrade]
    signals: list[Signal]
    broker_stats: dict[str, int]
    events: int
    skipped: dict[str, int] = field(default_factory=dict)


def _between(a: Decimal, x: Decimal, b: Decimal) -> bool:
    return min(a, b) < x < max(a, b)


def _interval_order(interval: KlineInterval) -> int:
    return list(KlineInterval).index(interval)


class Backtester:
    def __init__(
        self,
        store: HistoricalStore,
        symbols: Sequence[str],
        start: date,
        end: date,
        strategy_factory: StrategyFactory,
        *,
        costs: CostModel | None = None,
        sizing: SizingParams | None = None,
        price_source: PriceSource = PriceSource.KLINES,
        entry_style: ExecutionStyle = ExecutionStyle.TAKER,
        funding: Mapping[str, FundingSchedule] | None = None,
        strategy_interval: KlineInterval = KlineInterval.M1,
        maker_offset_bps: Decimal = Decimal(0),
    ) -> None:
        self._store = store
        self._symbols = list(symbols)
        self._start, self._end = start, end
        self._factory = strategy_factory
        self._costs = costs or CostModel()
        self._sizing = sizing or SizingParams()
        self._price_source = price_source
        self._entry_style = entry_style
        self._funding = funding
        self._strategy_interval = strategy_interval
        self._maker_offset = maker_offset_bps / Decimal(10_000)

    def run(self) -> BacktestResult:
        feed = ReplayFeed(
            self._store, self._symbols, self._start, self._end,
            agg_trades=self._price_source is PriceSource.TRADES,
            # 1m always feeds the broker's price path; the strategy may use a coarser one.
            intervals=sorted({KlineInterval.M1, self._strategy_interval}, key=_interval_order),
        )  # fmt: skip
        broker = SimBroker(self._costs, self._price_source, self._funding,
                           self._sizing.initial_equity)  # fmt: skip
        signals: list[Signal] = []
        skipped: dict[str, int] = {}

        def skip(reason: str) -> None:
            skipped[reason] = skipped.get(reason, 0) + 1

        def on_signal(signal: Signal) -> None:
            signals.append(signal)
            if broker.is_busy(signal.symbol):
                return skip("busy")
            entry = self._entry_price(signal)
            if not _between(signal.stop_loss, entry, signal.take_profit):
                return skip("entry_outside_brackets")  # maker offset beyond a tight stop
            equity = broker.equity if self._sizing.compounding else self._sizing.initial_equity
            qty = position_size(signal, entry, equity, self._sizing)
            if qty <= 0:
                return skip("size_zero")
            intent = OrderIntent.from_signal(
                signal,
                quantity=qty,
                execution=self._entry_style,
                created_at=feed.clock.now_ms(),
                entry_price=entry,
            )
            broker.submit(intent, feed.clock.now_ms(), expires_at=signal.expires_at)
            return None

        strategy = self._factory(feed.clock, on_signal)

        def on_event(event: MarketEvent) -> None:
            broker.on_event(event)
            strategy.on_event(event)

        events = feed.replay(on_event)
        broker.close_all(feed.clock.now_ms())
        return BacktestResult(
            metrics=compute_metrics(broker.trades, self._sizing.initial_equity),
            trades=broker.trades,
            signals=signals,
            broker_stats=dict(broker.stats),
            events=events,
            skipped=skipped,
        )

    def _entry_price(self, signal: Signal) -> Decimal:
        """Taker: the signal price. Maker: a limit ``maker_offset_bps`` better than it."""
        if self._entry_style is ExecutionStyle.TAKER or not self._maker_offset:
            return signal.reference_price
        sign = -1 if signal.side is Side.BUY else 1
        return signal.reference_price * (1 + sign * self._maker_offset)

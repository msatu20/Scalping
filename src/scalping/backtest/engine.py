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


@dataclass(frozen=True, slots=True)
class RunSpec:
    """One strategy + broker configuration evaluated during a shared replay pass."""

    name: str
    strategy_factory: StrategyFactory
    costs: CostModel = field(default_factory=CostModel)
    sizing: SizingParams = field(default_factory=SizingParams)
    entry_style: ExecutionStyle = ExecutionStyle.TAKER
    maker_offset_bps: Decimal = Decimal(0)


class _Run:
    """Per-spec state: its own SimBroker, strategy, signals and skip counters."""

    def __init__(
        self,
        spec: RunSpec,
        clock: Clock,
        price_source: PriceSource,
        funding: Mapping[str, FundingSchedule] | None,
    ) -> None:
        self.spec = spec
        self._clock = clock
        self._maker_offset = spec.maker_offset_bps / Decimal(10_000)
        self.broker = SimBroker(spec.costs, price_source, funding, spec.sizing.initial_equity)
        self.signals: list[Signal] = []
        self.skipped: dict[str, int] = {}
        self.strategy = spec.strategy_factory(clock, self._on_signal)

    def _skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def _on_signal(self, signal: Signal) -> None:
        self.signals.append(signal)
        broker, sizing = self.broker, self.spec.sizing
        if broker.is_busy(signal.symbol):
            return self._skip("busy")
        entry = self._entry_price(signal)
        if not _between(signal.stop_loss, entry, signal.take_profit):
            return self._skip("entry_outside_brackets")  # maker offset beyond a tight stop
        equity = broker.equity if sizing.compounding else sizing.initial_equity
        qty = position_size(signal, entry, equity, sizing)
        if qty <= 0:
            return self._skip("size_zero")
        now = self._clock.now_ms()
        intent = OrderIntent.from_signal(
            signal, quantity=qty, execution=self.spec.entry_style, created_at=now,
            entry_price=entry,
        )  # fmt: skip
        broker.submit(intent, now, expires_at=signal.expires_at)
        return None

    def _entry_price(self, signal: Signal) -> Decimal:
        """Taker: the signal price. Maker: a limit ``maker_offset_bps`` better than it."""
        if self.spec.entry_style is ExecutionStyle.TAKER or not self._maker_offset:
            return signal.reference_price
        sign = -1 if signal.side is Side.BUY else 1
        return signal.reference_price * (1 + sign * self._maker_offset)

    def on_event(self, event: MarketEvent) -> None:
        self.broker.on_event(event)  # fills for orders submitted by earlier events
        self.strategy.on_event(event)

    def result(self, events: int) -> BacktestResult:
        return BacktestResult(
            metrics=compute_metrics(self.broker.trades, self.spec.sizing.initial_equity),
            trades=self.broker.trades,
            signals=self.signals,
            broker_stats=dict(self.broker.stats),
            events=events,
            skipped=self.skipped,
        )


def run_many(
    store: HistoricalStore,
    symbols: Sequence[str],
    start: date,
    end: date,
    specs: Sequence[RunSpec],
    *,
    price_source: PriceSource = PriceSource.KLINES,
    funding: Mapping[str, FundingSchedule] | None = None,
    strategy_interval: KlineInterval = KlineInterval.M1,
) -> dict[str, BacktestResult]:
    """Replay once and evaluate every spec on the same event stream (events built once).

    Each spec is fully independent (own broker, strategy, signals); only the immutable
    events and the replay clock are shared.
    """
    if len({s.name for s in specs}) != len(specs):
        raise ValueError("RunSpec names must be unique")
    feed = ReplayFeed(
        store, symbols, start, end,
        agg_trades=price_source is PriceSource.TRADES,
        # 1m always feeds the broker's price path; the strategy may use a coarser one.
        intervals=sorted({KlineInterval.M1, strategy_interval}, key=_interval_order),
    )  # fmt: skip
    runs = [_Run(spec, feed.clock, price_source, funding) for spec in specs]

    def on_event(event: MarketEvent) -> None:
        for run in runs:
            run.on_event(event)

    events = feed.replay(on_event)
    for run in runs:
        run.broker.close_all(feed.clock.now_ms())
    return {run.spec.name: run.result(events) for run in runs}


class Backtester:
    """Single-spec convenience wrapper around :func:`run_many`."""

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
        self._spec = RunSpec(
            "backtest", strategy_factory, costs or CostModel(), sizing or SizingParams(),
            entry_style, maker_offset_bps,
        )  # fmt: skip
        self._price_source = price_source
        self._funding = funding
        self._strategy_interval = strategy_interval

    def run(self) -> BacktestResult:
        results = run_many(
            self._store, self._symbols, self._start, self._end, [self._spec],
            price_source=self._price_source, funding=self._funding,
            strategy_interval=self._strategy_interval,
        )  # fmt: skip
        return results["backtest"]

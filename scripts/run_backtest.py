"""Backtest MEAN_REVERSION with the replay engine + SimBroker (T13).

    .venv/Scripts/python.exe scripts/run_backtest.py --start 2026-07-16 --end 2026-10-12
    .venv/Scripts/python.exe scripts/run_backtest.py --start 2026-10-11 --end 2026-10-12 \
        --price-source trades --trigger tick

Costs: maker/taker fees from settings (0.02 % / 0.05 %), taker slippage (--slippage-bps),
funding from data/futures_um/fundingRate (download_history.py --funding).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from decimal import Decimal

from scalping.backtest import (
    Backtester,
    BacktestResult,
    CostModel,
    FundingSchedule,
    HistoricalStore,
    PriceSource,
    SizingParams,
    TpStyle,
    compute_metrics,
)
from scalping.config import Settings
from scalping.core import Clock, ExecutionStyle
from scalping.strategy.signals import (
    MeanReversionParams,
    MeanReversionStrategy,
    SignalHandler,
    TriggerMode,
)


def report(title: str, result: BacktestResult, initial: Decimal) -> None:
    m = result.metrics
    print(f"\n== {title}")
    print(f"   signals {len(result.signals)} | trades {m.trades} | skipped {result.skipped} "
          f"| exits {m.exit_reasons}")  # fmt: skip
    if not m.trades:
        return
    hold = f"{m.avg_hold_minutes:.1f} min"
    print(f"   win rate {m.win_rate:.1%} | expectancy {m.expectancy_r:+.3f} R "
          f"| profit factor {m.profit_factor:.2f} | avg hold {hold}")  # fmt: skip
    print(f"   gross {m.gross_pnl:+.2f} | fees -{m.fees:.2f} | funding {m.funding:+.2f} "
          f"| NET {m.net_pnl:+.2f} USDT ({m.return_pct:+.2%} on {initial})")  # fmt: skip
    print(f"   max drawdown {m.max_drawdown:.2f} ({m.max_drawdown_pct:.2%}) "
          f"| fees / |gross| {m.fee_to_gross_ratio:.1f}x")  # fmt: skip


def main(args: argparse.Namespace) -> int:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    store = HistoricalStore(args.data_dir)
    costs = CostModel.from_settings(
        settings, taker_slippage_bps=Decimal(str(args.slippage_bps)), tp_style=TpStyle(args.tp)
    )
    sizing = SizingParams(
        risk_per_trade=Decimal(str(args.risk)), max_leverage=settings.max_leverage
    )
    params = MeanReversionParams(trigger=TriggerMode(args.trigger))
    funding = {s: FundingSchedule.load(store, s) for s in args.symbols}

    def factory(clock: Clock, on_signal: SignalHandler) -> MeanReversionStrategy:
        return MeanReversionStrategy(args.symbols, clock, params, on_signal)

    result = Backtester(
        store, args.symbols, args.start, args.end, factory, costs=costs, sizing=sizing,
        price_source=PriceSource(args.price_source), entry_style=ExecutionStyle(args.entry),
        funding=funding,
    ).run()  # fmt: skip

    print(f"{args.start}..{args.end} | {result.events:,} events | price source {args.price_source}"
          f" | entry {args.entry} | TP {args.tp} | trigger {args.trigger}")  # fmt: skip
    print(f"costs: maker {costs.maker_fee} taker {costs.taker_fee} slippage "
          f"{costs.taker_slippage_bps} bps | risk/trade {sizing.risk_per_trade} "
          f"| broker {result.broker_stats}")  # fmt: skip
    for symbol in args.symbols:
        mine = [t for t in result.trades if t.symbol == symbol]
        sub = BacktestResult(
            compute_metrics(mine, sizing.initial_equity), mine,
            [s for s in result.signals if s.symbol == symbol], {}, 0,
        )  # fmt: skip
        report(symbol, sub, sizing.initial_equity)
    report("TOTAL (shared equity)", result, sizing.initial_equity)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--symbols", nargs="+", type=str.upper, default=["BTCUSDT", "ETHUSDT"])
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--price-source", choices=[p.value for p in PriceSource], default="klines")
    parser.add_argument("--entry", choices=[e.value for e in ExecutionStyle], default="TAKER")
    parser.add_argument("--tp", choices=[t.value for t in TpStyle], default="maker_limit")
    parser.add_argument("--trigger", choices=[m.value for m in TriggerMode], default="close")
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--risk", type=float, default=0.005)
    parser.add_argument("--data-dir", default="data")
    sys.exit(main(parser.parse_args()))

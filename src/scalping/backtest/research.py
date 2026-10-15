"""Shared helpers for walk-forward research reports (ADR-0008)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from scalping.backtest.walk_forward import Stats, TradeRecord, WalkForwardResult

CONTROL_SUFFIX = "#nocost"
STATS_HEADER = "trades | mean R | total R | win | PF | max DD (R) | t"


def fmt_stats(s: Stats) -> str:
    pf = "inf" if s.profit_factor == float("inf") else f"{s.profit_factor:.2f}"
    return (
        f"{s.trades} | {s.mean_r:+.3f} | {s.total_r:+.1f} | {s.win_rate:.1%} | {pf} | "
        f"{s.max_drawdown_r:.1f} | {s.t_stat:+.2f}"
    )


def split_controls(
    trades: Mapping[str, Sequence[TradeRecord]],
) -> tuple[dict[str, list[TradeRecord]], dict[str, list[TradeRecord]]]:
    real = {
        n: sorted(v, key=lambda r: r.entry_time)
        for n, v in trades.items()
        if not n.endswith(CONTROL_SUFFIX)
    }
    control = {
        n.removesuffix(CONTROL_SUFFIX): sorted(v, key=lambda r: r.entry_time)
        for n, v in trades.items()
        if n.endswith(CONTROL_SUFFIX)
    }
    return real, control


def breakdown(records: Sequence[TradeRecord], key: str) -> dict[str, Stats]:
    """Stats grouped by ``symbol`` or entry ``year``."""
    groups: dict[str, list[TradeRecord]] = {}
    for r in records:
        k = (
            r.symbol
            if key == "symbol"
            else str(datetime.fromtimestamp(r.entry_time / 1000, UTC).year)
        )
        groups.setdefault(k, []).append(r)
    return {k: Stats.of(v) for k, v in sorted(groups.items())}


def walk_forward_report(
    title: str,
    meta: Sequence[str],
    trades: Mapping[str, Sequence[TradeRecord]],
    wf: WalkForwardResult,
) -> str:
    real, control = split_controls(trades)
    if not real:
        return f"# {title}\n\nSin resultados.\n"
    full = {n: Stats.of(v) for n, v in real.items()}
    best = max(full, key=lambda n: (full[n].mean_r, full[n].trades))
    lines = [
        f"# {title}",
        "",
        *meta,
        "",
        "## Resultado fuera de muestra",
        "",
        f"| | {STATS_HEADER} |",
        f"|---|{'---|' * 7}",
        f"| **OOS walk-forward ({len(wf.folds)} tramos)** | {fmt_stats(wf.oos)} |",
        f"| Mejor a posteriori ({best}, IN-SAMPLE, sesgada) | {fmt_stats(full[best])} |",
    ]
    if best in control:
        lines.append(f"| La misma sin costes (control) | {fmt_stats(Stats.of(control[best]))} |")
    positive = sum(1 for fr in wf.folds if fr.test.trades and fr.test.total_r > 0)
    with_trades = sum(1 for fr in wf.folds if fr.test.trades)
    lines += [
        "",
        f"Tramos de test positivos: **{positive} / {with_trades}** (con operaciones).",
        "",
    ]
    for key, label in (("symbol", "símbolo"), ("year", "año")):
        lines += [f"### OOS por {label}", "", f"| {label} | {STATS_HEADER} |", f"|---|{'---|' * 7}"]
        lines += [f"| {k} | {fmt_stats(s)} |" for k, s in breakdown(wf.oos_records, key).items()]
        lines.append("")
    lines += [
        "## Tramos",
        "",
        "| Test | Variante elegida | Train trades / mean R | Test trades / mean R / total R |",
        "|---|---|---|---|",
    ]
    for fr in wf.folds:
        lines.append(
            f"| {fr.fold.test_start}..{fr.fold.test_end} | {fr.selected or '—'} | "
            f"{fr.train.trades} / {fr.train.mean_r:+.3f} | {fr.test.trades} / "
            f"{fr.test.mean_r:+.3f} / {fr.test.total_r:+.1f} |"
        )
    lines += [
        "",
        "## Variantes, periodo completo (IN-SAMPLE, descriptivo)",
        "",
        f"| Variante | {STATS_HEADER} | sin costes: mean R |",
        f"|---|{'---|' * 8}",
    ]
    for name in sorted(full, key=lambda n: -full[n].mean_r):
        ctrl = f"{Stats.of(control[name]).mean_r:+.3f}" if name in control else "—"
        lines.append(f"| {name} | {fmt_stats(full[name])} | {ctrl} |")
    lines += [
        "",
        "R = PnL neto / riesgo planificado (0,5 % de 10 000 USDT, sin capitalizar). "
        "t = media / error estándar (|t| < 2: no distinguible de 0).",
        "",
    ]
    return "\n".join(lines)

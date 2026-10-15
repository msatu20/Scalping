"""Shared helpers for walk-forward research reports (ADR-0008)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
    criteria: Sequence[Criterion] | None = None,
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
    if criteria:
        lines += ["", *criteria_table(criteria)]
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


@dataclass(frozen=True, slots=True)
class Criterion:
    name: str
    observed: str
    passed: bool


def evaluate_criteria(
    wf: WalkForwardResult,
    min_group_trades: int = 30,
    year_share: float = 0.7,
    worst_year_r: float = -0.10,
    symbol_share: float = 0.6,
) -> list[Criterion]:
    """Pre-registered approval criteria (ADR-0008 + stability/breadth of ADR-0011)."""
    oos = wf.oos
    folds = [fr for fr in wf.folds if fr.test.trades]
    positive_folds = sum(1 for fr in folds if fr.test.total_r > 0)
    years = {
        k: s for k, s in breakdown(wf.oos_records, "year").items() if s.trades >= min_group_trades
    }
    symbols = {
        k: s for k, s in breakdown(wf.oos_records, "symbol").items() if s.trades >= min_group_trades
    }
    pos_years = sum(1 for s in years.values() if s.mean_r > 0)
    pos_symbols = sum(1 for s in symbols.values() if s.mean_r > 0)
    worst = min((s.mean_r for s in years.values()), default=0.0)
    return [
        Criterion("OOS mean R > 0 y t ≥ 2", f"{oos.mean_r:+.3f} R, t {oos.t_stat:+.2f}",
                  oos.mean_r > 0 and oos.t_stat >= 2),
        Criterion("Profit factor ≥ 1,2", f"{oos.profit_factor:.2f}", oos.profit_factor >= 1.2),
        Criterion("≥ 200 trades OOS", str(oos.trades), oos.trades >= 200),
        Criterion("Mayoría de tramos positivos", f"{positive_folds}/{len(folds)}",
                  bool(folds) and positive_folds > len(folds) / 2),
        Criterion(f"Años positivos ≥ {year_share:.0%}", f"{pos_years}/{len(years)}",
                  bool(years) and pos_years / len(years) >= year_share),
        Criterion(f"Ningún año < {worst_year_r:+.2f} R", f"peor {worst:+.3f} R",
                  bool(years) and worst >= worst_year_r),
        Criterion(f"Activos positivos ≥ {symbol_share:.0%}", f"{pos_symbols}/{len(symbols)}",
                  bool(symbols) and pos_symbols / len(symbols) >= symbol_share),
    ]  # fmt: skip


def criteria_table(criteria: Sequence[Criterion]) -> list[str]:
    verdict = "**APROBADA**" if all(c.passed for c in criteria) else "**NO APROBADA**"
    lines = [
        "## Criterios pre-registrados",
        "",
        "| Criterio | Observado | Cumple |",
        "|---|---|---|",
    ]
    lines += [f"| {c.name} | {c.observed} | {'✅' if c.passed else '❌'} |" for c in criteria]
    return [*lines, "", f"Veredicto: {verdict}", ""]


def evaluate_fixed_rule(
    records: Sequence[TradeRecord],
    min_trades: int = 200,
    min_group_trades: int = 30,
    min_pf: float = 1.2,
    year_share: float = 0.7,
    symbol_share: float = 0.6,
) -> list[Criterion]:
    """Pre-registered criteria for a single fixed rule (ADR-0012): no selection, no folds."""
    s = Stats.of(sorted(records, key=lambda r: r.entry_time))

    def big(key: str) -> dict[str, Stats]:
        return {k: v for k, v in breakdown(records, key).items() if v.trades >= min_group_trades}

    years, symbols = big("year"), big("symbol")
    pos_years = sum(1 for v in years.values() if v.mean_r > 0)
    pos_symbols = sum(1 for v in symbols.values() if v.mean_r > 0)
    return [
        Criterion("Mean R > 0 y t ≥ 2", f"{s.mean_r:+.3f} R, t {s.t_stat:+.2f}",
                  s.mean_r > 0 and s.t_stat >= 2),
        Criterion(f"Profit factor ≥ {min_pf:.1f}".replace(".", ","), f"{s.profit_factor:.2f}",
                  s.profit_factor >= min_pf),
        Criterion(f"Años positivos ≥ {year_share:.0%}", f"{pos_years}/{len(years)}",
                  bool(years) and pos_years / len(years) >= year_share),
        Criterion(f"Activos positivos ≥ {symbol_share:.0%}", f"{pos_symbols}/{len(symbols)}",
                  bool(symbols) and pos_symbols / len(symbols) >= symbol_share),
        Criterion(f"≥ {min_trades} trades", str(s.trades), s.trades >= min_trades),
    ]  # fmt: skip


def fixed_rule_report(
    title: str,
    meta: Sequence[str],
    records: Sequence[TradeRecord],
    control: Sequence[TradeRecord],
    criteria: Sequence[Criterion],
) -> str:
    ordered = sorted(records, key=lambda r: r.entry_time)
    control_stats = Stats.of(sorted(control, key=lambda r: r.entry_time))
    lines = [f"# {title}", "", *meta, "", "## Resultado", "",
             f"| | {STATS_HEADER} |", f"|---|{'---|' * 7}",
             f"| **Regla fija (todos los activos)** | {fmt_stats(Stats.of(ordered))} |",
             f"| Control sin costes | {fmt_stats(control_stats)} |",
             "", *criteria_table(criteria)]  # fmt: skip
    for key, label in (("symbol", "activo"), ("year", "año")):
        lines += [f"### Por {label}", "", f"| {label} | {STATS_HEADER} |", f"|---|{'---|' * 7}"]
        lines += [f"| {k} | {fmt_stats(v)} |" for k, v in breakdown(ordered, key).items()]
        lines.append("")
    lines.append("R = PnL neto / riesgo planificado (0,5 % de 10 000 USDT, sin capitalizar).")
    return "\n".join([*lines, ""])

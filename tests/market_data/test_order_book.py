from decimal import Decimal as D

import pytest

from scalping.core import OrderBookDelta, OrderBookSnapshot, PriceLevel
from scalping.market_data import BookNotSyncedError, DeltaResult, LocalOrderBook, SyncState

SYM = "BTCUSDT"
T0 = 1_760_400_000_000

Levels = list[tuple[str, str]]


def lv(levels: Levels) -> tuple[PriceLevel, ...]:
    return tuple(PriceLevel(D(p), D(q)) for p, q in levels)


def delta(
    U: int,
    u: int,
    pu: int | None,
    bids: Levels = (),  # type: ignore[assignment]
    asks: Levels = (),  # type: ignore[assignment]
    latency_ms: int = 5,
) -> OrderBookDelta:
    return OrderBookDelta(SYM, U, u, pu, lv(bids), lv(asks), T0 + u, T0 + u, T0 + u + latency_ms)


def snap(lid: int, bids: Levels, asks: Levels) -> OrderBookSnapshot:
    return OrderBookSnapshot(SYM, lid, lv(bids), lv(asks), T0)


BASE_SNAPSHOT = snap(100, [("100.0", "1"), ("99.9", "2")], [("100.1", "1"), ("100.2", "3")])


def synced_book() -> LocalOrderBook:
    book = LocalOrderBook(SYM)
    assert book.apply_snapshot(BASE_SNAPSHOT)
    assert book.apply_delta(delta(99, 105, pu=98, bids=[("100.0", "1.5")])) is DeltaResult.APPLIED
    return book


def test_buffers_until_snapshot_then_replays_from_bridge() -> None:
    book = LocalOrderBook(SYM)
    assert book.apply_delta(delta(90, 95, pu=89, bids=[("50", "9")])) is DeltaResult.BUFFERED
    assert book.apply_delta(delta(96, 104, pu=95, bids=[("100.0", "4")])) is DeltaResult.BUFFERED
    assert book.apply_delta(delta(105, 110, pu=104, asks=[("100.1", "0")])) is DeltaResult.BUFFERED
    assert book.buffered == 3

    assert book.apply_snapshot(BASE_SNAPSHOT)

    assert book.state is SyncState.SYNCED
    assert book.last_update_id == 110
    assert book.best_bid() == PriceLevel(D("100.0"), D("4"))  # replayed delta
    assert book.best_ask() == PriceLevel(D("100.2"), D("3"))  # qty 0 removed 100.1
    assert D("50") not in {lvl.price for lvl in book.snapshot().bids}  # stale delta dropped
    assert book.buffered == 0


def test_snapshot_older_than_buffer_is_rejected() -> None:
    book = LocalOrderBook(SYM)
    book.apply_delta(delta(150, 160, pu=149))
    assert not book.apply_snapshot(BASE_SNAPSHOT)  # lid=100, first buffered U=150
    assert book.state is SyncState.UNSYNCED and book.buffered == 1

    newer = snap(155, [("100.0", "1")], [("100.1", "1")])
    assert book.apply_snapshot(newer)
    assert book.is_synced and book.last_update_id == 160


def test_snapshot_without_buffer_waits_for_bridge() -> None:
    book = LocalOrderBook(SYM)
    assert book.apply_snapshot(BASE_SNAPSHOT)
    assert book.state is SyncState.AWAITING_BRIDGE
    with pytest.raises(BookNotSyncedError):
        book.best_bid()
    assert book.apply_delta(delta(95, 99, pu=94)) is DeltaResult.STALE
    assert book.apply_delta(delta(101, 103, pu=100)) is DeltaResult.APPLIED
    assert book.is_synced


def test_no_overlapping_delta_after_snapshot_is_a_gap() -> None:
    book = LocalOrderBook(SYM)
    book.apply_snapshot(BASE_SNAPSHOT)
    assert book.apply_delta(delta(102, 103, pu=101)) is DeltaResult.GAP
    assert book.state is SyncState.UNSYNCED and book.gaps == 1


def test_live_sequence_gap_resets_and_buffers() -> None:
    book = synced_book()
    assert book.apply_delta(delta(106, 108, pu=105)) is DeltaResult.APPLIED
    assert book.apply_delta(delta(112, 115, pu=110)) is DeltaResult.GAP  # pu != 108

    assert book.state is SyncState.UNSYNCED
    assert book.gaps == 1 and book.buffered == 1 and book.last_update_id is None
    with pytest.raises(BookNotSyncedError):
        book.snapshot()


def test_duplicate_and_old_deltas_are_stale() -> None:
    book = synced_book()
    assert book.apply_delta(delta(99, 105, pu=98)) is DeltaResult.STALE
    assert book.apply_delta(delta(80, 90, pu=79)) is DeltaResult.STALE
    assert book.is_synced


def test_crossed_book_triggers_resync() -> None:
    book = synced_book()
    assert book.apply_delta(delta(106, 107, pu=105, bids=[("100.5", "1")])) is DeltaResult.GAP
    assert book.state is SyncState.UNSYNCED


def test_gap_during_replay_keeps_remaining_deltas() -> None:
    book = LocalOrderBook(SYM)
    for d in (delta(99, 102, pu=98), delta(110, 112, pu=109), delta(113, 115, pu=112)):
        book.apply_delta(d)
    assert not book.apply_snapshot(BASE_SNAPSHOT)  # 99..102 ok, then pu=109 != 102
    assert book.state is SyncState.UNSYNCED
    assert book.buffered == 2  # gap delta + the one after it


def test_snapshot_and_imbalance_views() -> None:
    book = synced_book()
    view = book.snapshot(levels=1)
    assert view.bids == (PriceLevel(D("100.0"), D("1.5")),)
    assert view.asks == (PriceLevel(D("100.1"), D("1")),)
    assert view.last_update_id == 105

    obi = book.imbalance(levels=2)
    assert (obi.bid_qty, obi.ask_qty) == (D("3.5"), D("4"))
    assert obi.value == pytest.approx(-0.5 / 7.5)


def test_latency_is_tracked() -> None:
    book = synced_book()
    book.apply_delta(delta(106, 107, pu=105, latency_ms=900))
    assert book.last_latency_ms == 900


def test_prune_keeps_levels_closest_to_touch() -> None:
    book = LocalOrderBook(SYM, max_levels_per_side=10)
    book.apply_snapshot(snap(100, [("100.0", "1")], [("100.1", "1")]))
    far_bids = [(str(99 - i), "1") for i in range(12)]
    book.apply_delta(delta(100, 101, pu=99, bids=far_bids))

    bids = book.snapshot().bids
    assert len(bids) == 8  # 13 > 10 -> pruned to 80 %
    assert bids[0].price == D("100.0") and bids[-1].price == D("93")


def test_buffer_is_bounded() -> None:
    book = LocalOrderBook(SYM, max_buffer=3)
    for i in range(5):
        book.apply_delta(delta(10 * i + 1, 10 * i + 10, pu=10 * i))
    assert book.buffered == 3


def test_rejects_other_symbol() -> None:
    other = OrderBookDelta("ETHUSDT", 1, 2, 0, (), (), T0, T0, T0)
    with pytest.raises(ValueError):
        LocalOrderBook(SYM).apply_delta(other)

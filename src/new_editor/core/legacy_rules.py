from __future__ import annotations

import math
from collections.abc import Iterable

from .models import Chart, Note, PendingLongNote


DELETE_TIME_TOLERANCE_MS = 50.0


def round_half_away_from_zero(value: float) -> int:
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def snap_duration_ms(bpm: float, snap_division: int) -> float:
    beat_ms = 60000.0 / bpm if bpm > 0 else 500.0
    safe_division = snap_division or 1
    return beat_ms / (safe_division / 4.0)


def snap_time_to_grid(raw_time_ms: float, bpm: float, snap_division: int) -> float:
    snap_ms = snap_duration_ms(bpm=bpm, snap_division=snap_division)
    snap_ratio = raw_time_ms / snap_ms
    return round_half_away_from_zero(snap_ratio) * snap_ms


def can_place_note(notes: Iterable[Note], lane: int, snapped_time_ms: float) -> bool:
    for note in notes:
        if note.lane != lane:
            continue
        if note.time_ms == snapped_time_ms:
            return False
        if note.end_time_ms is not None and note.time_ms < snapped_time_ms < note.end_time_ms:
            return False
    return True


def make_pending_long_note(snapped_time_ms: float, lane: int, note_type_name: str) -> PendingLongNote:
    return PendingLongNote(time_ms=snapped_time_ms, lane=lane, type_name=note_type_name)


def finalize_long_note(pending: PendingLongNote, snapped_time_ms: float) -> Note:
    start_time = pending.time_ms
    end_time = snapped_time_ms
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    if end_time == start_time:
        return Note(time_ms=start_time, note_type_name=pending.type_name, lane=pending.lane)
    return Note(
        time_ms=start_time,
        note_type_name=pending.type_name,
        lane=pending.lane,
        end_time_ms=end_time,
    )


def find_note_to_delete(
    notes: Iterable[Note],
    lane: int,
    raw_time_ms: float,
    tolerance_ms: float = DELETE_TIME_TOLERANCE_MS,
) -> Note | None:
    reversed_notes = list(notes)
    reversed_notes.reverse()
    for note in reversed_notes:
        if note.lane != lane:
            continue
        if note.end_time_ms is not None:
            if (note.time_ms - tolerance_ms) <= raw_time_ms <= (note.end_time_ms + tolerance_ms):
                return note
            continue
        if abs(note.time_ms - raw_time_ms) < tolerance_ms:
            return note
    return None


def chart_allows_placement(chart: Chart, lane: int, raw_time_ms: float, snap_division: int) -> bool:
    snapped_time_ms = snap_time_to_grid(raw_time_ms, bpm=chart.bpm, snap_division=snap_division)
    return can_place_note(chart.notes, lane=lane, snapped_time_ms=snapped_time_ms)

from __future__ import annotations

from bisect import bisect_right
from pathlib import Path
import sys

from .models import Chart


_SHARED_HITSOUND_RELATIVE_PATH = Path("legacy") / "pygame_editor" / "assets" / "hitsound.wav"


def _hitsound_search_roots() -> tuple[Path, ...]:
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(str(meipass)))
    roots.append(Path(__file__).resolve().parents[3])
    return tuple(roots)


def default_hitsound_path() -> Path:
    candidates: list[Path] = []
    for root in _hitsound_search_roots():
        candidate = root / _SHARED_HITSOUND_RELATIVE_PATH
        candidates.append(candidate)
        if candidate.exists():
            return candidate
    return candidates[-1]


def hitsound_crossings(chart: Chart, previous_note_time_ms: float, current_note_time_ms: float) -> tuple[float, ...]:
    if current_note_time_ms <= previous_note_time_ms:
        return ()

    crossed_times: set[float] = set()
    for note in chart.notes:
        note_type = chart.note_types.get(note.note_type_name)
        if note_type is None or not note_type.play_hitsound:
            continue

        if previous_note_time_ms < note.time_ms <= current_note_time_ms:
            crossed_times.add(note.time_ms)

        if note.end_time_ms is not None and previous_note_time_ms < note.end_time_ms <= current_note_time_ms:
            crossed_times.add(note.end_time_ms)

    return tuple(sorted(crossed_times))


def build_hitsound_event_times(chart: Chart) -> tuple[float, ...]:
    event_times: set[float] = set()
    for note in chart.notes:
        note_type = chart.note_types.get(note.note_type_name)
        if note_type is None or not note_type.play_hitsound:
            continue
        event_times.add(note.time_ms)
        if note.end_time_ms is not None:
            event_times.add(note.end_time_ms)
    return tuple(sorted(event_times))


def has_hitsound_crossing(event_times: tuple[float, ...], previous_note_time_ms: float, current_note_time_ms: float) -> bool:
    if current_note_time_ms <= previous_note_time_ms or not event_times:
        return False
    start_index = bisect_right(event_times, previous_note_time_ms)
    return start_index < len(event_times) and event_times[start_index] <= current_note_time_ms


def hitsound_status_text(*, source_path: str, is_ready: bool, error_message: str | None) -> str:
    if error_message:
        return f"Hitsound preview unavailable: {error_message}"
    if is_ready:
        return f"Hitsound preview ready: {Path(source_path).name}"
    if source_path:
        return f"Hitsound preview loading: {Path(source_path).name}"
    return "Hitsound preview unavailable: no hitsound asset configured."

from __future__ import annotations

from dataclasses import dataclass, replace

from .legacy_rules import (
    can_place_note,
    finalize_long_note,
    find_note_to_delete,
    make_pending_long_note,
    snap_time_to_grid,
)
from .models import Chart, Note, PendingLongNote


DEFAULT_LANE_WIDTH_PIXELS = 60
MIN_SCALE_PIXELS_PER_MS = 0.05
MAX_SCALE_PIXELS_PER_MS = 2.0
DEFAULT_SCALE_PIXELS_PER_MS = 0.5
DEFAULT_JUDGMENT_LINE_RATIO = 0.8
DEFAULT_SNAP_DIVISION = 16
QUICK_EDIT_KEY_PRESETS: dict[int, tuple[tuple[str, ...], ...]] = {
    3: (("d",), ("f",), ("j",)),
    4: (("d",), ("f",), ("j",), ("k",)),
    5: (("s",), ("d",), ("f", "j"), ("k",), ("l",)),
    6: (("s",), ("d",), ("f",), ("j",), ("k",), ("l",)),
    7: (("s",), ("d",), ("f",), ("space", " "), ("j",), ("k",), ("l",)),
}
DEFAULT_QUICK_EDIT_LANE_KEY_PRESET = QUICK_EDIT_KEY_PRESETS[4]


@dataclass(frozen=True, slots=True)
class TimelineGeometry:
    lane_width_pixels: int = DEFAULT_LANE_WIDTH_PIXELS
    scale_pixels_per_ms: float = DEFAULT_SCALE_PIXELS_PER_MS
    judgment_line_ratio: float = DEFAULT_JUDGMENT_LINE_RATIO


@dataclass(frozen=True, slots=True)
class TimelineToolState:
    snap_division: int = DEFAULT_SNAP_DIVISION
    current_note_type_name: str = "Tap"
    quick_edit_enabled: bool = False
    quick_edit_lane_key_preset: tuple[tuple[str, ...], ...] = DEFAULT_QUICK_EDIT_LANE_KEY_PRESET
    pending_long_note: PendingLongNote | None = None
    pending_long_notes: tuple[PendingLongNote, ...] = ()
    active_quick_edit_keys: tuple[str, ...] = ()
    selection_range: TimelineSelectionRange | None = None
    paste_marker_time_ms: float | None = None
    copy_buffer: TimelineCopyBuffer | None = None


@dataclass(frozen=True, slots=True)
class TimelineSelectionRange:
    start_time_ms: float
    end_time_ms: float


@dataclass(frozen=True, slots=True)
class TimelineCopiedNote:
    time_offset_ms: float
    lane: int
    note_type_name: str
    end_time_offset_ms: float | None = None


@dataclass(frozen=True, slots=True)
class TimelineCopyBuffer:
    source_start_time_ms: float
    notes: tuple[TimelineCopiedNote, ...]


@dataclass(frozen=True, slots=True)
class TimelineHit:
    lane: int
    raw_time_ms: float
    snapped_time_ms: float


@dataclass(frozen=True, slots=True)
class TimelineEditOutcome:
    chart_changed: bool
    next_state: TimelineToolState


def clamp_scale_pixels_per_ms(scale_pixels_per_ms: float) -> float:
    return min(MAX_SCALE_PIXELS_PER_MS, max(MIN_SCALE_PIXELS_PER_MS, float(scale_pixels_per_ms)))


def quick_edit_lane_key_preset_for_lane_count(lane_count: int) -> tuple[tuple[str, ...], ...]:
    safe_lane_count = min(7, max(3, int(lane_count)))
    return QUICK_EDIT_KEY_PRESETS[safe_lane_count]


def normalize_quick_edit_key(key: str) -> str:
    normalized_key = key.strip().lower()
    if normalized_key in {"", "spacebar"}:
        return "space" if key == " " else ""
    if normalized_key == " ":
        return "space"
    return normalized_key


def quick_edit_lane_for_key(tool_state: TimelineToolState, key: str) -> int | None:
    normalized_key = normalize_quick_edit_key(key)
    if not normalized_key:
        return None
    for lane, lane_keys in enumerate(tool_state.quick_edit_lane_key_preset):
        if normalized_key in lane_keys:
            return lane
    return None


def pending_long_note_for_lane(pending_long_notes: tuple[PendingLongNote, ...], lane: int) -> PendingLongNote | None:
    for pending_long_note in pending_long_notes:
        if pending_long_note.lane == lane:
            return pending_long_note
    return None


def normalize_selection_range(start_time_ms: float | None, end_time_ms: float | None) -> TimelineSelectionRange | None:
    if start_time_ms is None or end_time_ms is None:
        return None
    normalized_start_time_ms = float(start_time_ms)
    normalized_end_time_ms = float(end_time_ms)
    if normalized_end_time_ms < normalized_start_time_ms:
        normalized_start_time_ms, normalized_end_time_ms = normalized_end_time_ms, normalized_start_time_ms
    return TimelineSelectionRange(
        start_time_ms=normalized_start_time_ms,
        end_time_ms=normalized_end_time_ms,
    )


def snapped_chart_time_ms(chart: Chart, current_audio_time_ms: float, snap_division: int) -> float:
    current_note_time_ms = float(current_audio_time_ms) + chart.offset_ms
    return snap_time_to_grid(current_note_time_ms, bpm=chart.bpm, snap_division=snap_division)


def selected_notes_in_range(chart: Chart, selection_range: TimelineSelectionRange | None) -> tuple[Note, ...]:
    if selection_range is None:
        return ()
    matching_notes = [
        note
        for note in chart.notes
        if selection_range.start_time_ms <= note.time_ms <= selection_range.end_time_ms
    ]
    return tuple(sorted(matching_notes, key=_note_sort_key))


def build_copy_buffer(chart: Chart, selection_range: TimelineSelectionRange | None) -> TimelineCopyBuffer | None:
    if selection_range is None:
        return None
    selected_notes = selected_notes_in_range(chart, selection_range)
    copied_notes = tuple(
        TimelineCopiedNote(
            time_offset_ms=note.time_ms - selection_range.start_time_ms,
            lane=note.lane,
            note_type_name=note.note_type_name,
            end_time_offset_ms=None
            if note.end_time_ms is None
            else note.end_time_ms - selection_range.start_time_ms,
        )
        for note in selected_notes
    )
    return TimelineCopyBuffer(source_start_time_ms=selection_range.start_time_ms, notes=copied_notes)


def rename_note_type_in_copy_buffer(
    copy_buffer: TimelineCopyBuffer | None,
    old_name: str,
    new_name: str,
) -> TimelineCopyBuffer | None:
    if copy_buffer is None:
        return None
    return TimelineCopyBuffer(
        source_start_time_ms=copy_buffer.source_start_time_ms,
        notes=tuple(
            TimelineCopiedNote(
                time_offset_ms=copied_note.time_offset_ms,
                lane=copied_note.lane,
                note_type_name=new_name if copied_note.note_type_name == old_name else copied_note.note_type_name,
                end_time_offset_ms=copied_note.end_time_offset_ms,
            )
            for copied_note in copy_buffer.notes
        ),
    )


def handle_quick_edit_press(
    chart: Chart,
    tool_state: TimelineToolState,
    lane: int,
    snapped_time_ms: float,
) -> TimelineEditOutcome:
    current_note_type = chart.note_types.get(tool_state.current_note_type_name)
    if current_note_type is None:
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)
    if current_note_type.is_long_note:
        if pending_long_note_for_lane(tool_state.pending_long_notes, lane) is not None:
            return TimelineEditOutcome(chart_changed=False, next_state=tool_state)
        if not can_place_note(chart.notes, lane=lane, snapped_time_ms=snapped_time_ms):
            return TimelineEditOutcome(chart_changed=False, next_state=tool_state)
        pending_long_notes = list(tool_state.pending_long_notes)
        pending_long_notes.append(make_pending_long_note(snapped_time_ms, lane, tool_state.current_note_type_name))
        return TimelineEditOutcome(
            chart_changed=False,
            next_state=replace(tool_state, pending_long_notes=_sorted_pending_long_notes(pending_long_notes)),
        )
    if not can_place_note(chart.notes, lane=lane, snapped_time_ms=snapped_time_ms):
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)
    chart.notes.append(Note(time_ms=snapped_time_ms, note_type_name=tool_state.current_note_type_name, lane=lane))
    return TimelineEditOutcome(chart_changed=True, next_state=tool_state)


def handle_quick_edit_release(
    chart: Chart,
    tool_state: TimelineToolState,
    lane: int,
    snapped_time_ms: float,
) -> TimelineEditOutcome:
    pending_long_note = pending_long_note_for_lane(tool_state.pending_long_notes, lane)
    if pending_long_note is None:
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)
    remaining_pending_long_notes = tuple(
        existing_pending_long_note
        for existing_pending_long_note in tool_state.pending_long_notes
        if existing_pending_long_note.lane != lane
    )
    chart.notes.append(finalize_long_note(pending_long_note, snapped_time_ms))
    return TimelineEditOutcome(
        chart_changed=True,
        next_state=replace(tool_state, pending_long_notes=remaining_pending_long_notes),
    )


def apply_paste_buffer(chart: Chart, tool_state: TimelineToolState) -> TimelineEditOutcome:
    copy_buffer = tool_state.copy_buffer
    paste_marker_time_ms = tool_state.paste_marker_time_ms
    if copy_buffer is None or paste_marker_time_ms is None:
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)

    chart_changed = False
    for copied_note in copy_buffer.notes:
        if copied_note.lane >= chart.num_lanes:
            continue
        if copied_note.note_type_name not in chart.note_types:
            continue

        pasted_time_ms = paste_marker_time_ms + copied_note.time_offset_ms
        if not can_place_note(chart.notes, lane=copied_note.lane, snapped_time_ms=pasted_time_ms):
            continue

        chart.notes.append(
            Note(
                time_ms=pasted_time_ms,
                note_type_name=copied_note.note_type_name,
                lane=copied_note.lane,
                end_time_ms=None
                if copied_note.end_time_offset_ms is None
                else paste_marker_time_ms + copied_note.end_time_offset_ms,
            )
        )
        chart_changed = True
    return TimelineEditOutcome(chart_changed=chart_changed, next_state=tool_state)


def normalize_current_note_type(chart: Chart, requested_name: str | None = None) -> str:
    if requested_name and requested_name in chart.note_types:
        return requested_name
    note_type_names = list(chart.note_types.keys())
    if not note_type_names:
        return ""
    return note_type_names[0]


def judgment_line_y(panel_height: int | float, geometry: TimelineGeometry) -> float:
    return float(panel_height) * geometry.judgment_line_ratio


def centered_lane_start_x(panel_width: int | float, num_lanes: int, geometry: TimelineGeometry) -> float:
    safe_lanes = max(1, num_lanes)
    total_lanes_width = safe_lanes * geometry.lane_width_pixels
    return (float(panel_width) - total_lanes_width) / 2.0


def centered_lane_end_x(panel_width: int | float, num_lanes: int, geometry: TimelineGeometry) -> float:
    safe_lanes = max(1, num_lanes)
    return centered_lane_start_x(panel_width, safe_lanes, geometry) + (safe_lanes * geometry.lane_width_pixels)


def lane_from_panel_position(
    x_position: int | float,
    panel_width: int | float,
    num_lanes: int,
    geometry: TimelineGeometry,
) -> int | None:
    start_x = centered_lane_start_x(panel_width, num_lanes, geometry)
    end_x = centered_lane_end_x(panel_width, num_lanes, geometry)
    if x_position < start_x or x_position >= end_x:
        return None
    return int((x_position - start_x) // geometry.lane_width_pixels)


def time_to_screen_y(
    time_ms: float,
    current_time_ms: float,
    panel_height: int | float,
    geometry: TimelineGeometry,
) -> float:
    time_diff_ms = time_ms - current_time_ms
    pixel_diff = time_diff_ms * geometry.scale_pixels_per_ms
    return judgment_line_y(panel_height, geometry) - pixel_diff


def screen_y_to_time(
    screen_y: int | float,
    current_time_ms: float,
    panel_height: int | float,
    geometry: TimelineGeometry,
) -> float:
    if geometry.scale_pixels_per_ms == 0:
        return current_time_ms
    pixel_diff = judgment_line_y(panel_height, geometry) - float(screen_y)
    time_diff_ms = pixel_diff / geometry.scale_pixels_per_ms
    return current_time_ms + time_diff_ms


def resolve_timeline_hit(
    chart: Chart,
    current_audio_time_ms: float,
    tool_state: TimelineToolState,
    panel_width: int | float,
    panel_height: int | float,
    x_position: int | float,
    y_position: int | float,
    geometry: TimelineGeometry,
) -> TimelineHit | None:
    lane = lane_from_panel_position(x_position, panel_width, chart.num_lanes, geometry)
    if lane is None:
        return None

    current_note_time_ms = current_audio_time_ms + chart.offset_ms
    raw_time_ms = screen_y_to_time(y_position, current_note_time_ms, panel_height, geometry)
    snapped_time_ms = snap_time_to_grid(raw_time_ms, bpm=chart.bpm, snap_division=tool_state.snap_division)
    return TimelineHit(lane=lane, raw_time_ms=raw_time_ms, snapped_time_ms=snapped_time_ms)


def handle_primary_timeline_hit(
    chart: Chart,
    tool_state: TimelineToolState,
    hit: TimelineHit,
) -> TimelineEditOutcome:
    pending_long_note = tool_state.pending_long_note
    if pending_long_note is not None:
        next_state = replace(tool_state, pending_long_note=None)
        if hit.lane != pending_long_note.lane:
            return TimelineEditOutcome(chart_changed=False, next_state=next_state)

        chart.notes.append(finalize_long_note(pending_long_note, hit.snapped_time_ms))
        return TimelineEditOutcome(chart_changed=True, next_state=next_state)

    current_note_type = chart.note_types.get(tool_state.current_note_type_name)
    if current_note_type is None:
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)

    if not can_place_note(chart.notes, lane=hit.lane, snapped_time_ms=hit.snapped_time_ms):
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)

    if current_note_type.is_long_note:
        pending_long_note = make_pending_long_note(hit.snapped_time_ms, hit.lane, tool_state.current_note_type_name)
        return TimelineEditOutcome(
            chart_changed=False,
            next_state=replace(tool_state, pending_long_note=pending_long_note),
        )

    chart.notes.append(Note(time_ms=hit.snapped_time_ms, note_type_name=tool_state.current_note_type_name, lane=hit.lane))
    return TimelineEditOutcome(chart_changed=True, next_state=tool_state)


def handle_secondary_timeline_hit(
    chart: Chart,
    tool_state: TimelineToolState,
    hit: TimelineHit,
) -> TimelineEditOutcome:
    if tool_state.pending_long_note is not None:
        return TimelineEditOutcome(chart_changed=False, next_state=replace(tool_state, pending_long_note=None))

    note_to_delete = find_note_to_delete(chart.notes, lane=hit.lane, raw_time_ms=hit.raw_time_ms)
    if note_to_delete is None:
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)

    chart.notes.remove(note_to_delete)
    return TimelineEditOutcome(chart_changed=True, next_state=tool_state)


def _note_sort_key(note: Note) -> tuple[float, int, float, str]:
    return (
        note.time_ms,
        note.lane,
        note.end_time_ms if note.end_time_ms is not None else note.time_ms,
        note.note_type_name,
    )


def _sorted_pending_long_notes(pending_long_notes: list[PendingLongNote]) -> tuple[PendingLongNote, ...]:
    return tuple(sorted(pending_long_notes, key=lambda pending_long_note: (pending_long_note.lane, pending_long_note.time_ms, pending_long_note.type_name)))

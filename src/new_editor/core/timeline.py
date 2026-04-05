from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class TimelineGeometry:
    lane_width_pixels: int = DEFAULT_LANE_WIDTH_PIXELS
    scale_pixels_per_ms: float = DEFAULT_SCALE_PIXELS_PER_MS
    judgment_line_ratio: float = DEFAULT_JUDGMENT_LINE_RATIO


@dataclass(frozen=True, slots=True)
class TimelineToolState:
    snap_division: int = DEFAULT_SNAP_DIVISION
    current_note_type_name: str = "Tap"
    pending_long_note: PendingLongNote | None = None


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
        next_state = TimelineToolState(
            snap_division=tool_state.snap_division,
            current_note_type_name=tool_state.current_note_type_name,
            pending_long_note=None,
        )
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
            next_state=TimelineToolState(
                snap_division=tool_state.snap_division,
                current_note_type_name=tool_state.current_note_type_name,
                pending_long_note=pending_long_note,
            ),
        )

    chart.notes.append(Note(time_ms=hit.snapped_time_ms, note_type_name=tool_state.current_note_type_name, lane=hit.lane))
    return TimelineEditOutcome(chart_changed=True, next_state=tool_state)


def handle_secondary_timeline_hit(
    chart: Chart,
    tool_state: TimelineToolState,
    hit: TimelineHit,
) -> TimelineEditOutcome:
    if tool_state.pending_long_note is not None:
        return TimelineEditOutcome(
            chart_changed=False,
            next_state=TimelineToolState(
                snap_division=tool_state.snap_division,
                current_note_type_name=tool_state.current_note_type_name,
                pending_long_note=None,
            ),
        )

    note_to_delete = find_note_to_delete(chart.notes, lane=hit.lane, raw_time_ms=hit.raw_time_ms)
    if note_to_delete is None:
        return TimelineEditOutcome(chart_changed=False, next_state=tool_state)

    chart.notes.remove(note_to_delete)
    return TimelineEditOutcome(chart_changed=True, next_state=tool_state)

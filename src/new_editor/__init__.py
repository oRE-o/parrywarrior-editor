from .core.hitsounds import default_hitsound_path, hitsound_crossings, hitsound_status_text
from .core.legacy_import import chart_from_legacy_source_data, chart_from_legacy_source_text
from .core.legacy_rules import (
    DELETE_TIME_TOLERANCE_MS,
    can_place_note,
    chart_allows_placement,
    finalize_long_note,
    find_note_to_delete,
    make_pending_long_note,
    round_half_away_from_zero,
    snap_duration_ms,
    snap_time_to_grid,
)
from .core.media import MediaState, PlaybackState, WaveformData
from .core.models import Chart, Note, NoteType, PendingLongNote, default_note_types
from .core.note_types import LEGACY_NOTE_TYPE_PRESET_COLORS, create_note_type, update_note_type
from .core.timeline import (
    DEFAULT_LANE_WIDTH_PIXELS,
    DEFAULT_SNAP_DIVISION,
    TimelineEditOutcome,
    TimelineGeometry,
    TimelineHit,
    TimelineToolState,
    centered_lane_end_x,
    centered_lane_start_x,
    handle_primary_timeline_hit,
    handle_secondary_timeline_hit,
    judgment_line_y,
    lane_from_panel_position,
    normalize_current_note_type,
    resolve_timeline_hit,
    screen_y_to_time,
    time_to_screen_y,
)
from .core.legacy_json import chart_from_json_text, chart_to_json_text
from .services.session_io import SaveResult, load_chart_file, save_chart_file

try:
    from .services.media_session import MediaSessionService, WaveformExtractor
except ModuleNotFoundError:
    MediaSessionService = None
    WaveformExtractor = None

__all__ = [
    "Chart",
    "DEFAULT_LANE_WIDTH_PIXELS",
    "DEFAULT_SNAP_DIVISION",
    "DELETE_TIME_TOLERANCE_MS",
    "MediaSessionService",
    "MediaState",
    "LEGACY_NOTE_TYPE_PRESET_COLORS",
    "Note",
    "NoteType",
    "PendingLongNote",
    "PlaybackState",
    "SaveResult",
    "TimelineEditOutcome",
    "TimelineGeometry",
    "TimelineHit",
    "TimelineToolState",
    "WaveformData",
    "WaveformExtractor",
    "can_place_note",
    "centered_lane_end_x",
    "centered_lane_start_x",
    "chart_allows_placement",
    "chart_from_legacy_source_data",
    "chart_from_legacy_source_text",
    "create_note_type",
    "default_hitsound_path",
    "finalize_long_note",
    "find_note_to_delete",
    "handle_primary_timeline_hit",
    "handle_secondary_timeline_hit",
    "judgment_line_y",
    "lane_from_panel_position",
    "make_pending_long_note",
    "normalize_current_note_type",
    "round_half_away_from_zero",
    "resolve_timeline_hit",
    "screen_y_to_time",
    "snap_duration_ms",
    "snap_time_to_grid",
    "time_to_screen_y",
    "hitsound_crossings",
    "hitsound_status_text",
    "chart_from_json_text",
    "chart_to_json_text",
    "default_note_types",
    "load_chart_file",
    "save_chart_file",
    "update_note_type",
]

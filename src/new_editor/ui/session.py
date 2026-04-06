from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

try:
    from PySide6.QtCore import QObject as _QObject, Signal as _Signal

    QObject = cast(Any, _QObject)
    Signal = cast(Any, _Signal)
except ModuleNotFoundError:
    class _FallbackQtSignalProxy:
        def __init__(self) -> None:
            self._callbacks: list[object] = []

        def connect(self, callback: object) -> None:
            self._callbacks.append(callback)

        def emit(self, *args: object, **kwargs: object) -> None:
            for callback in list(self._callbacks):
                if callable(callback):
                    callback(*args, **kwargs)

    class QObject:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

    def _missing_signal_factory(*_args: object, **_kwargs: object) -> _FallbackQtSignalProxy:
        return _FallbackQtSignalProxy()

    QObject = cast(Any, QObject)
    Signal = cast(Any, _missing_signal_factory)

from ..core.media import MediaState, PlaybackState
from ..core.models import Chart
from ..core.hitsounds import build_hitsound_event_times, default_hitsound_path, has_hitsound_crossing
from ..core.note_types import create_note_type, update_note_type
from ..core.timeline import (
    TimelineEditOutcome,
    TimelineGeometry,
    TimelineHit,
    TimelineToolState,
    clamp_scale_pixels_per_ms,
    handle_primary_timeline_hit,
    handle_secondary_timeline_hit,
    normalize_current_note_type,
    resolve_timeline_hit,
    screen_y_to_time,
)
from ..services.media_session import MediaSessionService
from ..services.session_io import (
    SaveResult,
    autosave_chart_file,
    autosave_chart_path_for,
    clear_autosave_file,
    import_legacy_chart_file,
    load_chart_file,
    load_recovery_chart_file,
    save_chart_file,
)


class EditorSession(QObject):
    chart_changed = Signal(object, bool)
    timeline_state_changed = Signal(object)
    timeline_geometry_changed = Signal(object)
    media_state_changed = Signal(object)
    status_message_requested = Signal(str, int)

    def __init__(self) -> None:
        super().__init__()
        self._chart = Chart()
        self._is_dirty = False
        self._autosave_anchor_path: Path | None = None
        self._import_source_path: Path | None = None
        self._requires_save_as = False
        self._autosave_notice_emitted = False
        self._autosave_count_for_dirty_cycle = 0
        self._timeline_geometry = TimelineGeometry()
        self._timeline_state = TimelineToolState(current_note_type_name=normalize_current_note_type(self._chart))
        self._media_session = MediaSessionService()
        self._hitsound_event_times = build_hitsound_event_times(self._chart)
        self._last_played_note_time_ms = self._current_note_time_ms()
        self._media_session.media_state_changed.connect(self._handle_media_state_changed)
        self._media_session.load_hitsound(default_hitsound_path())

    @property
    def chart(self) -> Chart:
        return self._chart

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    @property
    def timeline_state(self) -> TimelineToolState:
        return self._timeline_state

    @property
    def suggested_save_name(self) -> str:
        if self._chart.chart_path:
            return Path(self._chart.chart_path).name
        if self._import_source_path is not None:
            return f"{self._import_source_path.stem}_chart.json"
        return "untitled_chart.json"

    @property
    def timeline_geometry(self) -> TimelineGeometry:
        return self._timeline_geometry

    def emit_initial_state(self) -> None:
        self.chart_changed.emit(self._chart, self._is_dirty)
        self.timeline_state_changed.emit(self._timeline_state)
        self.timeline_geometry_changed.emit(self._timeline_geometry)
        self.media_state_changed.emit(self._media_session.state)

    def new_chart(self) -> None:
        self._chart = Chart()
        self._autosave_anchor_path = None
        self._import_source_path = None
        self._requires_save_as = False
        self._set_dirty(False)
        self._reset_timeline_state()
        self._sync_last_played_note_time()
        self._media_session.clear_song()
        self._notify_chart_changed()
        self.status_message_requested.emit(
            "New chart.",
            2500,
        )

    def open_chart(self, path: str | Path) -> None:
        chart = load_chart_file(path)
        self._chart = chart
        self._autosave_anchor_path = Path(chart.chart_path)
        self._import_source_path = None
        self._requires_save_as = False
        self._set_dirty(False)
        self._reset_timeline_state()
        self._sync_last_played_note_time()
        if chart.song_path:
            self._media_session.load_song(chart.song_path)
        else:
            self._media_session.clear_song()
        self._notify_chart_changed()
        self.status_message_requested.emit(self._loaded_chart_message(f"Opened chart: {Path(chart.chart_path).name}"), 7000)

    def open_recovery_chart(
        self,
        path: str | Path,
        *,
        chart_path: str | Path | None = None,
        source_label: str = "recovery snapshot",
    ) -> None:
        chart = load_recovery_chart_file(path, chart_path=chart_path)
        self._chart = chart
        self._autosave_anchor_path = Path(chart.chart_path) if chart.chart_path else Path(path)
        self._import_source_path = None
        self._requires_save_as = not bool(chart.chart_path)
        self._autosave_notice_emitted = False
        self._autosave_count_for_dirty_cycle = 0
        self._set_dirty(True)
        self._reset_timeline_state()
        self._sync_last_played_note_time()
        if chart.song_path:
            self._media_session.load_song(chart.song_path)
        else:
            self._media_session.clear_song()
        self._notify_chart_changed()
        self.status_message_requested.emit(
            self._loaded_chart_message(f"Opened {source_label}: {Path(path).name}"),
            7000,
        )

    def import_legacy_chart(self, path: str | Path) -> None:
        source = Path(path)
        chart = import_legacy_chart_file(source)
        self._chart = chart
        self._autosave_anchor_path = source
        self._import_source_path = source
        self._requires_save_as = True
        self._autosave_notice_emitted = False
        self._autosave_count_for_dirty_cycle = 0
        self._set_dirty(True)
        self._reset_timeline_state()
        self._sync_last_played_note_time()
        if chart.song_path:
            self._media_session.load_song(chart.song_path)
        else:
            self._media_session.clear_song()
        self._notify_chart_changed()
        self._autosave_notice_emitted = True
        self.status_message_requested.emit(
            self._loaded_chart_message(
                f"Imported: {source.name}"
            ),
            4000,
        )

    def save_chart(self) -> SaveResult:
        if self._requires_save_as or not self._chart.chart_path:
            raise ValueError("This session does not have a writable chart location yet. Use Save As to keep the source file untouched.")
        previous_anchor = self._autosave_anchor_path
        result = save_chart_file(self._chart, self._chart.chart_path)
        self._finalize_manual_save(result, previous_anchor=previous_anchor)
        return result

    def save_chart_as(self, path: str | Path) -> SaveResult:
        previous_anchor = self._autosave_anchor_path
        result = save_chart_file(self._chart, path)
        self._finalize_manual_save(result, previous_anchor=previous_anchor)
        return result

    def autosave_if_needed(self) -> SaveResult | None:
        if not self._is_dirty or self._autosave_anchor_path is None:
            return None
        result = autosave_chart_file(self._chart, self._autosave_anchor_path)
        self._autosave_count_for_dirty_cycle += 1
        if self._autosave_count_for_dirty_cycle == 1:
            self.status_message_requested.emit(
                f"Autosaved recovery snapshot to {result.path.name}.",
                2500,
            )
        return result

    def load_song(self, path: str | Path) -> None:
        self._chart.song_path = str(Path(path))
        self._set_dirty(True)
        self._media_session.load_song(path)
        self._notify_chart_changed()

        media_state = self._media_session.state
        if media_state.error_message:
            message = f"Song linked · {media_state.error_message}"
        elif media_state.waveform.is_available:
            message = "Song linked."
        elif media_state.waveform.limitation:
            message = "Song linked."
        else:
            message = "Song linked."
        self.status_message_requested.emit(message, 3000)

    def toggle_play_pause(self) -> None:
        self._media_session.toggle_play_pause()

    def stop_song(self) -> None:
        self._media_session.stop()

    def seek_song(self, position_ms: float) -> None:
        self._media_session.seek(position_ms)

    def set_song_volume(self, volume: float) -> None:
        self._media_session.set_volume(volume)

    def scrub_timeline_by_wheel(
        self,
        wheel_steps: float,
        alt_pressed: bool = False,
        ctrl_pressed: bool = False,
    ) -> None:
        if wheel_steps == 0 or self._media_session.state.playback_state == PlaybackState.PLAYING:
            return
        if self._timeline_geometry.scale_pixels_per_ms <= 0:
            return

        scroll_amount_ms = wheel_steps * ((1000.0 / self._timeline_geometry.scale_pixels_per_ms) * 0.1)
        if alt_pressed:
            scroll_amount_ms *= 0.1
        if ctrl_pressed:
            scroll_amount_ms *= 6.0
        self._media_session.seek(self._media_session.state.position_ms + scroll_amount_ms)

    def nudge_timeline(self, delta_ms: float) -> None:
        if delta_ms == 0 or self._media_session.state.playback_state == PlaybackState.PLAYING:
            return
        self._media_session.seek(self._media_session.state.position_ms + delta_ms)

    def seek_from_overview(self, y_position: float, panel_height: int) -> None:
        if panel_height <= 0:
            return
        target_position_ms = screen_y_to_time(
            float(y_position),
            float(self._media_session.state.position_ms),
            panel_height,
            self._timeline_geometry,
        )
        self._media_session.seek(target_position_ms)

    def set_bpm(self, bpm: float) -> None:
        safe_bpm = float(bpm)
        if safe_bpm <= 0 or self._chart.bpm == safe_bpm:
            return
        self._chart.bpm = safe_bpm
        self._mark_chart_edited()

    def set_offset_ms(self, offset_ms: int) -> None:
        safe_offset_ms = float(offset_ms)
        if self._chart.offset_ms == safe_offset_ms:
            return
        self._chart.offset_ms = safe_offset_ms
        self._sync_last_played_note_time()
        self._mark_chart_edited()

    def set_lane_count(self, lane_count: int) -> None:
        safe_lane_count = min(7, max(3, int(lane_count)))
        if self._chart.num_lanes == safe_lane_count:
            return
        self._chart.num_lanes = safe_lane_count

        pending_long_note = self._timeline_state.pending_long_note
        if pending_long_note is not None and pending_long_note.lane >= safe_lane_count:
            self._set_timeline_state(replace(self._timeline_state, pending_long_note=None))

        self._mark_chart_edited()

    def set_snap_division(self, snap_division: int) -> None:
        safe_snap_division = max(1, int(snap_division))
        self._set_timeline_state(replace(self._timeline_state, snap_division=safe_snap_division))

    def set_scale_pixels_per_ms(self, scale_pixels_per_ms: float) -> None:
        safe_scale_pixels_per_ms = clamp_scale_pixels_per_ms(scale_pixels_per_ms)
        if self._timeline_geometry.scale_pixels_per_ms == safe_scale_pixels_per_ms:
            return
        self._timeline_geometry = replace(self._timeline_geometry, scale_pixels_per_ms=safe_scale_pixels_per_ms)
        self.timeline_geometry_changed.emit(self._timeline_geometry)

    def set_current_note_type(self, note_type_name: str) -> None:
        normalized_name = normalize_current_note_type(self._chart, note_type_name)
        self._set_timeline_state(replace(self._timeline_state, current_note_type_name=normalized_name))

    def create_note_type(
        self,
        *,
        name: str,
        color: tuple[int, int, int],
        is_long_note: bool,
        play_hitsound: bool,
    ) -> None:
        note_type = create_note_type(
            self._chart,
            name=name,
            color=color,
            is_long_note=is_long_note,
            play_hitsound=play_hitsound,
        )
        self._set_timeline_state(replace(self._timeline_state, current_note_type_name=note_type.name))
        self._mark_chart_edited()

    def update_note_type(
        self,
        note_type_name: str,
        *,
        name: str,
        color: tuple[int, int, int],
        is_long_note: bool,
        play_hitsound: bool,
    ) -> None:
        result = update_note_type(
            self._chart,
            note_type_name,
            name=name,
            color=color,
            is_long_note=is_long_note,
            play_hitsound=play_hitsound,
        )
        if result.renamed:
            renamed_note_type_name = result.note_type.name
            pending_long_note = self._timeline_state.pending_long_note
            if pending_long_note is not None and pending_long_note.type_name == note_type_name:
                pending_long_note = replace(pending_long_note, type_name=renamed_note_type_name)

            current_note_type_name = self._timeline_state.current_note_type_name
            if current_note_type_name == note_type_name:
                current_note_type_name = renamed_note_type_name

            self._set_timeline_state(
                replace(
                    self._timeline_state,
                    current_note_type_name=current_note_type_name,
                    pending_long_note=pending_long_note,
                )
            )
        self._mark_chart_edited()

    def handle_timeline_primary_click(
        self,
        x_position: float,
        y_position: float,
        panel_width: int,
        panel_height: int,
    ) -> None:
        hit = self._resolve_timeline_hit(x_position, y_position, panel_width, panel_height)
        if hit is None:
            return
        outcome = handle_primary_timeline_hit(self._chart, self._timeline_state, hit)
        self._apply_timeline_outcome(outcome)

    def handle_timeline_secondary_click(
        self,
        x_position: float,
        y_position: float,
        panel_width: int,
        panel_height: int,
    ) -> None:
        hit = self._resolve_timeline_hit(x_position, y_position, panel_width, panel_height)
        if hit is None:
            return
        outcome = handle_secondary_timeline_hit(self._chart, self._timeline_state, hit)
        self._apply_timeline_outcome(outcome)

    def _announce_save_result(self, result: SaveResult) -> None:
        if result.backup_path is None:
            message = f"Saved chart to {result.path.name}."
        else:
            message = f"Saved chart to {result.path.name} and refreshed backup {result.backup_path.name}."
        self.status_message_requested.emit(message, 7000)

    def _finalize_manual_save(self, result: SaveResult, *, previous_anchor: Path | None) -> None:
        self._requires_save_as = False
        self._import_source_path = None
        self._autosave_anchor_path = result.path
        self._clear_autosave_for_anchor(result.path)
        if previous_anchor is not None and previous_anchor != result.path:
            self._clear_autosave_for_anchor(previous_anchor)
        self._set_dirty(False)
        self._notify_chart_changed()
        self._announce_save_result(result)

    def _clear_autosave_for_anchor(self, anchor_path: str | Path) -> None:
        try:
            clear_autosave_file(anchor_path)
        except FileNotFoundError:
            pass

    def _loaded_chart_message(self, prefix: str) -> str:
        if self._chart.song_path and not Path(self._chart.song_path).exists():
            return f"{prefix} Linked song is missing on disk, so playback stays unavailable until you relink it."
        return prefix

    def _apply_timeline_outcome(self, outcome: TimelineEditOutcome) -> None:
        self._set_timeline_state(outcome.next_state)
        if outcome.chart_changed:
            self._mark_chart_edited()

    def _mark_chart_edited(self) -> None:
        self._set_dirty(True)
        if not self._autosave_notice_emitted:
            if self._autosave_anchor_path is None:
                self.status_message_requested.emit(
                    "Unsaved changes are in memory only right now. Autosave starts after Save As or after importing from a file.",
                    7000,
                )
            else:
                self.status_message_requested.emit(
                    f"Unsaved changes will be autosaved to {autosave_chart_path_for(self._autosave_anchor_path).name} while this session stays dirty.",
                    7000,
                )
            self._autosave_notice_emitted = True
        self._notify_chart_changed()

    def _notify_chart_changed(self) -> None:
        self._hitsound_event_times = build_hitsound_event_times(self._chart)
        self.chart_changed.emit(self._chart, self._is_dirty)

    def _reset_timeline_state(self) -> None:
        self._set_timeline_state(
            TimelineToolState(
                snap_division=self._timeline_state.snap_division,
                current_note_type_name=normalize_current_note_type(self._chart, self._timeline_state.current_note_type_name),
            )
        )

    def _set_timeline_state(self, timeline_state: TimelineToolState) -> None:
        if self._timeline_state == timeline_state:
            return
        self._timeline_state = timeline_state
        self.timeline_state_changed.emit(self._timeline_state)

    def _handle_media_state_changed(self, media_state: MediaState) -> None:
        current_note_time_ms = float(media_state.position_ms) + self._chart.offset_ms
        if media_state.playback_state == PlaybackState.PLAYING:
            if has_hitsound_crossing(self._hitsound_event_times, self._last_played_note_time_ms, current_note_time_ms):
                _ = self._media_session.play_hitsound()
            self._last_played_note_time_ms = max(self._last_played_note_time_ms, current_note_time_ms)
        else:
            self._last_played_note_time_ms = current_note_time_ms
        self.media_state_changed.emit(media_state)

    def _resolve_timeline_hit(
        self,
        x_position: float,
        y_position: float,
        panel_width: int,
        panel_height: int,
    ) -> TimelineHit | None:
        return resolve_timeline_hit(
            self._chart,
            float(self._media_session.state.position_ms),
            self._timeline_state,
            panel_width,
            panel_height,
            x_position,
            y_position,
            self._timeline_geometry,
        )

    def _set_dirty(self, value: bool) -> None:
        self._is_dirty = value
        if not value:
            self._autosave_notice_emitted = False
            self._autosave_count_for_dirty_cycle = 0

    def _current_note_time_ms(self) -> float:
        return float(self._media_session.state.position_ms) + self._chart.offset_ms

    def _sync_last_played_note_time(self) -> None:
        self._last_played_note_time_ms = self._current_note_time_ms()

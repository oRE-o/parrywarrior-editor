from __future__ import annotations

import unittest

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from src.new_editor.ui.main_window import EditorMainWindow
from src.new_editor.core.legacy_rules import make_pending_long_note
from src.new_editor.core.models import Chart, Note
from src.new_editor.core.timeline import (
    MAX_SCALE_PIXELS_PER_MS,
    MIN_SCALE_PIXELS_PER_MS,
    TimelineGeometry,
    TimelineHit,
    TimelineToolState,
    clamp_scale_pixels_per_ms,
    centered_lane_start_x,
    handle_primary_timeline_hit,
    handle_secondary_timeline_hit,
    judgment_line_y,
    lane_from_panel_position,
    quick_edit_lane_key_preset_for_lane_count,
    resolve_timeline_hit,
)
from src.new_editor.ui.session import EditorSession


class TimelineCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_quick_edit_lane_presets_match_documented_layouts(self) -> None:
        self.assertEqual(quick_edit_lane_key_preset_for_lane_count(3), (("d",), ("f",), ("j",)))
        self.assertEqual(quick_edit_lane_key_preset_for_lane_count(4), (("d",), ("f",), ("j",), ("k",)))
        self.assertEqual(quick_edit_lane_key_preset_for_lane_count(5), (("s",), ("d",), ("f", "j"), ("k",), ("l",)))
        self.assertEqual(quick_edit_lane_key_preset_for_lane_count(6), (("s",), ("d",), ("f",), ("j",), ("k",), ("l",)))
        self.assertEqual(
            quick_edit_lane_key_preset_for_lane_count(7),
            (("s",), ("d",), ("f",), ("space", " "), ("j",), ("k",), ("l",)),
        )

    def test_lane_hit_uses_centered_columns(self) -> None:
        geometry = TimelineGeometry()
        lane_start_x = centered_lane_start_x(480, 4, geometry)

        self.assertIsNone(lane_from_panel_position(lane_start_x - 1, 480, 4, geometry))
        self.assertEqual(lane_from_panel_position(lane_start_x, 480, 4, geometry), 0)
        self.assertEqual(lane_from_panel_position(lane_start_x + 60, 480, 4, geometry), 1)
        self.assertIsNone(lane_from_panel_position(lane_start_x + 240, 480, 4, geometry))

    def test_resolve_timeline_hit_uses_media_position_plus_offset(self) -> None:
        chart = Chart(bpm=120.0, offset_ms=125.0, num_lanes=4)
        tool_state = TimelineToolState(snap_division=16, current_note_type_name="Tap")
        geometry = TimelineGeometry()
        hit = resolve_timeline_hit(
            chart,
            current_audio_time_ms=250.0,
            tool_state=tool_state,
            panel_width=480,
            panel_height=600,
            x_position=centered_lane_start_x(480, 4, geometry) + 5,
            y_position=judgment_line_y(600, geometry),
            geometry=geometry,
        )

        self.assertIsNotNone(hit)
        assert hit is not None
        self.assertEqual(hit.lane, 0)
        self.assertEqual(hit.raw_time_ms, 375.0)
        self.assertEqual(hit.snapped_time_ms, 375.0)

    def test_long_note_two_click_flow_swaps_reverse_endpoints(self) -> None:
        chart = Chart()
        tool_state = TimelineToolState(current_note_type_name="Long")

        first_click = TimelineHit(lane=1, raw_time_ms=1000.0, snapped_time_ms=1000.0)
        first_outcome = handle_primary_timeline_hit(chart, tool_state, first_click)

        self.assertFalse(first_outcome.chart_changed)
        self.assertIsNotNone(first_outcome.next_state.pending_long_note)

        second_click = TimelineHit(lane=1, raw_time_ms=500.0, snapped_time_ms=500.0)
        second_outcome = handle_primary_timeline_hit(chart, first_outcome.next_state, second_click)

        self.assertTrue(second_outcome.chart_changed)
        self.assertIsNone(second_outcome.next_state.pending_long_note)
        self.assertEqual(len(chart.notes), 1)
        self.assertEqual(chart.notes[0].time_ms, 500.0)
        self.assertEqual(chart.notes[0].end_time_ms, 1000.0)

    def test_zero_length_long_note_collapses_to_note_without_end_time(self) -> None:
        chart = Chart()
        tool_state = TimelineToolState(current_note_type_name="Long")

        first_outcome = handle_primary_timeline_hit(chart, tool_state, TimelineHit(lane=2, raw_time_ms=750.0, snapped_time_ms=750.0))
        second_outcome = handle_primary_timeline_hit(
            chart,
            first_outcome.next_state,
            TimelineHit(lane=2, raw_time_ms=750.0, snapped_time_ms=750.0),
        )

        self.assertTrue(second_outcome.chart_changed)
        self.assertEqual(len(chart.notes), 1)
        self.assertIsNone(chart.notes[0].end_time_ms)
        self.assertEqual(chart.notes[0].note_type_name, "Long")

    def test_second_click_on_different_lane_cancels_pending_long_note(self) -> None:
        chart = Chart()
        tool_state = TimelineToolState(current_note_type_name="Long")

        first_outcome = handle_primary_timeline_hit(chart, tool_state, TimelineHit(lane=0, raw_time_ms=1000.0, snapped_time_ms=1000.0))
        second_outcome = handle_primary_timeline_hit(
            chart,
            first_outcome.next_state,
            TimelineHit(lane=1, raw_time_ms=1200.0, snapped_time_ms=1200.0),
        )

        self.assertFalse(second_outcome.chart_changed)
        self.assertIsNone(second_outcome.next_state.pending_long_note)
        self.assertEqual(chart.notes, [])

    def test_secondary_click_deletes_matching_note_using_raw_time(self) -> None:
        chart = Chart(notes=[Note(time_ms=1000.0, note_type_name="Tap", lane=1)])
        tool_state = TimelineToolState(current_note_type_name="Tap")

        outcome = handle_secondary_timeline_hit(
            chart,
            tool_state,
            TimelineHit(lane=1, raw_time_ms=1049.0, snapped_time_ms=1125.0),
        )

        self.assertTrue(outcome.chart_changed)
        self.assertEqual(chart.notes, [])

    def test_secondary_click_cancels_pending_long_note_before_delete(self) -> None:
        chart = Chart(notes=[Note(time_ms=1000.0, note_type_name="Tap", lane=0)])
        tool_state = TimelineToolState(
            current_note_type_name="Long",
            pending_long_note=make_pending_long_note(500.0, 0, "Long"),
        )

        outcome = handle_secondary_timeline_hit(
            chart,
            tool_state,
            TimelineHit(lane=0, raw_time_ms=1000.0, snapped_time_ms=1000.0),
        )

        self.assertFalse(outcome.chart_changed)
        self.assertIsNone(outcome.next_state.pending_long_note)
        self.assertEqual(len(chart.notes), 1)

    def test_editor_session_clamps_lane_count_to_legacy_range(self) -> None:
        session = EditorSession()

        session.set_lane_count(1)
        self.assertEqual(session.chart.num_lanes, 3)

        session.set_lane_count(99)
        self.assertEqual(session.chart.num_lanes, 7)

    def test_quick_edit_tap_inserts_snapped_note_at_current_playback_time(self) -> None:
        session = EditorSession()
        session.set_lane_count(6)
        session.set_quick_edit_enabled(True)
        session.seek_song(188.0)

        handled = session.handle_quick_edit_key_press("s")

        self.assertTrue(handled)
        self.assertEqual(len(session.chart.notes), 1)
        self.assertEqual(session.chart.notes[0].lane, 0)
        self.assertEqual(session.chart.notes[0].time_ms, 125.0)

    def test_quick_edit_tap_applies_input_correction_before_snapping(self) -> None:
        session = EditorSession()
        session.set_quick_edit_enabled(True)
        session.seek_song(160.0)

        handled = session.handle_quick_edit_key_press("d")

        self.assertTrue(handled)
        self.assertEqual(len(session.chart.notes), 1)
        self.assertEqual(session.chart.notes[0].time_ms, 125.0)

    def test_quick_edit_correction_does_not_push_very_early_input_below_zero(self) -> None:
        session = EditorSession()
        session.set_quick_edit_enabled(True)
        session.seek_song(20.0)

        handled = session.handle_quick_edit_key_press("d")

        self.assertTrue(handled)
        self.assertEqual(len(session.chart.notes), 1)
        self.assertEqual(session.chart.notes[0].time_ms, 0.0)

    def test_quick_edit_can_insert_same_time_chord_across_lanes(self) -> None:
        session = EditorSession()
        session.set_lane_count(4)
        session.set_quick_edit_enabled(True)
        session.seek_song(250.0)

        self.assertTrue(session.handle_quick_edit_key_press("d"))
        self.assertTrue(session.handle_quick_edit_key_press("f"))

        self.assertEqual([(note.lane, note.time_ms) for note in session.chart.notes], [(0, 250.0), (1, 250.0)])

    def test_quick_edit_long_note_holds_finalize_per_lane(self) -> None:
        session = EditorSession()
        session.set_lane_count(6)
        session.set_current_note_type("Long")
        session.set_quick_edit_enabled(True)
        session.seek_song(500.0)

        self.assertTrue(session.handle_quick_edit_key_press("s"))
        self.assertTrue(session.handle_quick_edit_key_press("j"))
        self.assertEqual([pending.lane for pending in session.timeline_state.pending_long_notes], [0, 3])

        session.seek_song(1000.0)
        self.assertTrue(session.handle_quick_edit_key_release("s"))
        self.assertTrue(session.handle_quick_edit_key_release("j"))

        self.assertEqual(
            [(note.lane, note.time_ms, note.end_time_ms) for note in session.chart.notes],
            [(0, 500.0, 1000.0), (3, 500.0, 1000.0)],
        )
        self.assertEqual(session.timeline_state.pending_long_notes, ())

    def test_quick_edit_long_note_release_applies_input_correction_before_snapping(self) -> None:
        session = EditorSession()
        session.set_current_note_type("Long")
        session.set_quick_edit_enabled(True)
        session.seek_song(500.0)

        self.assertTrue(session.handle_quick_edit_key_press("d"))

        session.seek_song(540.0)
        self.assertTrue(session.handle_quick_edit_key_release("d"))

        self.assertEqual(len(session.chart.notes), 1)
        self.assertEqual(session.chart.notes[0].time_ms, 500.0)
        self.assertIsNone(session.chart.notes[0].end_time_ms)

    def test_quick_edit_shared_center_key_waits_for_all_aliases_to_release(self) -> None:
        session = EditorSession()
        session.set_lane_count(5)
        session.set_current_note_type("Long")
        session.set_quick_edit_enabled(True)
        session.seek_song(500.0)

        self.assertTrue(session.handle_quick_edit_key_press("f"))
        self.assertTrue(session.handle_quick_edit_key_press("j"))
        self.assertEqual([pending.lane for pending in session.timeline_state.pending_long_notes], [2])

        session.seek_song(1000.0)
        self.assertTrue(session.handle_quick_edit_key_release("f"))
        self.assertEqual(len(session.chart.notes), 0)
        self.assertEqual([pending.lane for pending in session.timeline_state.pending_long_notes], [2])

        self.assertTrue(session.handle_quick_edit_key_release("j"))
        self.assertEqual(len(session.chart.notes), 1)
        self.assertEqual(session.chart.notes[0].lane, 2)
        self.assertEqual(session.chart.notes[0].time_ms, 500.0)
        self.assertEqual(session.chart.notes[0].end_time_ms, 1000.0)

    def test_quick_edit_selection_updates_live_while_hovering(self) -> None:
        session = EditorSession()
        session.set_quick_edit_enabled(True)

        session.handle_timeline_primary_click(150.0, 200.0, 480, 600)
        first_range = session.timeline_state.selection_range
        assert first_range is not None
        self.assertEqual(first_range.start_time_ms, first_range.end_time_ms)

        session.handle_timeline_hover(150.0, 80.0, 480, 600)

        updated_range = session.timeline_state.selection_range
        assert updated_range is not None
        self.assertNotEqual(updated_range.start_time_ms, updated_range.end_time_ms)

    def test_quick_edit_invalid_second_click_cancels_selection(self) -> None:
        session = EditorSession()
        session.set_quick_edit_enabled(True)

        session.handle_timeline_primary_click(150.0, 200.0, 480, 600)
        assert session.timeline_state.selection_range is not None

        session.handle_timeline_primary_click(5.0, 200.0, 480, 600)

        self.assertIsNone(session.timeline_state.selection_range)

    def test_main_window_routes_space_to_quick_edit_lane_input_in_seven_lane_mode(self) -> None:
        window = EditorMainWindow()
        setattr(window, "_should_handle_editor_shortcut", lambda: True)
        window.session.set_lane_count(7)
        window.session.set_quick_edit_enabled(True)

        press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ")
        release = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ")

        self.assertTrue(window.eventFilter(window, press))
        self.assertTrue(window.eventFilter(window, release))
        self.assertEqual(len(window.session.chart.notes), 1)
        self.assertEqual(window.session.chart.notes[0].lane, 3)

    def test_selection_copy_and_marker_paste_are_deterministic_and_skip_duplicates(self) -> None:
        session = EditorSession()
        session.chart.notes.extend(
            [
                Note(time_ms=1000.0, note_type_name="Tap", lane=0),
                Note(time_ms=1125.0, note_type_name="Tap", lane=1),
                Note(time_ms=1500.0, note_type_name="Tap", lane=2),
                Note(time_ms=2000.0, note_type_name="Tap", lane=0),
            ]
        )

        session.set_selection_range(1200.0, 1000.0)
        copied_count = session.copy_selection_range()
        session.set_paste_marker_time(2000.0)
        pasted_count = session.paste_copy_buffer()

        self.assertEqual(copied_count, 2)
        self.assertEqual(pasted_count, 1)
        self.assertIsNotNone(session.timeline_state.copy_buffer)
        self.assertEqual(
            [(note.lane, note.time_ms) for note in session.chart.notes],
            [(0, 1000.0), (1, 1125.0), (2, 1500.0), (0, 2000.0), (1, 2125.0)],
        )

    def test_paste_marker_can_snap_from_current_time(self) -> None:
        session = EditorSession()
        session.seek_song(188.0)

        paste_marker_time_ms = session.set_paste_marker_from_current_time()

        self.assertEqual(paste_marker_time_ms, 250.0)
        self.assertEqual(session.timeline_state.paste_marker_time_ms, 250.0)

    def test_clamp_scale_pixels_per_ms_matches_legacy_scroll_speed_range(self) -> None:
        self.assertEqual(clamp_scale_pixels_per_ms(0.01), MIN_SCALE_PIXELS_PER_MS)
        self.assertEqual(clamp_scale_pixels_per_ms(3.0), MAX_SCALE_PIXELS_PER_MS)
        self.assertEqual(clamp_scale_pixels_per_ms(0.5), 0.5)

    def test_editor_session_scrub_uses_current_scale_pixels_per_ms(self) -> None:
        session = EditorSession()
        session.seek_song(100.0)
        session.set_scale_pixels_per_ms(1.0)

        session.scrub_timeline_by_wheel(1.0)

        self.assertEqual(session.timeline_geometry.scale_pixels_per_ms, 1.0)
        self.assertEqual(session._media_session.state.position_ms, 200)

    def test_editor_session_scrub_modifiers_keep_legacy_multipliers(self) -> None:
        session = EditorSession()
        session.set_scale_pixels_per_ms(0.5)

        session.seek_song(1000.0)
        session.scrub_timeline_by_wheel(1.0, alt_pressed=True)
        self.assertEqual(session._media_session.state.position_ms, 1020)

        session.seek_song(1000.0)
        session.scrub_timeline_by_wheel(1.0, ctrl_pressed=True)
        self.assertEqual(session._media_session.state.position_ms, 2200)

    def test_editor_session_scrub_accepts_positional_modifier_arguments(self) -> None:
        session = EditorSession()
        session.set_scale_pixels_per_ms(0.5)

        session.seek_song(1000.0)
        session.scrub_timeline_by_wheel(1.0, True, False)

        self.assertEqual(session._media_session.state.position_ms, 1020)

    def test_editor_session_seek_clamps_to_song_end_plus_three_seconds(self) -> None:
        session = EditorSession()
        session._media_session._state.duration_ms = 10_000

        session.seek_song(20_000)

        self.assertEqual(session._media_session.state.position_ms, 13_000)


if __name__ == "__main__":
    _ = unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.new_editor.core.legacy_rules import make_pending_long_note
from src.new_editor.core.models import Chart, Note
from src.new_editor.core.note_types import create_note_type, update_note_type
from src.new_editor.core.timeline import TimelineCopiedNote, TimelineCopyBuffer, TimelineToolState
from src.new_editor.ui.session import EditorSession


class NoteTypeLogicTests(unittest.TestCase):
    def test_create_note_type_adds_legacy_fields(self) -> None:
        chart = Chart()

        created = create_note_type(
            chart,
            name="Lift",
            color=(12, 34, 56),
            is_long_note=False,
            play_hitsound=False,
        )

        self.assertEqual(created.name, "Lift")
        self.assertEqual(chart.note_types["Lift"].color, (12, 34, 56))
        self.assertFalse(chart.note_types["Lift"].is_long_note)
        self.assertFalse(chart.note_types["Lift"].play_hitsound)

    def test_create_note_type_rejects_duplicate_name(self) -> None:
        chart = Chart()

        with self.assertRaises(ValueError):
            _ = create_note_type(
                chart,
                name="Tap",
                color=(255, 255, 255),
                is_long_note=False,
                play_hitsound=True,
            )

    def test_update_note_type_preserves_existing_name(self) -> None:
        chart = Chart()

        updated = update_note_type(
            chart,
            "Tap",
            name="Tap",
            color=(1, 2, 3),
            is_long_note=True,
            play_hitsound=False,
        )

        self.assertEqual(updated.note_type.name, "Tap")
        self.assertEqual(chart.note_types["Tap"].name, "Tap")
        self.assertEqual(chart.note_types["Tap"].color, (1, 2, 3))
        self.assertTrue(chart.note_types["Tap"].is_long_note)
        self.assertFalse(chart.note_types["Tap"].play_hitsound)
        self.assertFalse(updated.renamed)
        self.assertEqual(updated.affected_note_count, 0)

    def test_update_note_type_renames_key_and_migrates_existing_notes(self) -> None:
        chart = Chart(
            notes=[
                Note(time_ms=1000.0, note_type_name="Tap", lane=0),
                Note(time_ms=1500.0, note_type_name="Long", lane=1),
                Note(time_ms=2000.0, note_type_name="Tap", lane=2),
            ]
        )

        updated = update_note_type(
            chart,
            "Tap",
            name="AA",
            color=(7, 8, 9),
            is_long_note=False,
            play_hitsound=True,
        )

        self.assertTrue(updated.renamed)
        self.assertEqual(updated.affected_note_count, 2)
        self.assertNotIn("Tap", chart.note_types)
        self.assertIn("AA", chart.note_types)
        self.assertEqual(chart.note_types["AA"].name, "AA")
        self.assertEqual(chart.note_types["AA"].color, (7, 8, 9))
        self.assertEqual([note.note_type_name for note in chart.notes], ["AA", "Long", "AA"])

    def test_editor_session_rename_updates_selected_and_pending_long_note_type(self) -> None:
        session = EditorSession()
        session.set_current_note_type("Long")
        session._set_timeline_state(
            TimelineToolState(
                snap_division=session.timeline_state.snap_division,
                current_note_type_name="Long",
                quick_edit_lane_key_preset=session.timeline_state.quick_edit_lane_key_preset,
                pending_long_note=make_pending_long_note(500.0, 1, "Long"),
                pending_long_notes=(make_pending_long_note(750.0, 2, "Long"),),
                copy_buffer=TimelineCopyBuffer(
                    source_start_time_ms=500.0,
                    notes=(
                        TimelineCopiedNote(
                            time_offset_ms=0.0,
                            lane=1,
                            note_type_name="Long",
                            end_time_offset_ms=250.0,
                        ),
                    ),
                ),
            )
        )

        session.update_note_type(
            "Long",
            name="AA Long",
            color=(10, 20, 30),
            is_long_note=True,
            play_hitsound=False,
        )

        self.assertEqual(session.timeline_state.current_note_type_name, "AA Long")
        self.assertIsNotNone(session.timeline_state.pending_long_note)
        assert session.timeline_state.pending_long_note is not None
        self.assertEqual(session.timeline_state.pending_long_note.type_name, "AA Long")
        self.assertEqual(session.timeline_state.pending_long_notes[0].type_name, "AA Long")
        assert session.timeline_state.copy_buffer is not None
        self.assertEqual(session.timeline_state.copy_buffer.notes[0].note_type_name, "AA Long")
        self.assertIn("AA Long", session.chart.note_types)
        self.assertNotIn("Long", session.chart.note_types)

    def test_editor_session_selects_new_note_type_for_placement(self) -> None:
        session = EditorSession()

        session.create_note_type(
            name="Slide",
            color=(9, 99, 199),
            is_long_note=True,
            play_hitsound=True,
        )

        self.assertEqual(session.timeline_state.current_note_type_name, "Slide")
        self.assertIn("Slide", session.chart.note_types)

    def test_editor_session_import_marks_session_dirty_and_autosaves_to_sidecar(self) -> None:
        session = EditorSession()

        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_path = Path(tmpdir) / "legacy_source.json"
            _ = legacy_path.write_text(
                json.dumps(
                    {
                        "AudioFilePath": "songs/legacy.wav",
                        "Bpm": 120,
                        "LaneCount": 4,
                        "AudioOffset": 0,
                        "NormalNoteTools": [{"Name": "Legacy Tap", "Color": "#ABCDEF", "Type": 0}],
                        "Notes": [{"Time": 2.0, "Lane": 1, "NoteToolName": "Legacy Tap"}],
                    }
                ),
                encoding="utf-8",
            )

            session.import_legacy_chart(legacy_path)
            autosave_result = session.autosave_if_needed()

            self.assertTrue(session.is_dirty)
            self.assertEqual(session.chart.chart_path, "")
            self.assertEqual(session.suggested_save_name, "legacy_source_chart.json")
            self.assertIsNotNone(autosave_result)
            assert autosave_result is not None
            self.assertTrue(autosave_result.path.exists())
            self.assertEqual(autosave_result.path.name, "legacy_source.autosave.chart.json")


if __name__ == "__main__":
    _ = unittest.main()

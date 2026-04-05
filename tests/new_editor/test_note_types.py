from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.new_editor.core.models import Chart
from src.new_editor.core.note_types import create_note_type, update_note_type
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
            color=(1, 2, 3),
            is_long_note=True,
            play_hitsound=False,
        )

        self.assertEqual(updated.name, "Tap")
        self.assertEqual(chart.note_types["Tap"].name, "Tap")
        self.assertEqual(chart.note_types["Tap"].color, (1, 2, 3))
        self.assertTrue(chart.note_types["Tap"].is_long_note)
        self.assertFalse(chart.note_types["Tap"].play_hitsound)

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
            legacy_path.write_text(
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
    unittest.main()

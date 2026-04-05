from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.new_editor.core.models import Chart, Note
from src.new_editor.services.session_io import (
    autosave_chart_file,
    autosave_chart_path_for,
    clear_autosave_file,
    import_legacy_chart_file,
    load_chart_file,
    load_recovery_chart_file,
    recovery_paths_for,
    save_chart_file,
)


class SessionIoTests(unittest.TestCase):
    def test_save_and_reload_chart(self) -> None:
        chart = Chart()
        chart.notes.append(Note(time_ms=500.0, note_type_name="Tap", lane=0))

        with tempfile.TemporaryDirectory() as tmpdir:
            chart_path = Path(tmpdir) / "chart.json"
            result = save_chart_file(chart, chart_path)
            self.assertTrue(result.path.exists())

            reloaded = load_chart_file(chart_path)
            self.assertEqual(len(reloaded.notes), 1)
            self.assertEqual(reloaded.notes[0].time_ms, 500.0)

    def test_save_creates_backup_when_replacing_existing_file(self) -> None:
        chart = Chart()
        with tempfile.TemporaryDirectory() as tmpdir:
            chart_path = Path(tmpdir) / "chart.json"
            save_chart_file(chart, chart_path)

            chart.notes.append(Note(time_ms=750.0, note_type_name="Tap", lane=1))
            result = save_chart_file(chart, chart_path)

            self.assertIsNotNone(result.backup_path)
            assert result.backup_path is not None
            self.assertTrue(result.backup_path.exists())

    def test_import_legacy_chart_file_converts_without_reusing_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_path = Path(tmpdir) / "input_chart.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "AudioFilePath": "songs/demo.ogg",
                        "Bpm": 150,
                        "AudioOffset": 0.5,
                        "LaneCount": 4,
                        "NormalNoteTools": [{"Name": "Normal", "Color": "#112233", "Type": 0}],
                        "Notes": [{"Time": 1.25, "Lane": 3, "NoteToolName": "Normal"}],
                    }
                ),
                encoding="utf-8",
            )

            chart = import_legacy_chart_file(legacy_path)

            self.assertEqual(chart.chart_path, "")
            self.assertEqual(chart.song_path, "songs/demo.ogg")
            self.assertEqual(chart.offset_ms, 500.0)
            self.assertEqual(chart.notes[0].time_ms, 1250.0)
            self.assertEqual(chart.notes[0].lane, 3)

    def test_autosave_writes_separate_recovery_snapshot_and_can_be_reloaded(self) -> None:
        chart = Chart()
        with tempfile.TemporaryDirectory() as tmpdir:
            chart_path = Path(tmpdir) / "chart.json"
            save_chart_file(chart, chart_path)

            chart.notes.append(Note(time_ms=875.0, note_type_name="Tap", lane=2))
            result = autosave_chart_file(chart, chart_path)

            self.assertEqual(result.path, autosave_chart_path_for(chart_path))
            self.assertIsNone(result.backup_path)
            self.assertTrue(result.path.exists())

            recovery = recovery_paths_for(chart_path)
            self.assertEqual(recovery.autosave_path, result.path)

            reloaded = load_recovery_chart_file(result.path, chart_path=chart_path)
            self.assertEqual(reloaded.chart_path, str(chart_path))
            self.assertEqual(len(reloaded.notes), 1)
            self.assertEqual(reloaded.notes[0].time_ms, 875.0)

            clear_autosave_file(chart_path)
            self.assertFalse(result.path.exists())


if __name__ == "__main__":
    unittest.main()

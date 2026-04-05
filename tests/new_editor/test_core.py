from __future__ import annotations

import unittest

from src.new_editor.core.legacy_import import chart_from_legacy_source_data
from src.new_editor.core.legacy_json import chart_from_json_data, chart_from_json_text, chart_to_json_text
from src.new_editor.core.legacy_rules import (
    DELETE_TIME_TOLERANCE_MS,
    finalize_long_note,
    find_note_to_delete,
    make_pending_long_note,
    snap_time_to_grid,
)
from src.new_editor.core.models import Chart, Note


class LegacyCoreTests(unittest.TestCase):
    def test_delete_tolerance_matches_legacy(self) -> None:
        self.assertEqual(DELETE_TIME_TOLERANCE_MS, 50.0)

    def test_finalize_long_note_swaps_backwards_endpoint(self) -> None:
        pending = make_pending_long_note(2000.0, 1, "Long")
        note = finalize_long_note(pending, 1500.0)
        self.assertEqual(note.time_ms, 1500.0)
        self.assertEqual(note.end_time_ms, 2000.0)

    def test_find_note_to_delete_uses_raw_tolerance(self) -> None:
        note = Note(time_ms=1000.0, note_type_name="Tap", lane=0)
        self.assertIsNotNone(find_note_to_delete([note], lane=0, raw_time_ms=1049.0))
        self.assertIsNone(find_note_to_delete([note], lane=0, raw_time_ms=1051.0))

    def test_chart_round_trip_preserves_note_data(self) -> None:
        chart = Chart()
        chart.notes.append(Note(time_ms=1000.0, note_type_name="Tap", lane=0))
        loaded = chart_from_json_text(chart_to_json_text(chart))
        self.assertEqual(len(loaded.notes), 1)
        self.assertEqual(loaded.notes[0].lane, 0)

    def test_missing_note_types_restore_legacy_defaults(self) -> None:
        chart = chart_from_json_data({"notes": []})
        self.assertIn("Tap", chart.note_types)
        self.assertIn("Long", chart.note_types)

    def test_invalid_note_types_payload_raises(self) -> None:
        with self.assertRaises(TypeError):
            chart_from_json_data({"note_types": []})

    def test_legacy_source_import_matches_grounded_parser_mapping(self) -> None:
        chart = chart_from_legacy_source_data(
            {
                "AudioFilePath": "songs/legacy.wav",
                "Bpm": 163,
                "AudioOffset": 0.125,
                "LaneCount": 5,
                "NormalNoteTools": [{"Name": "Normal 노트 1", "Color": "#C8960F", "Type": 0}],
                "AttackNoteTools": [{"Name": "Attack 노트 1", "Color": "#FF0100", "Type": 1}],
                "TriggerNoteTools": [{"Name": "Trigger 노트 1", "Color": "broken", "Type": 2}],
                "Notes": [
                    {"Time": 2.5, "Lane": 2, "NoteToolName": "Normal 노트 1"},
                    {"Time": 3.75, "Lane": 1, "NoteToolName": "Attack 노트 1"},
                    {"Time": 5.0, "Lane": 0},
                ],
            }
        )

        self.assertEqual(chart.song_path, "songs/legacy.wav")
        self.assertEqual(chart.bpm, 163.0)
        self.assertEqual(chart.offset_ms, 125.0)
        self.assertEqual(chart.num_lanes, 5)
        self.assertEqual(chart.note_types["Normal 노트 1"].color, (200, 150, 15))
        self.assertFalse(chart.note_types["Normal 노트 1"].is_long_note)
        self.assertTrue(chart.note_types["Attack 노트 1"].is_long_note)
        self.assertTrue(chart.note_types["Trigger 노트 1"].is_long_note)
        self.assertEqual(chart.note_types["Trigger 노트 1"].color, (255, 255, 255))
        self.assertEqual(chart.notes[0].time_ms, 2500.0)
        self.assertEqual(chart.notes[1].time_ms, 3750.0)
        self.assertEqual(chart.notes[2].note_type_name, "해류탄막")
        self.assertIsNone(chart.notes[0].end_time_ms)

    def test_snap_time_returns_numeric_value(self) -> None:
        snapped = snap_time_to_grid(187.0, bpm=120.0, snap_division=16)
        self.assertIsInstance(snapped, float)


if __name__ == "__main__":
    unittest.main()

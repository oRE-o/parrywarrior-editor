from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.new_editor.core.hitsounds import (
    build_hitsound_event_times,
    default_hitsound_path,
    has_hitsound_crossing,
    hitsound_crossings,
    hitsound_status_text,
)
from src.new_editor.core.models import Chart, Note, NoteType


class HitsoundLogicTests(unittest.TestCase):
    def test_hitsound_crossings_respect_note_type_flag(self) -> None:
        chart = Chart(
            note_types={
                "Tap": NoteType("Tap", (255, 80, 80), False, True),
                "Silent": NoteType("Silent", (80, 80, 80), False, False),
            },
            notes=[
                Note(time_ms=100.0, note_type_name="Tap", lane=0),
                Note(time_ms=120.0, note_type_name="Silent", lane=1),
            ],
        )

        self.assertEqual(hitsound_crossings(chart, 90.0, 130.0), (100.0,))

    def test_hitsound_crossings_include_long_note_end_and_dedupe_shared_times(self) -> None:
        chart = Chart(
            note_types={
                "Long": NoteType("Long", (80, 80, 255), True, True),
                "Tap": NoteType("Tap", (255, 80, 80), False, True),
            },
            notes=[
                Note(time_ms=200.0, note_type_name="Long", lane=0, end_time_ms=400.0),
                Note(time_ms=400.0, note_type_name="Tap", lane=1),
            ],
        )

        self.assertEqual(hitsound_crossings(chart, 150.0, 450.0), (200.0, 400.0))

    def test_hitsound_crossings_ignore_non_forward_windows(self) -> None:
        chart = Chart(notes=[Note(time_ms=100.0, note_type_name="Tap", lane=0)])

        self.assertEqual(hitsound_crossings(chart, 200.0, 100.0), ())
        self.assertEqual(hitsound_crossings(chart, 100.0, 100.0), ())

    def test_prebuilt_hitsound_event_times_and_crossing_check(self) -> None:
        chart = Chart(
            note_types={
                "Tap": NoteType("Tap", (255, 80, 80), False, True),
                "Silent": NoteType("Silent", (80, 80, 80), False, False),
            },
            notes=[
                Note(time_ms=100.0, note_type_name="Tap", lane=0),
                Note(time_ms=220.0, note_type_name="Silent", lane=1),
                Note(time_ms=300.0, note_type_name="Tap", lane=2, end_time_ms=450.0),
            ],
        )

        event_times = build_hitsound_event_times(chart)

        self.assertEqual(event_times, (100.0, 300.0, 450.0))
        self.assertTrue(has_hitsound_crossing(event_times, 90.0, 110.0))
        self.assertFalse(has_hitsound_crossing(event_times, 110.0, 200.0))
        self.assertTrue(has_hitsound_crossing(event_times, 310.0, 460.0))

    def test_default_hitsound_path_points_to_shared_legacy_asset(self) -> None:
        hitsound_path = default_hitsound_path()

        self.assertEqual(hitsound_path.name, "hitsound.wav")
        self.assertIn("legacy/pygame_editor/assets", hitsound_path.as_posix())

    def test_default_hitsound_path_prefers_bundled_asset_when_available(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bundled_hitsound_path = Path(tmpdir) / "legacy" / "pygame_editor" / "assets" / "hitsound.wav"
            bundled_hitsound_path.parent.mkdir(parents=True, exist_ok=True)
            bundled_hitsound_path.write_bytes(b"RIFF")

            with patch("sys._MEIPASS", tmpdir, create=True):
                self.assertEqual(default_hitsound_path(), bundled_hitsound_path)

    def test_default_hitsound_path_falls_back_to_source_asset_when_bundled_file_is_missing(self) -> None:
        with TemporaryDirectory() as tmpdir:
            with patch("sys._MEIPASS", tmpdir, create=True):
                hitsound_path = default_hitsound_path()

        self.assertEqual(hitsound_path.name, "hitsound.wav")
        self.assertIn("legacy/pygame_editor/assets", hitsound_path.as_posix())
        self.assertNotIn(tmpdir, str(hitsound_path))

    def test_hitsound_status_text_is_truthful_when_missing(self) -> None:
        status = hitsound_status_text(source_path="/tmp/missing.wav", is_ready=False, error_message="missing on disk")

        self.assertIn("unavailable", status)
        self.assertIn("missing on disk", status)


if __name__ == "__main__":
    unittest.main()

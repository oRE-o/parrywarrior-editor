from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.new_editor.core.media import MediaState
from src.new_editor.services.media_session import WaveformExtractor
from src.new_editor.services.media_session import MediaSessionService
from src.new_editor.ui.panels import TransportPanel
from src.new_editor.ui.session import EditorSession


class WaveformExtractorTests(unittest.TestCase):
    def test_extract_wav_waveform_generates_peaks(self) -> None:
        extractor = WaveformExtractor(target_points=64)
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "tone.wav"
            self._write_test_wav(wav_path)

            waveform = extractor.extract(wav_path)

            self.assertTrue(waveform.is_available)
            self.assertGreater(len(waveform.peak_values), 0)
            self.assertEqual(len(waveform.min_values), len(waveform.peak_values))
            self.assertEqual(len(waveform.max_values), len(waveform.peak_values))
            self.assertEqual(waveform.channel_count, 1)
            self.assertIsNone(waveform.limitation)

    def test_default_waveform_extractor_keeps_high_fidelity_point_budget(self) -> None:
        extractor = WaveformExtractor()

        self.assertGreaterEqual(extractor._target_points, 65536)

    def test_non_wav_file_reports_truthful_limitation(self) -> None:
        extractor = WaveformExtractor()
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_mp3 = Path(tmpdir) / "song.mp3"
            fake_mp3.write_bytes(b"not-real-mp3")

            waveform = extractor.extract(fake_mp3)

            self.assertFalse(waveform.is_available)
            self.assertIsNotNone(waveform.limitation)
            assert waveform.limitation is not None
            self.assertGreater(len(waveform.limitation), 0)

    def _write_test_wav(self, path: Path) -> None:
        sample_count = 2048
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            frames = bytearray()
            for index in range(sample_count):
                amplitude = 12000 if index % 2 == 0 else -12000
                frames.extend(int(amplitude).to_bytes(2, byteorder="little", signed=True))
            handle.writeframes(bytes(frames))


class MediaSessionServiceTests(unittest.TestCase):
    def test_separate_song_and_hitsound_volume_are_tracked_independently(self) -> None:
        service = MediaSessionService()

        service.set_song_volume(0.2)
        service.set_hitsound_volume(0.85)

        self.assertEqual(service.state.volume, 0.2)
        self.assertEqual(service.state.hitsound_volume, 0.85)

    def test_clear_song_preserves_audio_levels_and_hitsound_status(self) -> None:
        service = MediaSessionService()

        service.set_song_volume(0.25)
        service.set_hitsound_volume(0.6)
        service.load_hitsound("/tmp/missing-hitsound.wav")
        service.clear_song()

        self.assertEqual(service.state.volume, 0.25)
        self.assertEqual(service.state.hitsound_volume, 0.6)
        self.assertEqual(service.state.hitsound.source_path, "/tmp/missing-hitsound.wav")


class EditorSessionMediaTests(unittest.TestCase):
    def test_session_routes_hitsound_volume_without_changing_song_volume(self) -> None:
        session = EditorSession()
        media_states: list[MediaState] = []
        session.media_state_changed.connect(media_states.append)

        session.emit_initial_state()
        session.set_song_volume(0.45)
        session.set_hitsound_volume(0.8)

        self.assertGreaterEqual(len(media_states), 3)
        self.assertEqual(media_states[-1].volume, 0.45)
        self.assertEqual(media_states[-1].hitsound_volume, 0.8)


class TransportPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_transport_panel_shows_separate_song_and_hitsound_volume_values(self) -> None:
        panel = TransportPanel()

        panel.update_media_state(MediaState(volume=0.3, hitsound_volume=0.8))

        self.assertEqual(panel.song_volume_slider.value(), 30)
        self.assertEqual(panel.song_volume_label.text(), "30")
        self.assertEqual(panel.hitsound_volume_slider.value(), 80)
        self.assertEqual(panel.hitsound_volume_label.text(), "80")


if __name__ == "__main__":
    unittest.main()

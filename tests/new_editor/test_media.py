from __future__ import annotations

import tempfile
import unittest
import wave
from pathlib import Path

from src.new_editor.services.media_session import WaveformExtractor


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


if __name__ == "__main__":
    unittest.main()

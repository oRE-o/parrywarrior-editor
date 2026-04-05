from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import time
import wave
from array import array
from pathlib import Path
from typing import Any, cast

try:
    import imageio_ffmpeg
except ModuleNotFoundError:
    imageio_ffmpeg = None


class _FallbackQtSignalProxy:
    def __init__(self) -> None:
        self._callbacks: list[object] = []

    def connect(self, *_args: object, **_kwargs: object) -> None:
        callback = _args[0] if _args else None
        if callback is not None:
            self._callbacks.append(callback)

    def emit(self, *_args: object, **_kwargs: object) -> None:
        for callback in list(self._callbacks):
            if callable(callback):
                callback(*_args, **_kwargs)


try:
    from PySide6.QtCore import QObject as _QObject, QTimer as _QTimer, QUrl as _QUrl, Signal as _Signal
    from PySide6.QtMultimedia import QAudioOutput as _QAudioOutput, QMediaPlayer as _QMediaPlayer, QSoundEffect as _QSoundEffect

    QObject = cast(Any, _QObject)
    QTimer = cast(Any, _QTimer)
    QUrl = cast(Any, _QUrl)
    Signal = cast(Any, _Signal)
    QAudioOutput = cast(Any, _QAudioOutput)
    QMediaPlayer = cast(Any, _QMediaPlayer)
    QSoundEffect = cast(Any, _QSoundEffect)

    _qt_import_error: ModuleNotFoundError | None = None
except ModuleNotFoundError as exc:
    class QObject:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

    class QUrl:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

        @staticmethod
        def fromLocalFile(path: str) -> str:
            return path

    def _missing_signal_factory(*_args: object, **_kwargs: object) -> _FallbackQtSignalProxy:
        return _FallbackQtSignalProxy()

    class QTimer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise ModuleNotFoundError("PySide6 is required to use MediaSessionService.") from exc

    class QAudioOutput:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise ModuleNotFoundError("PySide6 is required to use MediaSessionService.") from exc

    class QMediaPlayer:
        class PlaybackState:
            PlayingState = object()
            PausedState = object()

        class Error:
            NoError = object()

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise ModuleNotFoundError("PySide6 is required to use MediaSessionService.") from exc

    class QSoundEffect:
        class Status:
            Null = object()
            Loading = object()
            Ready = object()
            Error = object()

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise ModuleNotFoundError("PySide6 is required to use MediaSessionService.") from exc

    QObject = cast(Any, QObject)
    QTimer = cast(Any, QTimer)
    QUrl = cast(Any, QUrl)
    Signal = cast(Any, _missing_signal_factory)
    QAudioOutput = cast(Any, QAudioOutput)
    QMediaPlayer = cast(Any, QMediaPlayer)
    QSoundEffect = cast(Any, QSoundEffect)

    _qt_import_error = exc

from ..core.media import HitsoundState, MediaState, PlaybackState, WaveformData


SMOOTH_POSITION_INTERVAL_MS = 8
FFMPEG_WAVEFORM_SAMPLE_RATE = 44100
MAX_SEEK_PADDING_MS = 3000


class WaveformExtractor:
    def __init__(self, *, target_points: int = 65536) -> None:
        self._target_points = max(8192, target_points)
        self._cache: dict[Path, WaveformData] = {}

    def extract(self, path: str | Path) -> WaveformData:
        source = Path(path).expanduser()
        cache_key = source.resolve(strict=False)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        if not source.exists():
            waveform = WaveformData(
                source_path=str(source),
                limitation="Waveform preview unavailable because the song file does not exist.",
            )
            self._cache[cache_key] = waveform
            return waveform

        if source.suffix.lower() not in {".wav", ".wave"}:
            waveform = self._extract_ffmpeg_waveform(source)
            self._cache[cache_key] = waveform
            return waveform

        waveform = self._extract_wav_waveform(source)
        if waveform.is_available:
            self._cache[cache_key] = waveform
            return waveform

        waveform = self._extract_ffmpeg_waveform(source)
        self._cache[cache_key] = waveform
        return waveform

    def clear(self) -> None:
        self._cache.clear()

    def _extract_ffmpeg_waveform(self, source: Path) -> WaveformData:
        ffmpeg_path = _resolve_ffmpeg_executable()
        if ffmpeg_path is None:
            return WaveformData(
                source_path=str(source),
                limitation="Waveform preview unavailable because the bundled ffmpeg executable could not be found.",
            )

        command = [
            ffmpeg_path,
            "-v",
            "error",
            "-i",
            str(source),
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            str(FFMPEG_WAVEFORM_SAMPLE_RATE),
            "-",
        ]

        try:
            completed = subprocess.run(command, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            error_message = ""
            if isinstance(exc, subprocess.CalledProcessError):
                error_message = exc.stderr.decode("utf-8", errors="ignore").strip()
            return WaveformData(
                source_path=str(source),
                limitation=error_message or "Waveform preview could not decode this audio file via ffmpeg.",
            )

        raw_pcm = completed.stdout
        if len(raw_pcm) < 2:
            return WaveformData(
                source_path=str(source),
                limitation="Waveform preview unavailable because ffmpeg returned no audio samples.",
            )

        samples = array("h")
        samples.frombytes(raw_pcm[: len(raw_pcm) - (len(raw_pcm) % 2)])
        if sys.byteorder != "little":
            samples.byteswap()

        return _waveform_from_pcm_samples(
            source=source,
            samples=samples,
            sample_rate_hz=FFMPEG_WAVEFORM_SAMPLE_RATE,
            channel_count=1,
            target_points=self._target_points,
        )

    def _extract_wav_waveform(self, source: Path) -> WaveformData:
        with wave.open(str(source), "rb") as handle:
            sample_rate_hz = handle.getframerate()
            frame_count = handle.getnframes()
            channel_count = handle.getnchannels()
            sample_width = handle.getsampwidth()
            compression_type = handle.getcomptype()

            if compression_type != "NONE":
                return WaveformData(
                    source_path=str(source),
                    sample_rate_hz=sample_rate_hz,
                    channel_count=channel_count,
                    duration_ms=_frames_to_duration_ms(frame_count, sample_rate_hz),
                    limitation="Waveform preview currently requires PCM WAV data without compression.",
                )

            if sample_width not in {1, 2, 3, 4}:
                return WaveformData(
                    source_path=str(source),
                    sample_rate_hz=sample_rate_hz,
                    channel_count=channel_count,
                    duration_ms=_frames_to_duration_ms(frame_count, sample_rate_hz),
                    limitation=f"Waveform preview does not yet support {sample_width * 8}-bit WAV samples.",
                )

            duration_ms = _frames_to_duration_ms(frame_count, sample_rate_hz)
            if frame_count <= 0 or sample_rate_hz <= 0 or channel_count <= 0:
                return WaveformData(
                    source_path=str(source),
                    duration_ms=duration_ms,
                    sample_rate_hz=sample_rate_hz,
                    channel_count=channel_count,
                    limitation="Waveform preview unavailable because the WAV file has no decodable audio frames.",
                )

            frames_per_bucket = max(1, math.ceil(frame_count / self._target_points))
            bytes_per_frame = sample_width * channel_count
            normalizer = _sample_normalizer(sample_width)
            peaks: list[float] = []
            min_values: list[float] = []
            max_values: list[float] = []
            bucket_peak = 0.0
            bucket_min = 1.0
            bucket_max = -1.0
            bucket_frames = 0

            while True:
                raw_frames = handle.readframes(min(4096, frame_count))
                if not raw_frames:
                    break

                usable_length = len(raw_frames) - (len(raw_frames) % bytes_per_frame)
                buffer = memoryview(raw_frames[:usable_length])
                for frame_offset in range(0, usable_length, bytes_per_frame):
                    frame_peak = 0.0
                    for channel_index in range(channel_count):
                        sample_offset = frame_offset + (channel_index * sample_width)
                        sample = _decode_sample(buffer[sample_offset : sample_offset + sample_width], sample_width)
                        normalized = sample / normalizer
                        frame_peak = max(frame_peak, abs(normalized))
                        bucket_min = min(bucket_min, normalized)
                        bucket_max = max(bucket_max, normalized)
                    bucket_peak = max(bucket_peak, frame_peak)
                    bucket_frames += 1
                    if bucket_frames >= frames_per_bucket:
                        peaks.append(min(bucket_peak, 1.0))
                        min_values.append(max(-1.0, bucket_min))
                        max_values.append(min(1.0, bucket_max))
                        bucket_peak = 0.0
                        bucket_min = 1.0
                        bucket_max = -1.0
                        bucket_frames = 0

            if bucket_frames > 0:
                peaks.append(min(bucket_peak, 1.0))
                min_values.append(max(-1.0, bucket_min))
                max_values.append(min(1.0, bucket_max))

            return WaveformData(
                source_path=str(source),
                peak_values=peaks,
                min_values=min_values,
                max_values=max_values,
                duration_ms=duration_ms,
                sample_rate_hz=sample_rate_hz,
                channel_count=channel_count,
                points_per_second=(len(peaks) / (duration_ms / 1000.0)) if duration_ms > 0 else 0.0,
            )


if _qt_import_error is None:
    class MediaSessionService(QObject):
        media_state_changed = Signal(object)
        waveform_changed = Signal(object)

        def __init__(self, *, waveform_extractor: WaveformExtractor | None = None) -> None:
            super().__init__()
            self._audio_output: Any = QAudioOutput(self)
            self._player: Any = QMediaPlayer(self)
            self._hitsound_effect: Any = QSoundEffect(self)
            self._player.setAudioOutput(self._audio_output)
            self._smooth_position_timer: Any = QTimer(self)
            self._smooth_position_timer.setInterval(SMOOTH_POSITION_INTERVAL_MS)
            self._smooth_position_timer.timeout.connect(self._refresh_playback_position)
            self._waveform_extractor = waveform_extractor or WaveformExtractor()
            self._state = MediaState()
            self._playback_anchor_position_ms = 0.0
            self._playback_anchor_monotonic = time.monotonic()
            self._audio_output.setVolume(self._state.volume)

            self._player.playbackStateChanged.connect(self._handle_playback_state_changed)
            self._player.positionChanged.connect(self._handle_position_changed)
            self._player.durationChanged.connect(self._handle_duration_changed)
            self._player.errorOccurred.connect(self._handle_error_occurred)
            self._hitsound_effect.statusChanged.connect(self._handle_hitsound_status_changed)
            self._hitsound_effect.setVolume(0.35)

        @property
        def state(self) -> MediaState:
            return self._copy_state()

        def emit_initial_state(self) -> None:
            self.media_state_changed.emit(self.state)
            self.waveform_changed.emit(self.state.waveform)

        def load_song(self, path: str | Path) -> None:
            source = Path(path).expanduser()
            self.stop()
            self._state.song_path = str(source)
            self._state.error_message = None
            self._state.position_ms = 0
            self._state.duration_ms = 0
            self._set_playback_anchor(0.0)

            waveform = self._waveform_extractor.extract(source)
            self._state.waveform = waveform

            if source.exists():
                self._player.setSource(QUrl.fromLocalFile(str(source.resolve())))
                self._state.can_play = True
                self._state.can_stop = False
            else:
                self._player.setSource(QUrl())
                self._state.can_play = False
                self._state.can_stop = False
                self._state.error_message = "The linked song file could not be found on disk."

            self._emit_state_changed(emit_waveform=True)

        def clear_song(self) -> None:
            self.stop()
            self._player.setSource(QUrl())
            hitsound = self._state.hitsound
            self._state = MediaState(
                hitsound=HitsoundState(
                    source_path=hitsound.source_path,
                    is_ready=hitsound.is_ready,
                    error_message=hitsound.error_message,
                )
            )
            self._emit_state_changed(emit_waveform=True)

        def load_hitsound(self, path: str | Path) -> None:
            source = Path(path).expanduser()
            self._hitsound_effect.stop()
            self._state.hitsound = HitsoundState(source_path=str(source), is_ready=False, error_message=None)
            if not source.exists():
                self._hitsound_effect.setSource(QUrl())
                self._state.hitsound.error_message = "the shared hitsound file could not be found on disk"
                self._emit_state_changed()
                return

            self._hitsound_effect.setSource(QUrl.fromLocalFile(str(source.resolve())))
            self._emit_state_changed()

        def play_hitsound(self) -> bool:
            if not self._state.hitsound.is_ready:
                return False
            self._hitsound_effect.play()
            return True

        def toggle_play_pause(self) -> None:
            if not self._state.can_play:
                return
            if self._state.playback_state == PlaybackState.PLAYING:
                self._player.pause()
                return
            self._player.play()

        def seek(self, position_ms: int | float) -> None:
            target_position_ms = self._clamp_seek_position_ms(position_ms)
            effective_duration_ms = self._effective_duration_ms()
            if self._state.song_path:
                self._player.setPosition(min(target_position_ms, effective_duration_ms))
            self._set_playback_anchor(float(target_position_ms))
            if not self._set_position_ms(target_position_ms):
                return
            self._emit_state_changed()

        def set_volume(self, volume: float) -> None:
            safe_volume = min(1.0, max(0.0, float(volume)))
            if self._state.volume == safe_volume:
                return
            self._state.volume = safe_volume
            self._audio_output.setVolume(safe_volume)
            self._emit_state_changed()

        def stop(self) -> None:
            self._smooth_position_timer.stop()
            self._player.stop()
            self._state.position_ms = 0
            self._state.can_stop = False
            self._set_playback_anchor(0.0)
            self._emit_state_changed()

        def _handle_playback_state_changed(self, state: object) -> None:
            self._state.playback_state = _playback_state_from_qt(state)
            self._state.can_play = bool(self._state.song_path)
            if self._state.playback_state == PlaybackState.PLAYING:
                self._set_playback_anchor(float(self._player.position()))
                self._smooth_position_timer.start()
            else:
                self._smooth_position_timer.stop()
                current_position = self._player.position()
                if self._state.position_ms > self._effective_duration_ms() >= 0 and current_position <= self._effective_duration_ms():
                    self._set_playback_anchor(float(self._state.position_ms))
                else:
                    self._set_playback_anchor(float(current_position))
                    self._set_position_ms(current_position)
            self._state.can_stop = self._state.playback_state != PlaybackState.STOPPED or self._state.position_ms > 0
            self._emit_state_changed()

        def _handle_position_changed(self, position_ms: int) -> None:
            effective_duration_ms = self._effective_duration_ms()
            if self._state.position_ms > effective_duration_ms > 0 and position_ms <= effective_duration_ms:
                return
            self._set_playback_anchor(float(position_ms))
            if self._state.playback_state == PlaybackState.PLAYING:
                return
            self._set_position_ms(position_ms)
            self._emit_state_changed()

        def _handle_duration_changed(self, duration_ms: int) -> None:
            self._state.duration_ms = max(0, int(duration_ms))
            self._emit_state_changed()

        def _handle_error_occurred(self, *_args: object) -> None:
            error_text = self._player.errorString().strip()
            self._state.error_message = error_text or "Qt Multimedia could not load or play the linked song."
            self._state.can_play = False
            self._state.can_stop = False
            self._emit_state_changed()

        def _handle_hitsound_status_changed(self) -> None:
            hitsound = self._state.hitsound
            if not hitsound.source_path:
                return

            status = self._hitsound_effect.status()
            if status == QSoundEffect.Status.Ready:
                hitsound.is_ready = True
                hitsound.error_message = None
            elif status == QSoundEffect.Status.Error:
                hitsound.is_ready = False
                hitsound.error_message = "Qt Multimedia could not load the shared hitsound WAV file"
            elif status == QSoundEffect.Status.Null:
                hitsound.is_ready = False
                if hitsound.error_message is None:
                    hitsound.error_message = "the shared hitsound effect is not loaded"
            else:
                hitsound.is_ready = False
                if hitsound.error_message and "found on disk" in hitsound.error_message:
                    pass
                else:
                    hitsound.error_message = None
            self._emit_state_changed()

        def _emit_state_changed(self, *, emit_waveform: bool = False) -> None:
            state = self.state
            self.media_state_changed.emit(state)
            if emit_waveform:
                self.waveform_changed.emit(state.waveform)

        def _refresh_playback_position(self) -> None:
            if self._state.playback_state != PlaybackState.PLAYING:
                self._smooth_position_timer.stop()
                return
            elapsed_ms = (time.monotonic() - self._playback_anchor_monotonic) * 1000.0
            target_position_ms = self._playback_anchor_position_ms + elapsed_ms
            if self._state.duration_ms > 0:
                target_position_ms = min(float(self._state.duration_ms + MAX_SEEK_PADDING_MS), target_position_ms)
            if not self._set_position_ms(target_position_ms):
                return
            self._emit_state_changed()

        def _set_playback_anchor(self, position_ms: float) -> None:
            self._playback_anchor_position_ms = max(0.0, position_ms)
            self._playback_anchor_monotonic = time.monotonic()

        def _effective_duration_ms(self) -> int:
            if self._state.duration_ms > 0:
                return int(self._state.duration_ms)
            if self._state.waveform.duration_ms > 0:
                return int(round(self._state.waveform.duration_ms))
            return 0

        def _clamp_seek_position_ms(self, position_ms: int | float) -> int:
            safe_position_ms = max(0, int(round(position_ms)))
            effective_duration_ms = self._effective_duration_ms()
            if effective_duration_ms <= 0:
                return safe_position_ms
            return min(safe_position_ms, effective_duration_ms + MAX_SEEK_PADDING_MS)

        def _set_position_ms(self, position_ms: int | float) -> bool:
            safe_position_ms = max(0, int(round(position_ms)))
            if self._state.position_ms == safe_position_ms:
                self._state.can_stop = self._state.playback_state != PlaybackState.STOPPED or safe_position_ms > 0
                return False
            self._state.position_ms = safe_position_ms
            self._state.can_stop = self._state.playback_state != PlaybackState.STOPPED or safe_position_ms > 0
            return True

        def _copy_state(self) -> MediaState:
            waveform = self._state.waveform
            return MediaState(
                song_path=self._state.song_path,
                playback_state=self._state.playback_state,
                position_ms=self._state.position_ms,
                duration_ms=self._state.duration_ms,
                volume=self._state.volume,
                waveform=WaveformData(
                    source_path=waveform.source_path,
                    peak_values=waveform.peak_values,
                    min_values=waveform.min_values,
                    max_values=waveform.max_values,
                    duration_ms=waveform.duration_ms,
                    sample_rate_hz=waveform.sample_rate_hz,
                    channel_count=waveform.channel_count,
                    points_per_second=waveform.points_per_second,
                    limitation=waveform.limitation,
                ),
                hitsound=HitsoundState(
                    source_path=self._state.hitsound.source_path,
                    is_ready=self._state.hitsound.is_ready,
                    error_message=self._state.hitsound.error_message,
                ),
                can_play=self._state.can_play,
                can_stop=self._state.can_stop,
                error_message=self._state.error_message,
            )
else:
    class MediaSessionService:
        def __init__(self, *, waveform_extractor: WaveformExtractor | None = None) -> None:
            self.media_state_changed = _FallbackQtSignalProxy()
            self.waveform_changed = _FallbackQtSignalProxy()
            self._waveform_extractor = waveform_extractor or WaveformExtractor()
            self._state = MediaState()

        @property
        def state(self) -> MediaState:
            waveform = self._state.waveform
            return MediaState(
                song_path=self._state.song_path,
                playback_state=self._state.playback_state,
                position_ms=self._state.position_ms,
                duration_ms=self._state.duration_ms,
                volume=self._state.volume,
                waveform=WaveformData(
                    source_path=waveform.source_path,
                    peak_values=waveform.peak_values,
                    min_values=waveform.min_values,
                    max_values=waveform.max_values,
                    duration_ms=waveform.duration_ms,
                    sample_rate_hz=waveform.sample_rate_hz,
                    channel_count=waveform.channel_count,
                    points_per_second=waveform.points_per_second,
                    limitation=waveform.limitation,
                ),
                hitsound=HitsoundState(
                    source_path=self._state.hitsound.source_path,
                    is_ready=self._state.hitsound.is_ready,
                    error_message=self._state.hitsound.error_message,
                ),
                can_play=self._state.can_play,
                can_stop=self._state.can_stop,
                error_message=self._state.error_message,
            )

        def emit_initial_state(self) -> None:
            self.media_state_changed.emit(self.state)
            self.waveform_changed.emit(self.state.waveform)

        def load_song(self, path: str | Path) -> None:
            source = Path(path).expanduser()
            waveform = self._waveform_extractor.extract(source)
            self._state.song_path = str(source)
            self._state.position_ms = 0
            self._state.playback_state = PlaybackState.STOPPED
            self._state.waveform = waveform
            self._state.duration_ms = int(round(waveform.duration_ms)) if waveform.duration_ms > 0 else 0
            self._state.can_stop = False
            if source.exists():
                self._state.can_play = True
                self._state.error_message = None
            else:
                self._state.can_play = False
                self._state.error_message = "The linked song file could not be found on disk."
            self.media_state_changed.emit(self.state)
            self.waveform_changed.emit(self.state.waveform)

        def clear_song(self) -> None:
            hitsound = self._state.hitsound
            self._state = MediaState(
                hitsound=HitsoundState(
                    source_path=hitsound.source_path,
                    is_ready=hitsound.is_ready,
                    error_message=hitsound.error_message,
                )
            )
            self.media_state_changed.emit(self.state)
            self.waveform_changed.emit(self.state.waveform)

        def load_hitsound(self, path: str | Path) -> None:
            source = Path(path).expanduser()
            if source.exists():
                self._state.hitsound = HitsoundState(source_path=str(source), is_ready=True, error_message=None)
            else:
                self._state.hitsound = HitsoundState(
                    source_path=str(source),
                    is_ready=False,
                    error_message="the shared hitsound file could not be found on disk",
                )
            self.media_state_changed.emit(self.state)

        def play_hitsound(self) -> bool:
            return self._state.hitsound.is_ready

        def toggle_play_pause(self) -> None:
            if not self._state.can_play:
                return
            if self._state.playback_state == PlaybackState.PLAYING:
                self._state.playback_state = PlaybackState.PAUSED
            else:
                self._state.playback_state = PlaybackState.PLAYING
            self._state.can_stop = self._state.playback_state != PlaybackState.STOPPED or self._state.position_ms > 0
            self.media_state_changed.emit(self.state)

        def seek(self, position_ms: int | float) -> None:
            self._state.position_ms = self._clamp_seek_position_ms(position_ms)
            self._state.can_stop = self._state.playback_state != PlaybackState.STOPPED or self._state.position_ms > 0
            self.media_state_changed.emit(self.state)

        def stop(self) -> None:
            self._state.playback_state = PlaybackState.STOPPED
            self._state.position_ms = 0
            self._state.can_stop = False
            self.media_state_changed.emit(self.state)

        def _effective_duration_ms(self) -> int:
            if self._state.duration_ms > 0:
                return int(self._state.duration_ms)
            if self._state.waveform.duration_ms > 0:
                return int(round(self._state.waveform.duration_ms))
            return 0

        def _clamp_seek_position_ms(self, position_ms: int | float) -> int:
            safe_position_ms = max(0, int(round(position_ms)))
            effective_duration_ms = self._effective_duration_ms()
            if effective_duration_ms <= 0:
                return safe_position_ms
            return min(safe_position_ms, effective_duration_ms + MAX_SEEK_PADDING_MS)


def _frames_to_duration_ms(frame_count: int, sample_rate_hz: int) -> float:
    if frame_count <= 0 or sample_rate_hz <= 0:
        return 0.0
    return (frame_count / sample_rate_hz) * 1000.0


def _resolve_ffmpeg_executable() -> str | None:
    bundled_candidates = _bundled_ffmpeg_candidates()
    for candidate in bundled_candidates:
        if candidate.is_file() and _is_executable_file(candidate):
            return str(candidate)

    if imageio_ffmpeg is not None:
        try:
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg_path = None
        if ffmpeg_path:
            return ffmpeg_path

    return shutil.which("ffmpeg")


def _bundled_ffmpeg_candidates() -> tuple[Path, ...]:
    roots: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(str(meipass)))
    roots.append(Path(__file__).resolve().parents[3])

    names = ("ffmpeg", "ffmpeg.exe")
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for relative in (
            Path("third_party/ffmpeg"),
            Path("imageio_ffmpeg/binaries"),
            Path("ffmpeg"),
        ):
            for name in names:
                candidate = root / relative / name
                key = candidate.as_posix()
                if key not in seen:
                    seen.add(key)
                    candidates.append(candidate)
    return tuple(candidates)


def _is_executable_file(path: Path) -> bool:
    return path.exists() and path.is_file() and (os.access(path, os.X_OK) or path.suffix.lower() == ".exe")


def _waveform_from_pcm_samples(
    *,
    source: Path,
    samples: array,
    sample_rate_hz: int,
    channel_count: int,
    target_points: int,
) -> WaveformData:
    sample_count = len(samples)
    if sample_count <= 0 or sample_rate_hz <= 0:
        return WaveformData(
            source_path=str(source),
            sample_rate_hz=sample_rate_hz,
            channel_count=channel_count,
            limitation="Waveform preview unavailable because the decoded audio contains no samples.",
        )

    duration_ms = _frames_to_duration_ms(sample_count, sample_rate_hz)
    frames_per_bucket = max(1, math.ceil(sample_count / max(64, target_points)))
    peaks: list[float] = []
    min_values: list[float] = []
    max_values: list[float] = []
    bucket_peak = 0.0
    bucket_min = 1.0
    bucket_max = -1.0
    bucket_size = 0
    normalizer = 32768.0

    for sample in samples:
        normalized = sample / normalizer
        bucket_peak = max(bucket_peak, abs(normalized))
        bucket_min = min(bucket_min, normalized)
        bucket_max = max(bucket_max, normalized)
        bucket_size += 1
        if bucket_size >= frames_per_bucket:
            peaks.append(min(bucket_peak, 1.0))
            min_values.append(max(-1.0, bucket_min))
            max_values.append(min(1.0, bucket_max))
            bucket_peak = 0.0
            bucket_min = 1.0
            bucket_max = -1.0
            bucket_size = 0

    if bucket_size > 0:
        peaks.append(min(bucket_peak, 1.0))
        min_values.append(max(-1.0, bucket_min))
        max_values.append(min(1.0, bucket_max))

    return WaveformData(
        source_path=str(source),
        peak_values=peaks,
        min_values=min_values,
        max_values=max_values,
        duration_ms=duration_ms,
        sample_rate_hz=sample_rate_hz,
        channel_count=channel_count,
        points_per_second=(len(peaks) / (duration_ms / 1000.0)) if duration_ms > 0 else 0.0,
    )


def _sample_normalizer(sample_width: int) -> float:
    return {
        1: 128.0,
        2: 32768.0,
        3: 8388608.0,
        4: 2147483648.0,
    }[sample_width]


def _decode_sample(sample_bytes: memoryview, sample_width: int) -> int:
    raw = bytes(sample_bytes)
    if sample_width == 1:
        return raw[0] - 128
    return int.from_bytes(raw, byteorder="little", signed=True)


if _qt_import_error is None:
    def _playback_state_from_qt(state: object) -> PlaybackState:
        if state == QMediaPlayer.PlaybackState.PlayingState:
            return PlaybackState.PLAYING
        if state == QMediaPlayer.PlaybackState.PausedState:
            return PlaybackState.PAUSED
        return PlaybackState.STOPPED

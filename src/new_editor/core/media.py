from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PlaybackState(StrEnum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


@dataclass(slots=True)
class HitsoundState:
    source_path: str = ""
    is_ready: bool = False
    error_message: str | None = None


@dataclass(slots=True)
class WaveformData:
    source_path: str = ""
    peak_values: list[float] = field(default_factory=list)
    min_values: list[float] = field(default_factory=list)
    max_values: list[float] = field(default_factory=list)
    duration_ms: float = 0.0
    sample_rate_hz: int = 0
    channel_count: int = 0
    points_per_second: float = 0.0
    limitation: str | None = None

    @property
    def is_available(self) -> bool:
        return bool(self.source_path and self.peak_values)


@dataclass(slots=True)
class MediaState:
    song_path: str = ""
    playback_state: PlaybackState = PlaybackState.STOPPED
    position_ms: int = 0
    duration_ms: int = 0
    volume: float = 0.7
    hitsound_volume: float = 0.35
    waveform: WaveformData = field(default_factory=WaveformData)
    hitsound: HitsoundState = field(default_factory=HitsoundState)
    can_play: bool = False
    can_stop: bool = False
    error_message: str | None = None

    @property
    def is_song_loaded(self) -> bool:
        return bool(self.song_path)

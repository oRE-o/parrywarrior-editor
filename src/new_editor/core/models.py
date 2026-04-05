from __future__ import annotations

from dataclasses import dataclass, field


Color = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class NoteType:
    name: str
    color: Color
    is_long_note: bool
    play_hitsound: bool


@dataclass(frozen=True, slots=True)
class Note:
    time_ms: float
    note_type_name: str
    lane: int
    end_time_ms: float | None = None

    @property
    def is_long_note(self) -> bool:
        return self.end_time_ms is not None


@dataclass(frozen=True, slots=True)
class PendingLongNote:
    time_ms: float
    lane: int
    type_name: str


@dataclass(slots=True)
class Chart:
    song_path: str = ""
    chart_path: str = ""
    bpm: float = 120.0
    offset_ms: float = 0.0
    num_lanes: int = 4
    note_types: dict[str, NoteType] = field(default_factory=dict)
    notes: list[Note] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.note_types:
            self.note_types = default_note_types()


def default_note_types() -> dict[str, NoteType]:
    return {
        "Tap": NoteType("Tap", (255, 80, 80), False, True),
        "Long": NoteType("Long", (80, 80, 255), True, True),
    }

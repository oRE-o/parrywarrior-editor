from __future__ import annotations

from .models import Chart, Color, NoteType


LEGACY_NOTE_TYPE_PRESET_COLORS: tuple[Color, ...] = (
    (255, 80, 80),
    (80, 255, 80),
    (80, 80, 255),
    (255, 255, 80),
    (80, 255, 255),
    (255, 80, 255),
    (200, 200, 200),
    (255, 150, 80),
)


def create_note_type(
    chart: Chart,
    *,
    name: str,
    color: Color,
    is_long_note: bool,
    play_hitsound: bool,
) -> NoteType:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Note type name cannot be empty.")
    if normalized_name in chart.note_types:
        raise ValueError(f"A note type named '{normalized_name}' already exists.")

    note_type = NoteType(
        name=normalized_name,
        color=_normalize_color(color),
        is_long_note=bool(is_long_note),
        play_hitsound=bool(play_hitsound),
    )
    chart.note_types[normalized_name] = note_type
    return note_type


def update_note_type(
    chart: Chart,
    note_type_name: str,
    *,
    color: Color,
    is_long_note: bool,
    play_hitsound: bool,
) -> NoteType:
    existing_note_type = chart.note_types.get(note_type_name)
    if existing_note_type is None:
        raise KeyError(f"Unknown note type: {note_type_name}")

    updated_note_type = NoteType(
        name=existing_note_type.name,
        color=_normalize_color(color),
        is_long_note=bool(is_long_note),
        play_hitsound=bool(play_hitsound),
    )
    chart.note_types[note_type_name] = updated_note_type
    return updated_note_type


def _normalize_color(color: Color) -> Color:
    normalized_channels: list[int] = []
    for channel in color:
        channel_value = int(channel)
        if not 0 <= channel_value <= 255:
            raise ValueError("Note type colors must use RGB channels in the range 0..255.")
        normalized_channels.append(channel_value)
    return (normalized_channels[0], normalized_channels[1], normalized_channels[2])

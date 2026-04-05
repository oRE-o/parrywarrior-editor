from __future__ import annotations

import json
from typing import Any

from .models import Chart, Note, NoteType, default_note_types


def chart_to_json_data(chart: Chart) -> dict[str, Any]:
    note_types = {
        name: {
            "name": note_type.name,
            "color": list(note_type.color),
            "is_long_note": note_type.is_long_note,
            "play_hitsound": note_type.play_hitsound,
        }
        for name, note_type in chart.note_types.items()
    }
    notes = [
        {
            "time_ms": note.time_ms,
            "note_type_name": note.note_type_name,
            "lane": note.lane,
            "end_time_ms": note.end_time_ms,
        }
        for note in chart.notes
    ]
    return {
        "song_path": chart.song_path,
        "bpm": chart.bpm,
        "offset_ms": chart.offset_ms,
        "num_lanes": chart.num_lanes,
        "note_types": note_types,
        "notes": notes,
    }


def chart_to_json_text(chart: Chart) -> str:
    return json.dumps(chart_to_json_data(chart), indent=4, ensure_ascii=False)


def chart_from_json_text(text: str, *, chart_path: str = "") -> Chart:
    data = json.loads(text)
    return chart_from_json_data(data, chart_path=chart_path)


def chart_from_json_data(data: object, *, chart_path: str = "") -> Chart:
    if not isinstance(data, dict):
        raise TypeError("Chart JSON root must be an object.")

    raw_note_types = data.get("note_types")
    note_types = _parse_note_types(raw_note_types)
    notes_payload = data.get("notes", [])
    if not isinstance(notes_payload, list):
        raise TypeError("Chart 'notes' must be a list.")

    return Chart(
        song_path=_expect_string(data.get("song_path", ""), field_name="song_path"),
        chart_path=chart_path,
        bpm=_expect_float(data.get("bpm", 120.0), field_name="bpm"),
        offset_ms=_expect_float(data.get("offset_ms", 0), field_name="offset_ms"),
        num_lanes=_expect_int(data.get("num_lanes", 4), field_name="num_lanes"),
        note_types=note_types,
        notes=[_parse_note(note_payload) for note_payload in notes_payload],
    )


def _parse_note_types(payload: object) -> dict[str, NoteType]:
    if payload is None:
        return default_note_types()
    if isinstance(payload, dict) and not payload:
        return default_note_types()
    if not isinstance(payload, dict):
        raise TypeError("Chart 'note_types' must be an object.")

    parsed: dict[str, NoteType] = {}
    for name, raw_note_type in payload.items():
        if not isinstance(name, str):
            raise TypeError("Note type names must be strings.")
        if not isinstance(raw_note_type, dict):
            raise TypeError(f"Note type '{name}' must be an object.")
        parsed[name] = NoteType(
            name=_expect_string(raw_note_type.get("name", name), field_name=f"note_types.{name}.name"),
            color=_expect_color(raw_note_type.get("color", [255, 255, 255]), field_name=f"note_types.{name}.color"),
            is_long_note=_expect_bool(raw_note_type.get("is_long_note", False), field_name=f"note_types.{name}.is_long_note"),
            play_hitsound=_expect_bool(raw_note_type.get("play_hitsound", True), field_name=f"note_types.{name}.play_hitsound"),
        )
    return parsed


def _parse_note(payload: object) -> Note:
    if not isinstance(payload, dict):
        raise TypeError("Each note must be an object.")
    end_time_value = payload.get("end_time_ms")
    end_time_ms = None if end_time_value is None else _expect_float(end_time_value, field_name="notes[].end_time_ms")
    return Note(
        time_ms=_expect_float(payload.get("time_ms", 0), field_name="notes[].time_ms"),
        note_type_name=_expect_string(payload.get("note_type_name", ""), field_name="notes[].note_type_name"),
        lane=_expect_int(payload.get("lane", 0), field_name="notes[].lane"),
        end_time_ms=end_time_ms,
    )


def _expect_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    return value


def _expect_bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean.")
    return value


def _expect_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def _expect_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    return float(value)


def _expect_color(value: object, *, field_name: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise TypeError(f"{field_name} must be a 3-item list or tuple.")
    channels: list[int] = []
    for channel in value:
        if isinstance(channel, bool) or not isinstance(channel, int):
            raise TypeError(f"{field_name} must contain integer channels.")
        if not 0 <= channel <= 255:
            raise ValueError(f"{field_name} channels must be in the range 0..255.")
        channels.append(channel)
    return (channels[0], channels[1], channels[2])

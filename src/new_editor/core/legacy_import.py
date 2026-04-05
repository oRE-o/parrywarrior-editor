from __future__ import annotations

import json
from typing import Any

from .models import Chart, Note, NoteType, default_note_types


def chart_from_legacy_source_text(text: str, *, chart_path: str = "") -> Chart:
    data = json.loads(text)
    return chart_from_legacy_source_data(data, chart_path=chart_path)


def chart_from_legacy_source_data(data: object, *, chart_path: str = "") -> Chart:
    if not isinstance(data, dict):
        raise TypeError("Legacy source chart JSON root must be an object.")

    notes_payload = data.get("Notes", [])
    if not isinstance(notes_payload, list):
        raise TypeError("Legacy source chart 'Notes' must be a list.")

    note_types = _parse_note_types(data)
    chart = Chart(
        song_path=_expect_string(data.get("AudioFilePath", ""), field_name="AudioFilePath"),
        chart_path=chart_path,
        bpm=_expect_float(data.get("Bpm", 120.0), field_name="Bpm"),
        offset_ms=_expect_float(data.get("AudioOffset", 0), field_name="AudioOffset") * 1000.0,
        num_lanes=_expect_int(data.get("LaneCount", 4), field_name="LaneCount"),
        note_types=note_types or default_note_types(),
        notes=[_parse_note(note_payload) for note_payload in notes_payload],
    )
    if not note_types:
        chart.note_types = {}
    return chart


def _parse_note_types(data: dict[str, Any]) -> dict[str, NoteType]:
    parsed: dict[str, NoteType] = {}
    tool_lists_to_check = (
        ("NormalNoteTools", data.get("NormalNoteTools", [])),
        ("AttackNoteTools", data.get("AttackNoteTools", [])),
        ("TriggerNoteTools", data.get("TriggerNoteTools", [])),
    )
    for field_name, tool_list in tool_lists_to_check:
        if not isinstance(tool_list, list):
            raise TypeError(f"Legacy source chart '{field_name}' must be a list.")
        for tool in tool_list:
            if not isinstance(tool, dict):
                raise TypeError(f"Legacy source chart '{field_name}' entries must be objects.")
            note_name = tool.get("Name")
            if not note_name:
                continue
            if not isinstance(note_name, str):
                raise TypeError(f"Legacy source chart '{field_name}[].Name' must be a string.")
            if note_name in parsed:
                continue
            parsed[note_name] = NoteType(
                name=note_name,
                color=_hex_to_rgb(tool.get("Color", "#FFFFFF")),
                is_long_note=_expect_float(tool.get("Type", 0), field_name=f"{field_name}[].Type") != 0,
                play_hitsound=True,
            )
    return parsed


def _parse_note(payload: object) -> Note:
    if not isinstance(payload, dict):
        raise TypeError("Legacy source chart notes must be objects.")
    return Note(
        time_ms=_expect_float(payload.get("Time", 0), field_name="Notes[].Time") * 1000.0,
        note_type_name=_expect_string(payload.get("NoteToolName", "해류탄막"), field_name="Notes[].NoteToolName"),
        lane=_expect_int(payload.get("Lane", 0), field_name="Notes[].Lane"),
        end_time_ms=None,
    )


def _expect_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    return value


def _expect_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    return value


def _expect_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    return float(value)


def _hex_to_rgb(hex_color: object) -> tuple[int, int, int]:
    if not isinstance(hex_color, str):
        return (255, 255, 255)
    normalized = hex_color.lstrip("#")
    if len(normalized) != 6:
        return (255, 255, 255)
    try:
        return (
            int(normalized[0:2], 16),
            int(normalized[2:4], 16),
            int(normalized[4:6], 16),
        )
    except ValueError:
        return (255, 255, 255)

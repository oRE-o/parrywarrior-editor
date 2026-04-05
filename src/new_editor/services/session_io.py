from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
import shutil

from ..core.legacy_import import chart_from_legacy_source_text
from ..core.legacy_json import chart_from_json_text, chart_to_json_text
from ..core.models import Chart


@dataclass(frozen=True, slots=True)
class SaveResult:
    path: Path
    backup_path: Path | None
    replaced_existing_file: bool


@dataclass(frozen=True, slots=True)
class RecoveryPaths:
    chart_path: Path
    backup_path: Path | None
    autosave_path: Path | None
    autosave_is_newer: bool


def load_chart_file(path: str | Path) -> Chart:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    chart = chart_from_json_text(text, chart_path=str(source))
    chart.chart_path = str(source)
    return chart


def import_legacy_chart_file(path: str | Path) -> Chart:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    chart = chart_from_legacy_source_text(text)
    chart.chart_path = ""
    return chart


def load_recovery_chart_file(path: str | Path, *, chart_path: str | Path | None = None) -> Chart:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    target_chart_path = "" if chart_path is None else str(Path(chart_path))
    chart = chart_from_json_text(text, chart_path=target_chart_path)
    chart.chart_path = target_chart_path
    return chart


def save_chart_file(chart: Chart, path: str | Path) -> SaveResult:
    destination = Path(path)
    return _write_chart_file(chart, destination, create_backup=True, update_chart_path=True)


def autosave_chart_file(chart: Chart, anchor_path: str | Path) -> SaveResult:
    destination = autosave_chart_path_for(anchor_path)
    return _write_chart_file(chart, destination, create_backup=False, update_chart_path=False)


def clear_autosave_file(anchor_path: str | Path) -> None:
    autosave_path = autosave_chart_path_for(anchor_path)
    if autosave_path.exists():
        autosave_path.unlink()


def backup_chart_path_for(path: str | Path) -> Path:
    destination = Path(path)
    return destination.with_suffix(destination.suffix + ".bak")


def autosave_chart_path_for(anchor_path: str | Path) -> Path:
    anchor = Path(anchor_path)
    suffixes = "".join(anchor.suffixes)
    if suffixes:
        return anchor.with_name(f"{anchor.name[:-len(suffixes)]}.autosave.chart.json")
    return anchor.with_name(f"{anchor.name}.autosave.chart.json")


def recovery_paths_for(path: str | Path) -> RecoveryPaths:
    chart_path = Path(path)
    backup_path = backup_chart_path_for(chart_path)
    autosave_path = autosave_chart_path_for(chart_path)
    existing_backup = backup_path if backup_path.exists() else None
    existing_autosave = autosave_path if autosave_path.exists() else None
    autosave_is_newer = False
    if existing_autosave is not None:
        if not chart_path.exists():
            autosave_is_newer = True
        else:
            autosave_is_newer = existing_autosave.stat().st_mtime > chart_path.stat().st_mtime
    return RecoveryPaths(
        chart_path=chart_path,
        backup_path=existing_backup,
        autosave_path=existing_autosave,
        autosave_is_newer=autosave_is_newer,
    )


def _write_chart_file(chart: Chart, destination: Path, *, create_backup: bool, update_chart_path: bool) -> SaveResult:
    destination.parent.mkdir(parents=True, exist_ok=True)

    backup_path = backup_chart_path_for(destination) if create_backup and destination.exists() else None
    replaced_existing_file = destination.exists()
    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=destination.parent,
        prefix=f".{destination.stem}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(temp_file.name)
    try:
        with temp_file:
            temp_file.write(chart_to_json_text(chart))
            temp_file.flush()
            os.fsync(temp_file.fileno())

        if backup_path is not None:
            shutil.copy2(destination, backup_path)

        os.replace(temp_path, destination)
        if update_chart_path:
            chart.chart_path = str(destination)
        return SaveResult(
            path=destination,
            backup_path=backup_path,
            replaced_existing_file=replaced_existing_file,
        )
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

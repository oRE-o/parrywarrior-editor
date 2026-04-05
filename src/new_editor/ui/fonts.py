from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication


_PREFERRED_FAMILIES = [
    "Pretendard Variable",
    "Pretendard",
]


def configure_application_font(app: QApplication) -> None:
    for directory in _candidate_font_directories():
        if not directory.exists():
            continue
        for pattern in ("Pretendard*.otf", "Pretendard*.ttf"):
            for font_path in directory.glob(pattern):
                QFontDatabase.addApplicationFont(str(font_path))

    available_families = set(QFontDatabase.families())
    for family in _PREFERRED_FAMILIES:
        if family in available_families:
            app.setFont(QFont(family))
            return


def _candidate_font_directories() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    return [
        repo_root / "assets" / "fonts",
        repo_root / "legacy" / "pygame_editor" / "assets" / "fonts",
    ]

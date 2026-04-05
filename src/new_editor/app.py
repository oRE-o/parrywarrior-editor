from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from new_editor.ui.fonts import configure_application_font
    from new_editor.ui.main_window import EditorMainWindow
else:
    from .ui.fonts import configure_application_font
    from .ui.main_window import EditorMainWindow


def create_application(argv: list[str] | None = None) -> QApplication:
    arguments = argv if argv is not None else sys.argv
    app = QApplication.instance() or QApplication(arguments)
    app.setApplicationName("Parry Warrior Editor")
    configure_application_font(app)
    return app


def run(argv: list[str] | None = None) -> int:
    app = create_application(argv)
    window = EditorMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())

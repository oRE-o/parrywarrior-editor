from __future__ import annotations

from json import JSONDecodeError
from pathlib import Path
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..services.session_io import recovery_paths_for
from .panels import InspectorPanel, OverviewPanel, TimelinePanel, TransportPanel
from .session import EditorSession
from .styles import build_app_stylesheet
from .tokens import SHELL, SPACE, format_file_name


AUTOSAVE_INTERVAL_MS = 30_000


class EditorMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.session = EditorSession()
        self._current_directory = Path.cwd()
        self._last_autosave_error: str | None = None

        self.setWindowTitle("Parry Warrior Editor")
        self.setMinimumSize(SHELL.minimum_width, SHELL.minimum_height)
        self.setStyleSheet(build_app_stylesheet())

        self._build_actions()
        self._build_menu_bar()
        self._build_shell()
        self._connect_session()
        self._install_editor_shortcuts()
        self._start_autosave_timer()

        self.session.emit_initial_state()

    def _build_actions(self) -> None:
        self.new_action = QAction("New", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.triggered.connect(self._new_chart)

        self.open_action = QAction("Open…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self._open_chart)

        self.import_legacy_action = QAction("Import legacy source…", self)
        self.import_legacy_action.triggered.connect(self._import_legacy_chart)

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self._save_chart)

        self.save_as_action = QAction("Save As…", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self._save_chart_as)

        self.load_song_action = QAction("Load Song…", self)
        self.load_song_action.triggered.connect(self._load_song)

    def _build_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.import_legacy_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.load_song_action)

    def _build_shell(self) -> None:
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(SPACE.md, SPACE.md, SPACE.md, SPACE.md)
        shell_layout.setSpacing(SPACE.md)

        self.overview_panel = OverviewPanel()
        self.timeline_panel = TimelinePanel()
        self.inspector_panel = InspectorPanel()
        self.transport_panel = TransportPanel()

        editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        editor_splitter.setChildrenCollapsible(False)
        editor_splitter.setOpaqueResize(False)
        editor_splitter.addWidget(self.overview_panel)
        editor_splitter.addWidget(self.timeline_panel)
        editor_splitter.addWidget(self.inspector_panel)
        editor_splitter.setStretchFactor(0, 2)
        editor_splitter.setStretchFactor(1, 5)
        editor_splitter.setStretchFactor(2, 3)
        editor_splitter.setSizes([
            SHELL.left_panel_width,
            SHELL.minimum_width - SHELL.left_panel_width - SHELL.right_panel_width,
            SHELL.right_panel_width,
        ])
        self.overview_panel.setMinimumWidth(120)
        self.timeline_panel.setMinimumWidth(320)
        self.inspector_panel.setMinimumWidth(220)

        shell_layout.addWidget(editor_splitter, 1)
        shell_layout.addWidget(self.transport_panel)
        self.setCentralWidget(shell)

        self.inspector_panel.bind_actions(
            new_chart=self._new_chart,
            open_chart=self._open_chart,
            import_legacy_chart=self._import_legacy_chart,
            save_chart=self._save_chart,
            save_chart_as=self._save_chart_as,
            load_song=self._load_song,
        )
        self.inspector_panel.bind_editor_actions(
            set_bpm=self.session.set_bpm,
            set_offset=self.session.set_offset_ms,
            set_snap=self.session.set_snap_division,
            set_lanes=self.session.set_lane_count,
            set_scale=self.session.set_scale_pixels_per_ms,
            set_note_type=self.session.set_current_note_type,
            create_note_type=self.session.create_note_type,
            edit_note_type=self.session.update_note_type,
        )
        self.overview_panel.bind_actions(
            seek_overview=self.session.seek_from_overview,
            nudge=self.session.nudge_timeline,
        )
        self.timeline_panel.bind_actions(
            primary_click=self.session.handle_timeline_primary_click,
            secondary_click=self.session.handle_timeline_secondary_click,
            scrub=self.session.scrub_timeline_by_wheel,
            nudge=self.session.nudge_timeline,
        )
        self.transport_panel.bind_actions(
            play_pause=self.session.toggle_play_pause,
            stop=self.session.stop_song,
            seek=self.session.seek_song,
            set_volume=self.session.set_song_volume,
        )

    def _connect_session(self) -> None:
        self.session.chart_changed.connect(self.overview_panel.update_chart)
        self.session.chart_changed.connect(self.timeline_panel.update_chart)
        self.session.chart_changed.connect(self.inspector_panel.update_chart)
        self.session.chart_changed.connect(self.transport_panel.update_chart)
        self.session.chart_changed.connect(self._refresh_window_title)
        self.session.timeline_state_changed.connect(self.timeline_panel.update_timeline_state)
        self.session.timeline_state_changed.connect(self.inspector_panel.update_timeline_state)
        self.session.timeline_geometry_changed.connect(self.overview_panel.update_timeline_geometry)
        self.session.timeline_geometry_changed.connect(self.timeline_panel.update_timeline_geometry)
        self.session.timeline_geometry_changed.connect(self.inspector_panel.update_timeline_geometry)
        self.session.media_state_changed.connect(self.timeline_panel.update_media_state)
        self.session.media_state_changed.connect(self.overview_panel.update_media_state)
        self.session.media_state_changed.connect(self.transport_panel.update_media_state)
        self.session.status_message_requested.connect(self.statusBar().showMessage)

    def _install_editor_shortcuts(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.installEventFilter(self)

    def eventFilter(self, watched: QObject | None, event: QEvent) -> bool:
        if event.type() != QEvent.Type.KeyPress or not self._should_handle_editor_shortcut():
            return False if watched is None else super().eventFilter(watched, event)
        key_event = cast(QKeyEvent, event)
        if key_event.key() == Qt.Key.Key_Space and key_event.modifiers() == Qt.KeyboardModifier.NoModifier and not key_event.isAutoRepeat():
            self.session.toggle_play_pause()
            return True
        return False if watched is None else super().eventFilter(watched, event)

    def _should_handle_editor_shortcut(self) -> bool:
        app = QApplication.instance()
        if not isinstance(app, QApplication) or app.activeWindow() is not self:
            return False
        return not self._active_focus_widget_is_text_input()

    def _active_focus_widget_is_text_input(self) -> bool:
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return False
        focus_widget = app.focusWidget()
        if focus_widget is None:
            return False
        if isinstance(focus_widget, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)):
            return True
        return isinstance(focus_widget, QComboBox) and focus_widget.isEditable()

    def _start_autosave_timer(self) -> None:
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._run_autosave)
        self._autosave_timer.start()

    def _new_chart(self) -> None:
        if not self._guard_unsaved_changes("start a new chart"):
            return
        self.session.new_chart()
        self._last_autosave_error = None

    def _open_chart(self) -> None:
        if not self._guard_unsaved_changes("open another chart"):
            return
        start_dir = self._suggested_directory(self.session.chart.chart_path)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open chart",
            str(start_dir),
            "Chart JSON (*.json);;All files (*)",
        )
        if not path:
            self.statusBar().showMessage("Open chart canceled.", 3000)
            return
        self._current_directory = Path(path).parent
        recovery = recovery_paths_for(path)
        if recovery.autosave_path is not None and recovery.autosave_is_newer:
            decision = self._ask_autosave_recovery(recovery.chart_path, recovery.autosave_path)
            if decision == "cancel":
                self.statusBar().showMessage("Open chart canceled.", 3000)
                return
            if decision == "autosave":
                self._open_recovery_snapshot(recovery.autosave_path, chart_path=recovery.chart_path, source_label="autosave recovery")
                return
        try:
            self.session.open_chart(path)
        except Exception as exc:
            if self._offer_open_failure_recovery(path, exc):
                return
            self._show_error(
                "Could not open chart",
                self._build_open_error_message(exc),
            )
            return
        self._last_autosave_error = None
        self._warn_about_missing_song_link("chart")

    def _import_legacy_chart(self) -> None:
        if not self._guard_unsaved_changes("import a legacy source chart"):
            return
        start_dir = self._suggested_directory(self.session.chart.chart_path)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import legacy source chart",
            str(start_dir),
            "Legacy source files (*.json *.tep);;All files (*)",
        )
        if not path:
            self.statusBar().showMessage("Legacy import canceled.", 3000)
            return
        self._current_directory = Path(path).parent
        try:
            self.session.import_legacy_chart(path)
        except Exception as exc:
            self._show_error(
                "Could not import legacy chart",
                f"The legacy source chart could not be converted into the current editor model.\n\nReason: {exc}",
            )
            return
        self._last_autosave_error = None
        self._warn_about_missing_song_link("imported chart")

    def _save_chart(self) -> None:
        if not self.session.chart.chart_path:
            self._save_chart_as()
            return
        try:
            self.session.save_chart()
            self._last_autosave_error = None
        except Exception as exc:
            self._show_error(
                "Could not save chart",
                f"The chart file could not be written safely.\n\nReason: {exc}",
            )

    def _save_chart_as(self) -> bool:
        suggested_name = self.session.suggested_save_name
        start_path = self._suggested_directory(self.session.chart.chart_path) / suggested_name
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save chart as",
            str(start_path),
            "Chart JSON (*.json);;All files (*)",
        )
        if not path:
            self.statusBar().showMessage("Save As canceled.", 3000)
            return False
        if not Path(path).suffix:
            path = f"{path}.json"
        self._current_directory = Path(path).parent
        try:
            self.session.save_chart_as(path)
            self._last_autosave_error = None
            return True
        except Exception as exc:
            self._show_error(
                "Could not save chart",
                f"The chart file could not be written safely.\n\nReason: {exc}",
            )
            return False

    def _load_song(self) -> None:
        start_dir = self._suggested_directory(self.session.chart.song_path)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load song",
            str(start_dir),
            "Audio files (*.wav *.mp3 *.ogg *.flac *.m4a *.aac *.opus *.aiff *.aif *.wma);;All files (*)",
        )
        if not path:
            self.statusBar().showMessage("Load song canceled.", 3000)
            return
        self._current_directory = Path(path).parent
        self.session.load_song(path)

    def _run_autosave(self) -> None:
        try:
            result = self.session.autosave_if_needed()
        except Exception as exc:
            error_text = str(exc)
            self.statusBar().showMessage(f"Autosave failed: {error_text}", 7000)
            if self._last_autosave_error != error_text:
                _ = QMessageBox.warning(
                    self,
                    "Autosave failed",
                    f"The recovery snapshot could not be updated.\n\nReason: {exc}",
                )
                self._last_autosave_error = error_text
            return
        if result is not None:
            self._last_autosave_error = None

    def _guard_unsaved_changes(self, next_step: str) -> bool:
        if not self.session.is_dirty:
            return True

        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            f"You have unsaved changes. Save before you {next_step}?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if answer == QMessageBox.StandardButton.Save:
            return self._save_chart_as() if not self.session.chart.chart_path else self._save_and_continue()
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _save_and_continue(self) -> bool:
        try:
            self.session.save_chart()
            self._last_autosave_error = None
            return True
        except Exception as exc:
            self._show_error(
                "Could not save chart",
                f"The chart file could not be written safely.\n\nReason: {exc}",
            )
            return False

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
        self.statusBar().showMessage(title, 5000)

    def _build_open_error_message(self, exc: Exception) -> str:
        if isinstance(exc, JSONDecodeError):
            return (
                "The chart file could not be opened because its JSON is corrupt or incomplete. "
                "If you have a recovery snapshot or .bak backup, you can recover that instead."
                f"\n\nReason: {exc}"
            )
        if isinstance(exc, (TypeError, ValueError)):
            return (
                "The chart file could not be opened because its contents do not match the current chart format."
                f"\n\nReason: {exc}"
            )
        return f"The chart file could not be loaded.\n\nReason: {exc}"

    def _ask_autosave_recovery(self, chart_path: Path, autosave_path: Path) -> str:
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle("Open newer autosave?")
        dialog.setText(
            "A newer autosave recovery snapshot exists for this chart. "
            "Open the autosave snapshot or continue with the last manual save?"
        )
        dialog.setInformativeText(
            f"Saved chart: {chart_path.name}\nAutosave snapshot: {autosave_path.name}"
        )
        autosave_button = dialog.addButton("Open autosave", QMessageBox.ButtonRole.AcceptRole)
        saved_button = dialog.addButton("Open saved chart", QMessageBox.ButtonRole.ActionRole)
        cancel_button = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.setDefaultButton(autosave_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked == autosave_button:
            return "autosave"
        if clicked == saved_button:
            return "saved"
        if clicked == cancel_button:
            return "cancel"
        return "cancel"

    def _offer_open_failure_recovery(self, path: str | Path, exc: Exception) -> bool:
        recovery = recovery_paths_for(path)
        if recovery.autosave_path is None and recovery.backup_path is None:
            return False

        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Open failed - recover another file?")
        dialog.setText(self._build_open_error_message(exc))
        details: list[str] = []
        if recovery.autosave_path is not None:
            details.append(f"Autosave snapshot: {recovery.autosave_path.name}")
        if recovery.backup_path is not None:
            details.append(f"Backup file: {recovery.backup_path.name}")
        dialog.setInformativeText("\n".join(details))

        autosave_button = None
        backup_button = None
        if recovery.autosave_path is not None:
            autosave_button = dialog.addButton("Open autosave", QMessageBox.ButtonRole.AcceptRole)
        if recovery.backup_path is not None:
            backup_button = dialog.addButton("Open backup", QMessageBox.ButtonRole.ActionRole)
        cancel_button = dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()

        clicked = dialog.clickedButton()
        if autosave_button is not None and clicked == autosave_button:
            self._open_recovery_snapshot(recovery.autosave_path, chart_path=recovery.chart_path, source_label="autosave recovery")
            return True
        if backup_button is not None and clicked == backup_button:
            self._open_recovery_snapshot(recovery.backup_path, chart_path=recovery.chart_path, source_label="backup recovery")
            return True
        if clicked == cancel_button:
            self.statusBar().showMessage("Open chart canceled.", 3000)
            return True
        return False

    def _open_recovery_snapshot(self, recovery_path: Path | None, *, chart_path: Path, source_label: str) -> None:
        if recovery_path is None:
            return
        try:
            self.session.open_recovery_chart(recovery_path, chart_path=chart_path, source_label=source_label)
        except Exception as exc:
            self._show_error(
                f"Could not open {source_label}",
                f"The selected recovery file could not be loaded.\n\nReason: {exc}",
            )
            return
        self._last_autosave_error = None
        self._warn_about_missing_song_link(source_label)

    def _warn_about_missing_song_link(self, context_label: str) -> None:
        song_path = self.session.chart.song_path
        if not song_path or Path(song_path).exists():
            return
        _ = QMessageBox.warning(
            self,
            "Linked song missing",
            f"The {context_label} opened successfully, but the linked song file is missing on disk.\n\nMissing path: {song_path}\n\nYou can keep editing and use Load Song… to relink the audio.",
        )
        self.statusBar().showMessage("Linked song is missing on disk.", 7000)

    def _refresh_window_title(self, chart, is_dirty: bool) -> None:
        marker = "* " if is_dirty else ""
        name = format_file_name(chart.chart_path, fallback="Untitled chart")
        self.setWindowTitle(f"{marker}{name} - Parry Warrior Editor")

    def _suggested_directory(self, active_path: str) -> Path:
        if active_path:
            candidate = Path(active_path)
            if candidate.exists():
                return candidate.parent if candidate.is_file() else candidate
            if candidate.parent.exists():
                return candidate.parent
        return self._current_directory

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._guard_unsaved_changes("close the editor"):
            event.accept()
            return
        event.ignore()

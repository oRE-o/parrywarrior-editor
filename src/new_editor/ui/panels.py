from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.media import MediaState, PlaybackState
from ..core.models import Chart, Color
from ..core.note_types import LEGACY_NOTE_TYPE_PRESET_COLORS, count_notes_using_note_type
from ..core.timeline import (
    DEFAULT_SCALE_PIXELS_PER_MS,
    MAX_SCALE_PIXELS_PER_MS,
    MIN_SCALE_PIXELS_PER_MS,
    TimelineGeometry,
    TimelineToolState,
)
from .media_widgets import (
    TransportSeekBarWidget,
    WaveformPreviewWidget,
    effective_duration_ms,
    format_media_time,
    media_status_text,
    playback_state_label,
    waveform_detail_text,
)
from .timeline_canvas import TimelineCanvasWidget
from .tokens import PALETTE, SHELL, SPACE, color_to_hex, format_file_name


def _set_label_role(label: QLabel, role: str) -> QLabel:
    _ = label.setProperty("role", role)
    return label


def _format_quick_edit_lane_keys(lane_keys: tuple[str, ...]) -> str:
    if not lane_keys:
        return "Unbound"
    formatted_keys = ["Space" if key == "space" else key.upper() for key in lane_keys]
    return " / ".join(formatted_keys)


class QuickEditSettingsDialog(QDialog):
    def __init__(self, *, lane_key_preset: tuple[tuple[str, ...], ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lane_key_preset = [tuple(lane_keys) for lane_keys in lane_key_preset]
        self._capture_lane_index: int | None = None
        self._binding_buttons: list[QPushButton] = []

        self.setModal(True)
        self.setMinimumWidth(SPACE.xxl * 10)
        self.setWindowTitle("빠른 편집 키 설정")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)
        layout.setSpacing(SPACE.md)

        summary_label = QLabel("변경할 레인을 클릭한 뒤 원하는 키를 누르세요. Q는 빠른 편집 토글로 예약되어 있습니다.")
        summary_label.setWordWrap(True)
        layout.addWidget(_set_label_role(summary_label, "secondary"))

        bindings_layout = QGridLayout()
        bindings_layout.setContentsMargins(0, 0, 0, 0)
        bindings_layout.setHorizontalSpacing(SPACE.sm)
        bindings_layout.setVerticalSpacing(SPACE.sm)
        for lane_index, lane_keys in enumerate(self._lane_key_preset):
            lane_label = QLabel(f"레인 {lane_index + 1}")
            binding_button = QPushButton(_format_quick_edit_lane_keys(lane_keys))
            binding_button.clicked.connect(lambda _checked=False, selected_lane=lane_index: self._begin_key_capture(selected_lane))
            self._binding_buttons.append(binding_button)
            bindings_layout.addWidget(_set_label_role(lane_label, "secondary"), lane_index, 0)
            bindings_layout.addWidget(binding_button, lane_index, 1)
        layout.addLayout(bindings_layout)

        self.status_label = QLabel("7레인 기본값에서는 Space를 4번 레인 입력으로 사용합니다.")
        self.status_label.setWordWrap(True)
        layout.addWidget(_set_label_role(self.status_label, "muted"))

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def values(self) -> tuple[tuple[str, ...], ...]:
        return tuple(self._lane_key_preset)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        capture_lane_index = self._capture_lane_index
        if capture_lane_index is None:
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Escape:
            self._capture_lane_index = None
            self.status_label.setText("키 변경을 취소했습니다.")
            self._refresh_binding_buttons()
            event.accept()
            return

        binding_key = self._binding_key_from_event(event)
        if binding_key is None:
            event.accept()
            return

        self._lane_key_preset[capture_lane_index] = (binding_key,)
        self._capture_lane_index = None
        self.status_label.setText(f"레인 {capture_lane_index + 1} 키를 {_format_quick_edit_lane_keys((binding_key,))}(으)로 변경했습니다.")
        self._refresh_binding_buttons()
        event.accept()

    def _begin_key_capture(self, lane_index: int) -> None:
        self._capture_lane_index = lane_index
        self.status_label.setText(f"레인 {lane_index + 1}에 사용할 키를 누르세요. Esc로 취소할 수 있습니다.")
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self._refresh_binding_buttons()

    def _refresh_binding_buttons(self) -> None:
        for lane_index, binding_button in enumerate(self._binding_buttons):
            if lane_index == self._capture_lane_index:
                binding_button.setText("키 입력 대기 중…")
                binding_button.setDown(True)
                continue
            binding_button.setDown(False)
            binding_button.setText(_format_quick_edit_lane_keys(self._lane_key_preset[lane_index]))

    def _binding_key_from_event(self, event: QKeyEvent) -> str | None:
        if event.key() == Qt.Key.Key_Space:
            return "space"
        if event.key() in {
            Qt.Key.Key_Shift,
            Qt.Key.Key_Control,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_AltGr,
            Qt.Key.Key_CapsLock,
            Qt.Key.Key_Tab,
        }:
            return None
        key_text = event.text()
        if len(key_text) != 1 or not key_text.isprintable():
            return None
        return key_text.lower()


class NoteTypeEditorDialog(QDialog):
    def __init__(
        self,
        *,
        mode: str,
        existing_names: set[str],
        name: str,
        color: Color,
        is_long_note: bool,
        play_hitsound: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._original_name = name
        self._existing_names = set(existing_names)
        self._selected_color = color

        self.setModal(True)
        self.setMinimumWidth(SPACE.xxl * 10)
        self.setWindowTitle("New Note Type" if mode == "create" else f"Edit Note Type · {name}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.lg, SPACE.lg, SPACE.lg, SPACE.lg)
        layout.setSpacing(SPACE.md)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(SPACE.sm)
        form.setVerticalSpacing(SPACE.sm)

        self.name_edit = QLineEdit()
        self.name_edit.setText(name)
        form.addRow("Name", self.name_edit)

        color_controls = QHBoxLayout()
        color_controls.setSpacing(SPACE.sm)
        self.color_button = QPushButton("Pick color…")
        self.color_button.clicked.connect(self._pick_color)
        self.color_value_label = QLabel()
        color_controls.addWidget(self.color_button)
        color_controls.addWidget(_set_label_role(self.color_value_label, "secondary"), 1)
        color_controls_container = QWidget()
        color_controls_container.setLayout(color_controls)
        form.addRow("Color", color_controls_container)
        layout.addLayout(form)

        presets_label = QLabel("Presets")
        layout.addWidget(_set_label_role(presets_label, "eyebrow"))

        presets_layout = QGridLayout()
        presets_layout.setContentsMargins(0, 0, 0, 0)
        presets_layout.setHorizontalSpacing(SPACE.sm)
        presets_layout.setVerticalSpacing(SPACE.sm)
        for index, preset_color in enumerate(LEGACY_NOTE_TYPE_PRESET_COLORS):
            swatch = QPushButton()
            _ = swatch.setProperty("colorSwatch", True)
            swatch.setToolTip(color_to_hex(preset_color))
            swatch.setFixedSize(SPACE.xxl + SPACE.md, SPACE.xxl + SPACE.md)
            swatch.setStyleSheet(
                "; ".join(
                    [
                        f"background-color: {color_to_hex(preset_color)}",
                        f"border: 1px solid {PALETTE.panel_border}",
                        f"border-radius: {SPACE.sm}px",
                    ]
                )
            )
            swatch.clicked.connect(lambda _checked=False, selected=preset_color: self._set_selected_color(selected))
            presets_layout.addWidget(swatch, index // 4, index % 4)
        layout.addLayout(presets_layout)

        self.long_note_check = QCheckBox("Long note")
        self.long_note_check.setChecked(is_long_note)
        layout.addWidget(self.long_note_check)

        self.hitsound_check = QCheckBox("Play hitsound")
        self.hitsound_check.setChecked(play_hitsound)
        layout.addWidget(self.hitsound_check)

        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        layout.addWidget(_set_label_role(self.validation_label, "muted"))

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self._ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setText("Create" if mode == "create" else "Save")
        layout.addWidget(self.button_box)

        self.name_edit.textChanged.connect(self._refresh_validation)
        self._set_selected_color(color)
        self._refresh_validation()

    def values(self) -> tuple[str, Color, bool, bool]:
        return (
            self.name_edit.text().strip(),
            self._selected_color,
            self.long_note_check.isChecked(),
            self.hitsound_check.isChecked(),
        )

    def _pick_color(self) -> None:
        selected = QColorDialog.getColor(QColor(color_to_hex(self._selected_color)), self, "Pick note color")
        if not selected.isValid():
            return
        self._set_selected_color((selected.red(), selected.green(), selected.blue()))

    def _set_selected_color(self, color: Color) -> None:
        self._selected_color = color
        hex_color = color_to_hex(color)
        self.color_button.setStyleSheet(
            "; ".join(
                [
                    f"background-color: {hex_color}",
                    f"color: {PALETTE.app_bg}",
                    f"border: 1px solid {PALETTE.panel_border}",
                    f"border-radius: {SPACE.md}px",
                    f"padding: {SPACE.sm}px {SPACE.lg}px",
                ]
            )
        )
        self.color_value_label.setText(hex_color)

    def _refresh_validation(self) -> None:
        proposed_name = self.name_edit.text().strip()
        if not proposed_name:
            self._ok_button.setEnabled(False)
            self.validation_label.setText("")
            return

        name_conflicts = proposed_name in self._existing_names
        if self._mode == "edit" and proposed_name == self._original_name:
            name_conflicts = False

        if name_conflicts:
            self._ok_button.setEnabled(False)
            self.validation_label.setText("Name already exists.")
            return
        self._ok_button.setEnabled(True)
        self.validation_label.setText("")


class PanelCard(QFrame):
    def __init__(self, title: str, description: str = "") -> None:
        super().__init__()
        self.setObjectName("panelCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.md, SPACE.md, SPACE.md, SPACE.md)
        layout.setSpacing(SPACE.sm)

        layout.addWidget(_set_label_role(QLabel(title), "section"))
        if description:
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            layout.addWidget(_set_label_role(description_label, "secondary"))

        self.body_layout = layout


class OverviewPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._chart = Chart()
        self._media_state = MediaState()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.md)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        self.waveform_card = PanelCard("Waveform")
        self.song_label = QLabel("Song · No song")
        self.chart_label = QLabel("Chart · Untitled chart")
        self.status_label = QLabel(media_status_text(self._media_state))
        self.waveform_preview = WaveformPreviewWidget()
        self.waveform_detail_label = QLabel(waveform_detail_text(self._media_state))
        for label in (self.song_label, self.chart_label, self.status_label, self.waveform_detail_label):
            label.setWordWrap(False)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.waveform_card.body_layout.addWidget(_set_label_role(self.song_label, "meta"))
        self.waveform_card.body_layout.addWidget(_set_label_role(self.chart_label, "muted"))
        self.waveform_card.body_layout.addWidget(self.waveform_preview, 1)
        self.waveform_card.body_layout.addWidget(_set_label_role(self.status_label, "secondary"))
        self.waveform_card.body_layout.addWidget(_set_label_role(self.waveform_detail_label, "muted"))
        layout.addWidget(self.waveform_card, 1)

    def bind_actions(self, *, seek_overview, nudge) -> None:
        self.waveform_preview.bind_actions(seek=seek_overview, nudge=nudge)

    def update_chart(self, chart: Chart, is_dirty: bool) -> None:
        self._chart = chart
        song_name = format_file_name(chart.song_path, fallback="No song")
        chart_name = format_file_name(chart.chart_path, fallback="Untitled chart")
        self.song_label.setText(f"Song · {song_name}")
        self.song_label.setToolTip(chart.song_path or "")
        dirty_marker = "*" if is_dirty else ""
        self.chart_label.setText(f"Chart · {dirty_marker}{chart_name}")
        self.chart_label.setToolTip(chart.chart_path or "")

    def update_media_state(self, media_state: MediaState) -> None:
        self._media_state = media_state
        self.waveform_preview.set_media_state(media_state)
        self.status_label.setText(media_status_text(media_state))
        self.waveform_detail_label.setText(waveform_detail_text(media_state))

    def update_timeline_geometry(self, timeline_geometry: TimelineGeometry) -> None:
        self.waveform_preview.set_timeline_geometry(timeline_geometry)

    def update_timeline_state(self, tool_state: TimelineToolState) -> None:
        del tool_state


class TimelinePanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._tool_state = TimelineToolState()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.md)
        self.setMinimumWidth(0)

        self.workspace_card = PanelCard("Timeline")
        self.timeline_canvas = TimelineCanvasWidget()
        self.workspace_card.body_layout.addWidget(self.timeline_canvas, 1)
        self.info_grid = QGridLayout()
        self.info_grid.setContentsMargins(0, 0, 0, 0)
        self.info_grid.setHorizontalSpacing(SPACE.md)
        self.info_grid.setVerticalSpacing(SPACE.xs)
        self.bpm_label = QLabel()
        self.offset_label = QLabel()
        self.lane_label = QLabel()
        self.note_count_label = QLabel()
        self.note_type_count_label = QLabel()
        self.snap_label = QLabel()
        self.current_note_type_label = QLabel()
        self.pending_long_label = QLabel()
        info_labels = (
            self.bpm_label,
            self.offset_label,
            self.lane_label,
            self.note_count_label,
            self.note_type_count_label,
            self.snap_label,
            self.current_note_type_label,
            self.pending_long_label,
        )
        for index, label in enumerate(info_labels):
            self.info_grid.addWidget(_set_label_role(label, "secondary"), index // 4, index % 4)
        self.workspace_card.body_layout.addLayout(self.info_grid)
        layout.addWidget(self.workspace_card, 1)

    def bind_actions(self, *, primary_click, secondary_click, hover, scrub, nudge) -> None:
        self.timeline_canvas.bind_actions(
            primary_click=primary_click,
            secondary_click=secondary_click,
            hover=hover,
            scrub=scrub,
            nudge=nudge,
        )

    def update_chart(self, chart: Chart, _: bool) -> None:
        self.timeline_canvas.set_chart(chart)
        self.bpm_label.setText(f"BPM {chart.bpm:.2f}")
        self.offset_label.setText(f"Offset {chart.offset_ms:.0f} ms")
        self.lane_label.setText(f"Lane {chart.num_lanes}")
        self.note_count_label.setText(f"Notes {len(chart.notes)}")
        self.note_type_count_label.setText(f"Types {len(chart.note_types)}")

    def update_media_state(self, media_state: MediaState) -> None:
        self.timeline_canvas.set_media_state(media_state)

    def update_timeline_geometry(self, timeline_geometry: TimelineGeometry) -> None:
        self.timeline_canvas.set_timeline_geometry(timeline_geometry)

    def update_timeline_state(self, tool_state: TimelineToolState) -> None:
        self._tool_state = tool_state
        self.timeline_canvas.set_tool_state(tool_state)
        self.snap_label.setText(f"Snap {tool_state.snap_division}")
        current_note_type = tool_state.current_note_type_name or "None"
        self.current_note_type_label.setText(f"Type {current_note_type}")
        pending_long_note = tool_state.pending_long_note
        if pending_long_note is None:
            self.pending_long_label.setText("Long none")
            return
        self.pending_long_label.setText(
            f"Long L{pending_long_note.lane + 1} @ {pending_long_note.time_ms:.0f} ms"
        )


class InspectorPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._chart = Chart()
        self._timeline_geometry = TimelineGeometry()
        self._tool_state = TimelineToolState()
        self._set_quick_edit_lane_key_preset_handler: Callable[[tuple[tuple[str, ...], ...]], None] | None = None
        self._create_note_type_handler: Callable[..., None] | None = None
        self._edit_note_type_handler: Callable[..., None] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE.md)
        self.setMinimumWidth(0)

        self.actions_card = PanelCard("Session")
        self.load_song_button = QPushButton("Load Song")
        self.save_button = QPushButton("Save")
        self.open_button = QPushButton("Load")
        self.save_as_button = QPushButton("Save As")
        self.import_legacy_button = QPushButton("Import")
        self.new_button = QPushButton("New")

        self.actions_card.body_layout.addWidget(self.load_song_button)

        primary_actions = QHBoxLayout()
        primary_actions.setSpacing(SPACE.sm)
        primary_actions.addWidget(self.save_button)
        primary_actions.addWidget(self.open_button)
        self.actions_card.body_layout.addLayout(primary_actions)

        secondary_actions = QHBoxLayout()
        secondary_actions.setSpacing(SPACE.sm)
        secondary_actions.addWidget(self.save_as_button)
        secondary_actions.addWidget(self.import_legacy_button)
        secondary_actions.addWidget(self.new_button)
        self.actions_card.body_layout.addLayout(secondary_actions)

        self.file_label = QLabel("Untitled chart")
        self.song_label = QLabel("No song")
        self.status_label = QLabel("Saved")
        for label in (self.file_label, self.song_label, self.status_label):
            label.setWordWrap(False)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.actions_card.body_layout.addWidget(_set_label_role(self.file_label, "secondary"))
        self.actions_card.body_layout.addWidget(_set_label_role(self.song_label, "secondary"))
        self.actions_card.body_layout.addWidget(_set_label_role(self.status_label, "muted"))
        layout.addWidget(self.actions_card)

        self.controls_card = PanelCard("Chart")
        controls_form = QFormLayout()
        controls_form.setContentsMargins(0, 0, 0, 0)
        controls_form.setHorizontalSpacing(SPACE.sm)
        controls_form.setVerticalSpacing(SPACE.sm)

        self.bpm_spin = QDoubleSpinBox()
        self.bpm_spin.setDecimals(2)
        self.bpm_spin.setRange(1.0, 999.0)
        self.bpm_spin.setSingleStep(1.0)

        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-600000, 600000)
        self.offset_spin.setSingleStep(1)
        self.offset_spin.setSuffix(" ms")

        self.snap_combo = QComboBox()
        self.snap_combo.addItems(["4", "8", "12", "16", "24", "32"])

        self.lane_combo = QComboBox()
        self.lane_combo.addItems(["3", "4", "5", "6", "7"])

        self.scroll_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.scroll_speed_slider.setRange(int(MIN_SCALE_PIXELS_PER_MS * 100), int(MAX_SCALE_PIXELS_PER_MS * 100))
        self.scroll_speed_slider.setSingleStep(1)
        self.scroll_speed_slider.setPageStep(5)
        self.scroll_speed_slider.setValue(int(DEFAULT_SCALE_PIXELS_PER_MS * 100))
        self.scroll_speed_value_label = QLabel()
        scroll_speed_row = QWidget()
        scroll_speed_layout = QHBoxLayout(scroll_speed_row)
        scroll_speed_layout.setContentsMargins(0, 0, 0, 0)
        scroll_speed_layout.setSpacing(SPACE.sm)
        scroll_speed_layout.addWidget(self.scroll_speed_slider, 1)
        scroll_speed_layout.addWidget(_set_label_role(self.scroll_speed_value_label, "secondary"))

        controls_form.addRow("BPM", self.bpm_spin)
        controls_form.addRow("Offset", self.offset_spin)
        controls_form.addRow("Snap", self.snap_combo)
        controls_form.addRow("Lane", self.lane_combo)
        controls_form.addRow("Zoom (Scroll Speed)", scroll_speed_row)
        self.controls_card.body_layout.addLayout(controls_form)

        self.edit_state_label = QLabel()
        self.edit_state_label.setWordWrap(False)
        self.edit_state_label.setMinimumWidth(0)
        self.edit_state_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.controls_card.body_layout.addWidget(_set_label_role(self.edit_state_label, "muted"))
        layout.addWidget(self.controls_card)

        self.quick_edit_card = PanelCard("빠른 편집")
        quick_edit_actions = QHBoxLayout()
        quick_edit_actions.setContentsMargins(0, 0, 0, 0)
        quick_edit_actions.setSpacing(SPACE.sm)
        self.quick_edit_toggle_button = QPushButton("빠른 편집 · 꺼짐")
        self.quick_edit_toggle_button.setCheckable(True)
        self.quick_edit_toggle_button.setToolTip("단축키 · Q")
        self.quick_edit_bindings_button = QPushButton("키 설정…")
        quick_edit_actions.addWidget(self.quick_edit_toggle_button, 1)
        quick_edit_actions.addWidget(self.quick_edit_bindings_button)
        self.quick_edit_card.body_layout.addLayout(quick_edit_actions)

        self.quick_edit_status_label = QLabel("꺼짐 · Q로 빠른 편집 전환")
        self.quick_edit_status_label.setWordWrap(True)
        self.quick_edit_bindings_label = QLabel("키 설정 · 없음")
        self.quick_edit_bindings_label.setWordWrap(True)
        self.quick_edit_card.body_layout.addWidget(_set_label_role(self.quick_edit_status_label, "secondary"))
        self.quick_edit_card.body_layout.addWidget(_set_label_role(self.quick_edit_bindings_label, "muted"))
        layout.addWidget(self.quick_edit_card)

        self.note_types_card = PanelCard("Note Types")

        self.note_type_list = QListWidget()
        self.note_types_card.body_layout.addWidget(self.note_type_list)

        note_type_actions = QHBoxLayout()
        note_type_actions.setSpacing(SPACE.sm)
        self.new_note_type_button = QPushButton("New")
        self.edit_note_type_button = QPushButton("Edit")
        self.edit_note_type_button.setEnabled(False)
        note_type_actions.addWidget(self.new_note_type_button)
        note_type_actions.addWidget(self.edit_note_type_button)
        self.note_types_card.body_layout.addLayout(note_type_actions)

        self.note_type_detail_label = QLabel("Select a type")
        self.note_type_detail_label.setWordWrap(False)
        self.note_type_detail_label.setMinimumWidth(0)
        self.note_type_detail_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.note_types_card.body_layout.addWidget(_set_label_role(self.note_type_detail_label, "muted"))
        layout.addWidget(self.note_types_card, 1)

    def bind_actions(self, *, new_chart, open_chart, import_legacy_chart, save_chart, save_chart_as, load_song) -> None:
        self.new_button.clicked.connect(new_chart)
        self.open_button.clicked.connect(open_chart)
        self.import_legacy_button.clicked.connect(import_legacy_chart)
        self.save_button.clicked.connect(save_chart)
        self.save_as_button.clicked.connect(save_chart_as)
        self.load_song_button.clicked.connect(load_song)

    def bind_editor_actions(
        self,
        *,
        set_bpm,
        set_offset,
        set_snap,
        set_lanes,
        set_scale,
        toggle_quick_edit,
        set_quick_edit_lane_key_preset,
        set_note_type,
        create_note_type,
        edit_note_type,
    ) -> None:
        self._set_quick_edit_lane_key_preset_handler = set_quick_edit_lane_key_preset
        self._create_note_type_handler = create_note_type
        self._edit_note_type_handler = edit_note_type
        self.bpm_spin.valueChanged.connect(set_bpm)
        self.offset_spin.valueChanged.connect(set_offset)
        self.snap_combo.currentTextChanged.connect(lambda text: text and set_snap(int(text)))
        self.lane_combo.currentTextChanged.connect(lambda text: text and set_lanes(int(text)))
        self.scroll_speed_slider.valueChanged.connect(lambda value: set_scale(float(value) / 100.0))
        self.quick_edit_toggle_button.clicked.connect(lambda _checked=False: toggle_quick_edit())
        self.quick_edit_bindings_button.clicked.connect(self._open_quick_edit_settings_dialog)
        self.note_type_list.itemSelectionChanged.connect(lambda: self._notify_note_type_selection(set_note_type))
        self.note_type_list.itemSelectionChanged.connect(self._refresh_note_type_actions)
        self.new_note_type_button.clicked.connect(self._open_create_note_type_dialog)
        self.edit_note_type_button.clicked.connect(self._open_edit_note_type_dialog)
        self._apply_scale_pixels_per_ms(self._timeline_geometry.scale_pixels_per_ms)

    def update_chart(self, chart: Chart, is_dirty: bool) -> None:
        self._chart = chart
        chart_name = format_file_name(chart.chart_path, fallback="Untitled chart")
        song_name = format_file_name(chart.song_path, fallback="No song")
        self.file_label.setText(f"Chart · {chart_name}")
        self.file_label.setToolTip(chart.chart_path or "")
        self.song_label.setText(f"Song · {song_name}")
        self.song_label.setToolTip(chart.song_path or "")
        self.status_label.setText("Unsaved" if is_dirty else "Saved")

        self.bpm_spin.blockSignals(True)
        self.bpm_spin.setValue(chart.bpm)
        self.bpm_spin.blockSignals(False)

        self.offset_spin.blockSignals(True)
        self.offset_spin.setValue(int(chart.offset_ms))
        self.offset_spin.blockSignals(False)

        self.lane_combo.blockSignals(True)
        self.lane_combo.setCurrentText(str(chart.num_lanes))
        self.lane_combo.blockSignals(False)

        self.note_type_list.blockSignals(True)
        self.note_type_list.clear()
        for name in chart.note_types:
            item = QListWidgetItem(self._note_type_row_text(name))
            item.setToolTip(self._note_type_detail_text(name))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.note_type_list.addItem(item)
        self._apply_selected_note_type()
        self.note_type_list.blockSignals(False)
        self._refresh_note_type_actions()
        self._refresh_note_type_details()
        self._refresh_quick_edit_summary()

    def update_timeline_geometry(self, timeline_geometry: TimelineGeometry) -> None:
        self._timeline_geometry = timeline_geometry
        self._apply_scale_pixels_per_ms(timeline_geometry.scale_pixels_per_ms)

    def update_timeline_state(self, tool_state: TimelineToolState) -> None:
        self._tool_state = tool_state

        self.snap_combo.blockSignals(True)
        self.snap_combo.setCurrentText(str(tool_state.snap_division))
        self.snap_combo.blockSignals(False)

        self.quick_edit_toggle_button.blockSignals(True)
        self.quick_edit_toggle_button.setChecked(tool_state.quick_edit_enabled)
        self.quick_edit_toggle_button.setText("빠른 편집 · 켜짐" if tool_state.quick_edit_enabled else "빠른 편집 · 꺼짐")
        self.quick_edit_toggle_button.blockSignals(False)

        self._apply_selected_note_type()
        self._refresh_note_type_actions()
        self._refresh_note_type_details()
        self._refresh_quick_edit_summary()
        pending_long_note = tool_state.pending_long_note
        if pending_long_note is None:
            self.edit_state_label.setText(f"Type {tool_state.current_note_type_name} · Long none")
            return
        self.edit_state_label.setText(
            f"Type {tool_state.current_note_type_name} · Long L{pending_long_note.lane + 1} @ {pending_long_note.time_ms:.0f} ms"
        )

    def _apply_selected_note_type(self) -> None:
        self.note_type_list.blockSignals(True)
        for row_index in range(self.note_type_list.count()):
            item = self.note_type_list.item(row_index)
            if item.data(Qt.ItemDataRole.UserRole) != self._tool_state.current_note_type_name:
                continue
            self.note_type_list.setCurrentRow(row_index)
            self.note_type_list.blockSignals(False)
            return
        self.note_type_list.clearSelection()
        self.note_type_list.blockSignals(False)

    def _notify_note_type_selection(self, set_note_type) -> None:
        current_item = self.note_type_list.currentItem()
        if current_item is None:
            return
        note_type_name = current_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(note_type_name, str):
            return
        set_note_type(note_type_name)

    def _refresh_note_type_actions(self) -> None:
        self.edit_note_type_button.setEnabled(self._selected_note_type_name() is not None)

    def _apply_scale_pixels_per_ms(self, scale_pixels_per_ms: float) -> None:
        self.scroll_speed_slider.blockSignals(True)
        self.scroll_speed_slider.setValue(int(round(scale_pixels_per_ms * 100.0)))
        self.scroll_speed_slider.blockSignals(False)
        self.scroll_speed_value_label.setText(f"{scale_pixels_per_ms:.2f}x")

    def _open_quick_edit_settings_dialog(self) -> None:
        if self._set_quick_edit_lane_key_preset_handler is None:
            return
        dialog = QuickEditSettingsDialog(lane_key_preset=self._tool_state.quick_edit_lane_key_preset, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._set_quick_edit_lane_key_preset_handler(dialog.values())
        except ValueError as exc:
            _ = QMessageBox.warning(self, "빠른 편집 키 설정 변경 실패", str(exc))

    def _refresh_quick_edit_summary(self) -> None:
        tool_state = self._tool_state
        if tool_state.quick_edit_enabled:
            range_text = "구간 선택 대기"
            selection_range = tool_state.selection_range
            if selection_range is not None:
                range_text = f"선택 {selection_range.start_time_ms:.0f}-{selection_range.end_time_ms:.0f} ms"
            paste_text = "붙여넣기 마커 없음"
            if tool_state.paste_marker_time_ms is not None:
                paste_text = f"붙여넣기 {tool_state.paste_marker_time_ms:.0f} ms"
            hold_text = f"홀드 {len(tool_state.pending_long_notes)}개"
            self.quick_edit_status_label.setText(
                f"켜짐 · 좌클릭 구간 선택 · 우클릭 붙여넣기 마커 · {range_text} · {paste_text} · {hold_text}"
            )
        else:
            self.quick_edit_status_label.setText("꺼짐 · Q로 빠른 편집 전환")

        visible_bindings = [
            f"L{lane_index + 1} {_format_quick_edit_lane_keys(lane_keys)}"
            for lane_index, lane_keys in enumerate(tool_state.quick_edit_lane_key_preset[: self._chart.num_lanes])
        ]
        self.quick_edit_bindings_label.setText(
            "키 설정 · " + (" · ".join(visible_bindings) if visible_bindings else "없음")
        )

    def _refresh_note_type_details(self) -> None:
        selected_name = self._selected_note_type_name()
        if selected_name is None:
            self.note_type_detail_label.setText("Select a type")
            return
        self.note_type_detail_label.setText(self._note_type_detail_text(selected_name))

    def _open_create_note_type_dialog(self) -> None:
        if self._create_note_type_handler is None:
            return
        dialog = NoteTypeEditorDialog(
            mode="create",
            existing_names=set(self._chart.note_types.keys()),
            name="",
            color=LEGACY_NOTE_TYPE_PRESET_COLORS[0],
            is_long_note=False,
            play_hitsound=True,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, color, is_long_note, play_hitsound = dialog.values()
        try:
            self._create_note_type_handler(
                name=name,
                color=color,
                is_long_note=is_long_note,
                play_hitsound=play_hitsound,
            )
        except ValueError as exc:
            _ = QMessageBox.warning(self, "Could not create note type", str(exc))

    def _open_edit_note_type_dialog(self) -> None:
        if self._edit_note_type_handler is None:
            return
        selected_name = self._selected_note_type_name()
        if selected_name is None:
            return
        note_type = self._chart.note_types.get(selected_name)
        if note_type is None:
            return
        dialog = NoteTypeEditorDialog(
            mode="edit",
            existing_names=set(self._chart.note_types.keys()),
            name=note_type.name,
            color=note_type.color,
            is_long_note=note_type.is_long_note,
            play_hitsound=note_type.play_hitsound,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, color, is_long_note, play_hitsound = dialog.values()
        if not self._confirm_note_type_rename(selected_name, name):
            return
        try:
            self._edit_note_type_handler(
                selected_name,
                name=name,
                color=color,
                is_long_note=is_long_note,
                play_hitsound=play_hitsound,
            )
        except ValueError as exc:
            _ = QMessageBox.warning(self, "Could not update note type", str(exc))

    def _confirm_note_type_rename(self, original_name: str, updated_name: str) -> bool:
        if updated_name == original_name:
            return True

        affected_count = count_notes_using_note_type(self._chart, original_name)
        if affected_count <= 0:
            return True

        note_label = "note" if affected_count == 1 else "notes"
        answer = QMessageBox.question(
            self,
            "Rename note type and migrate notes?",
            (
                f"Renaming note type '{original_name}' to '{updated_name}' will migrate "
                f"{affected_count} placed {note_label} from '{original_name}' to '{updated_name}'."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _selected_note_type_name(self) -> str | None:
        current_item = self.note_type_list.currentItem()
        if current_item is not None:
            note_type_name = current_item.data(Qt.ItemDataRole.UserRole)
            if isinstance(note_type_name, str) and note_type_name in self._chart.note_types:
                return note_type_name
        if self._tool_state.current_note_type_name in self._chart.note_types:
            return self._tool_state.current_note_type_name
        return None

    def _note_type_row_text(self, note_type_name: str) -> str:
        note_type = self._chart.note_types[note_type_name]
        lane_behavior = "long" if note_type.is_long_note else "tap"
        hitsound = "hs" if note_type.play_hitsound else "mute"
        return f"{note_type.name} · {lane_behavior} · {hitsound}"

    def _note_type_detail_text(self, note_type_name: str) -> str:
        note_type = self._chart.note_types[note_type_name]
        note_kind = "Long" if note_type.is_long_note else "Tap"
        hitsound = "hitsound on" if note_type.play_hitsound else "hitsound off"
        return f"{note_kind} · {color_to_hex(note_type.color)} · {hitsound}"


class TransportPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("transportBar")
        self.setMinimumHeight(SHELL.transport_height)
        self._media_state = MediaState()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE.md, SPACE.sm, SPACE.md, SPACE.sm)
        layout.setSpacing(SPACE.sm)

        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)
        controls_row.setSpacing(SPACE.md)

        self.play_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.time_label = QLabel("00:00.000 / 00:00.000")
        self.song_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.song_volume_slider.setRange(0, 100)
        self.song_volume_slider.setValue(70)
        self.song_volume_slider.setFixedWidth(100)
        self.song_volume_label = QLabel("70")
        self.hitsound_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.hitsound_volume_slider.setRange(0, 100)
        self.hitsound_volume_slider.setValue(35)
        self.hitsound_volume_slider.setFixedWidth(100)
        self.hitsound_volume_label = QLabel("35")
        self.seek_bar = TransportSeekBarWidget()

        controls_row.addStretch(1)
        controls_row.addWidget(self.play_button, 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(self.stop_button, 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(_set_label_role(QLabel("Song"), "muted"), 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(self.song_volume_slider, 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(_set_label_role(self.song_volume_label, "muted"), 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(_set_label_role(QLabel("Hit"), "muted"), 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(self.hitsound_volume_slider, 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(_set_label_role(self.hitsound_volume_label, "muted"), 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addWidget(_set_label_role(self.time_label, "section"), 0, Qt.AlignmentFlag.AlignVCenter)
        controls_row.addStretch(1)
        layout.addLayout(controls_row)
        layout.addWidget(self.seek_bar)

    def bind_actions(self, *, play_pause, stop, seek, set_song_volume, set_hitsound_volume) -> None:
        self.play_button.clicked.connect(play_pause)
        self.stop_button.clicked.connect(stop)
        self.seek_bar.bind_actions(seek=seek)
        self.song_volume_slider.valueChanged.connect(lambda value: set_song_volume(float(value) / 100.0))
        self.hitsound_volume_slider.valueChanged.connect(lambda value: set_hitsound_volume(float(value) / 100.0))

    def update_chart(self, chart: Chart, _: bool) -> None:
        del chart

    def update_media_state(self, media_state: MediaState) -> None:
        self._media_state = media_state
        self.seek_bar.set_media_state(media_state)
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        self.time_label.setText(
            f"{format_media_time(self._media_state.position_ms)} / {format_media_time(effective_duration_ms(self._media_state))}"
        )
        self.time_label.setToolTip(playback_state_label(self._media_state))
        self.play_button.setText("Pause" if self._media_state.playback_state == PlaybackState.PLAYING else "Play")
        self.play_button.setEnabled(self._media_state.can_play)
        self.stop_button.setEnabled(self._media_state.can_stop)
        song_volume_percent = int(round(self._media_state.volume * 100.0))
        self.song_volume_slider.blockSignals(True)
        self.song_volume_slider.setValue(song_volume_percent)
        self.song_volume_slider.blockSignals(False)
        self.song_volume_label.setText(str(song_volume_percent))
        hitsound_volume_percent = int(round(self._media_state.hitsound_volume * 100.0))
        self.hitsound_volume_slider.blockSignals(True)
        self.hitsound_volume_slider.setValue(hitsound_volume_percent)
        self.hitsound_volume_slider.blockSignals(False)
        self.hitsound_volume_label.setText(str(hitsound_volume_percent))

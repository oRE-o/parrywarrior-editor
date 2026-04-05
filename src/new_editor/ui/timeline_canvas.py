from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QLineF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QWidget

from ..core.legacy_rules import snap_duration_ms
from ..core.media import MediaState
from ..core.models import Chart, Note
from ..core.timeline import (
    TimelineGeometry,
    TimelineToolState,
    centered_lane_end_x,
    centered_lane_start_x,
    judgment_line_y,
    screen_y_to_time,
    time_to_screen_y,
)
from .tokens import PALETTE, RADII, SPACE, color_to_hex


TimelineClickHandler = Callable[[float, float, int, int], None]
TimelineScrubHandler = Callable[[float, bool, bool], None]
TimelineNudgeHandler = Callable[[float], None]


class TimelineCanvasWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(SPACE.xxl * 10)
        self.setMinimumWidth(0)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        self._chart = Chart()
        self._media_state = MediaState()
        self._tool_state = TimelineToolState()
        self._timeline_geometry = TimelineGeometry()
        self._preview_mouse_y: float | None = None

        self._primary_click_handler: TimelineClickHandler | None = None
        self._secondary_click_handler: TimelineClickHandler | None = None
        self._scrub_handler: TimelineScrubHandler | None = None
        self._nudge_handler: TimelineNudgeHandler | None = None

    def sizeHint(self) -> QSize:
        return QSize(720, SPACE.xxl * 12)

    def bind_actions(
        self,
        *,
        primary_click: TimelineClickHandler,
        secondary_click: TimelineClickHandler,
        scrub: TimelineScrubHandler,
        nudge: TimelineNudgeHandler,
    ) -> None:
        self._primary_click_handler = primary_click
        self._secondary_click_handler = secondary_click
        self._scrub_handler = scrub
        self._nudge_handler = nudge

    def set_chart(self, chart: Chart) -> None:
        self._chart = chart
        self.update()

    def set_media_state(self, media_state: MediaState) -> None:
        self._media_state = media_state
        self.update()

    def set_tool_state(self, tool_state: TimelineToolState) -> None:
        self._tool_state = tool_state
        if tool_state.pending_long_note is None:
            self._preview_mouse_y = None
        self.update()

    def set_timeline_geometry(self, timeline_geometry: TimelineGeometry) -> None:
        self._timeline_geometry = timeline_geometry
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        position = event.position()
        if event.button() == Qt.MouseButton.LeftButton and self._primary_click_handler is not None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._preview_mouse_y = float(position.y())
            self._primary_click_handler(float(position.x()), float(position.y()), self.width(), self.height())
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self._secondary_click_handler is not None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._secondary_click_handler(float(position.x()), float(position.y()), self.width(), self.height())
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._scrub_handler is None:
            super().wheelEvent(event)
            return

        angle_delta_y = event.angleDelta().y()
        if angle_delta_y == 0:
            super().wheelEvent(event)
            return

        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._scrub_handler(
            float(angle_delta_y) / 120.0,
            alt_pressed=bool(event.modifiers() & Qt.KeyboardModifier.AltModifier),
            ctrl_pressed=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier),
        )
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._nudge_handler is None:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Up:
            self._nudge_handler(1.0)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self._nudge_handler(-1.0)
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._tool_state.pending_long_note is not None:
            self._preview_mouse_y = self._clamp_y(float(event.position().y()))
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        if self._tool_state.pending_long_note is not None:
            self._preview_mouse_y = None
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)

        panel_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if panel_rect.width() <= 1 or panel_rect.height() <= 1:
            return

        painter.setPen(QPen(QColor(PALETTE.panel_border), 1.0))
        painter.setBrush(QColor(PALETTE.panel_bg_alt))
        painter.drawRoundedRect(panel_rect, float(RADII.md), float(RADII.md))

        lane_start_x = centered_lane_start_x(self.width(), self._chart.num_lanes, self._timeline_geometry)
        lane_end_x = centered_lane_end_x(self.width(), self._chart.num_lanes, self._timeline_geometry)
        lane_rect = QRectF(
            lane_start_x,
            panel_rect.top() + 1.0,
            max(0.0, lane_end_x - lane_start_x),
            max(0.0, panel_rect.height() - 2.0),
        )
        if lane_rect.width() > 0:
            painter.fillRect(lane_rect, QColor(PALETTE.panel_bg))

        current_note_time_ms = self._current_note_time_ms()
        self._draw_grid(painter, lane_start_x, lane_end_x, current_note_time_ms)
        self._draw_lane_boundaries(painter, lane_start_x)
        self._draw_notes(painter, current_note_time_ms)
        self._draw_pending_long_preview(painter, current_note_time_ms)
        self._draw_playhead(painter, lane_start_x, lane_end_x, current_note_time_ms)
        self._draw_judgment_line(painter, lane_start_x, lane_end_x)

    def _draw_grid(
        self,
        painter: QPainter,
        lane_start_x: float,
        lane_end_x: float,
        current_note_time_ms: float,
    ) -> None:
        if lane_end_x <= lane_start_x:
            return

        beat_duration_ms = 60000.0 / self._chart.bpm if self._chart.bpm > 0 else 500.0
        snap_ms = snap_duration_ms(self._chart.bpm, self._tool_state.snap_division)
        if snap_ms <= 0:
            return

        time_at_top = screen_y_to_time(0.0, current_note_time_ms, self.height(), self._timeline_geometry)
        time_at_bottom = screen_y_to_time(float(self.height()), current_note_time_ms, self.height(), self._timeline_geometry)

        current_snap_time = math.floor(time_at_bottom / snap_ms) * snap_ms
        while current_snap_time <= time_at_top:
            y = time_to_screen_y(current_snap_time, current_note_time_ms, self.height(), self._timeline_geometry)
            if 0.0 <= y <= self.height():
                beat_count_float = current_snap_time / beat_duration_ms
                beat_count_int = round(beat_count_float)

                color = PALETTE.panel_border
                width = 1.0
                if abs(beat_count_float - beat_count_int) < 0.001:
                    if beat_count_int % 4 == 0:
                        color = PALETTE.danger
                        width = 2.0
                    else:
                        color = PALETTE.text_secondary
                painter.setPen(QPen(QColor(color), width))
                painter.drawLine(QLineF(lane_start_x, y, lane_end_x, y))
            current_snap_time += snap_ms

    def _draw_lane_boundaries(self, painter: QPainter, lane_start_x: float) -> None:
        lane_count = max(1, self._chart.num_lanes)
        painter.setPen(QPen(QColor(PALETTE.panel_border), 1.0))
        for lane_index in range(lane_count + 1):
            x = lane_start_x + (lane_index * self._timeline_geometry.lane_width_pixels)
            painter.drawLine(QLineF(x, 0.0, x, float(self.height())))

    def _draw_notes(self, painter: QPainter, current_note_time_ms: float) -> None:
        for note in self._chart.notes:
            if note.end_time_ms is not None:
                self._draw_long_note(painter, note, current_note_time_ms)
        for note in self._chart.notes:
            if note.end_time_ms is None:
                self._draw_tap_note(painter, note, current_note_time_ms)

    def _draw_long_note(self, painter: QPainter, note: Note, current_note_time_ms: float) -> None:
        note_type = self._chart.note_types.get(note.note_type_name)
        if note_type is None or note.end_time_ms is None:
            return

        lane_x = self._lane_x(note.lane)
        note_start_y = time_to_screen_y(note.time_ms, current_note_time_ms, self.height(), self._timeline_geometry)
        note_end_y = time_to_screen_y(note.end_time_ms, current_note_time_ms, self.height(), self._timeline_geometry)
        top_y = min(note_start_y, note_end_y)
        height = abs(note_start_y - note_end_y)
        if note_start_y < 0 and note_end_y < 0:
            return
        if note_start_y > self.height() and note_end_y > self.height():
            return

        body_color = QColor(color_to_hex(note_type.color))
        outline_color = QColor(PALETTE.text_primary)
        body_rect = QRectF(lane_x + 1.0, top_y, self._timeline_geometry.lane_width_pixels - 2.0, max(1.0, height))
        painter.setPen(QPen(outline_color, 1.0))
        painter.setBrush(body_color)
        painter.drawRect(body_rect)

        cap_color = body_color.darker(145)
        cap_rect = QRectF(
            lane_x + 1.0,
            note_start_y - float(SPACE.sm),
            self._timeline_geometry.lane_width_pixels - 2.0,
            float(SPACE.sm),
        )
        painter.setBrush(cap_color)
        painter.drawRect(cap_rect)

    def _draw_tap_note(self, painter: QPainter, note: Note, current_note_time_ms: float) -> None:
        note_type = self._chart.note_types.get(note.note_type_name)
        if note_type is None:
            return

        note_y = time_to_screen_y(note.time_ms, current_note_time_ms, self.height(), self._timeline_geometry)
        if note_y < -float(SPACE.sm) or note_y > self.height() + float(SPACE.sm):
            return

        note_rect = QRectF(
            self._lane_x(note.lane) + 1.0,
            note_y - float(SPACE.sm),
            self._timeline_geometry.lane_width_pixels - 2.0,
            float(SPACE.sm),
        )
        painter.setPen(QPen(QColor(PALETTE.text_primary), 1.0))
        painter.setBrush(QColor(color_to_hex(note_type.color)))
        painter.drawRect(note_rect)

    def _draw_pending_long_preview(self, painter: QPainter, current_note_time_ms: float) -> None:
        pending_long_note = self._tool_state.pending_long_note
        preview_mouse_y = self._preview_mouse_y
        if pending_long_note is None or preview_mouse_y is None:
            return

        note_type = self._chart.note_types.get(pending_long_note.type_name)
        if note_type is None:
            return

        start_y = time_to_screen_y(pending_long_note.time_ms, current_note_time_ms, self.height(), self._timeline_geometry)
        preview_rect = QRectF(
            self._lane_x(pending_long_note.lane) + 1.0,
            min(start_y, preview_mouse_y),
            self._timeline_geometry.lane_width_pixels - 2.0,
            abs(start_y - preview_mouse_y),
        )
        preview_color = QColor(color_to_hex(note_type.color))
        preview_color.setAlpha(140)
        painter.setPen(QPen(QColor(PALETTE.text_primary), 1.0, Qt.PenStyle.DashLine))
        painter.setBrush(preview_color)
        painter.drawRect(preview_rect)

    def _draw_playhead(
        self,
        painter: QPainter,
        lane_start_x: float,
        lane_end_x: float,
        current_note_time_ms: float,
    ) -> None:
        if lane_end_x <= lane_start_x:
            return
        playhead_y = time_to_screen_y(self._media_state.position_ms, current_note_time_ms, self.height(), self._timeline_geometry)
        if not 0.0 <= playhead_y <= self.height():
            return
        painter.setPen(QPen(QColor(PALETTE.accent_strong), 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QLineF(lane_start_x, playhead_y, lane_end_x, playhead_y))

    def _draw_judgment_line(self, painter: QPainter, lane_start_x: float, lane_end_x: float) -> None:
        if lane_end_x <= lane_start_x:
            return
        y = judgment_line_y(self.height(), self._timeline_geometry)
        painter.setPen(QPen(QColor(PALETTE.warning), 3.0))
        painter.drawLine(QLineF(lane_start_x, y, lane_end_x, y))

    def _lane_x(self, lane: int) -> float:
        return centered_lane_start_x(self.width(), self._chart.num_lanes, self._timeline_geometry) + (
            lane * self._timeline_geometry.lane_width_pixels
        )

    def _current_note_time_ms(self) -> float:
        return float(self._media_state.position_ms) + self._chart.offset_ms

    def _clamp_y(self, y_position: float) -> float:
        return min(float(self.height()), max(0.0, y_position))

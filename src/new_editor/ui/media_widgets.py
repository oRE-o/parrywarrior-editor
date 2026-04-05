from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QLineF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.timeline import TimelineGeometry, judgment_line_y, screen_y_to_time
from ..core.media import MediaState, PlaybackState
from .tokens import PALETTE, RADII, SPACE


OverviewSeekHandler = Callable[[float, int], None]
TimelineNudgeHandler = Callable[[float], None]
TransportSeekHandler = Callable[[float], None]


def format_media_time(milliseconds: int | float) -> str:
    total_ms = max(0, int(milliseconds))
    minutes, remainder = divmod(total_ms, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def source_name(path_text: str, *, fallback: str = "No song") -> str:
    if not path_text:
        return fallback
    return Path(path_text).name or fallback


def effective_duration_ms(media_state: MediaState) -> int:
    if media_state.duration_ms > 0:
        return media_state.duration_ms
    return int(media_state.waveform.duration_ms)


def playback_state_label(media_state: MediaState) -> str:
    if media_state.error_message:
        return "Unavailable"
    if not media_state.is_song_loaded:
        return "Unavailable"
    if media_state.playback_state == PlaybackState.PLAYING:
        return "Playing"
    if media_state.playback_state == PlaybackState.PAUSED:
        return "Paused"
    return "Stopped"


def media_status_text(media_state: MediaState) -> str:
    if media_state.error_message:
        return media_state.error_message
    if media_state.playback_state == PlaybackState.PLAYING:
        return "Playing"
    if media_state.playback_state == PlaybackState.PAUSED:
        return "Paused"
    if media_state.is_song_loaded:
        return "Ready"
    return "No song loaded"


def waveform_detail_text(media_state: MediaState) -> str:
    if media_state.waveform.is_available:
        return f"Waveform · {len(media_state.waveform.peak_values)} pts · click to seek"
    if media_state.waveform.limitation:
        return media_state.waveform.limitation
    if media_state.is_song_loaded:
        return "Waveform loading"
    return ""


class WaveformPreviewWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._media_state = MediaState()
        self._timeline_geometry = TimelineGeometry()
        self._seek_handler: OverviewSeekHandler | None = None
        self._nudge_handler: TimelineNudgeHandler | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(SPACE.xxl * 6)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def sizeHint(self) -> QSize:
        return QSize(200, SPACE.xxl * 6)

    def set_media_state(self, media_state: MediaState) -> None:
        self._media_state = media_state
        self.update()

    def bind_actions(
        self,
        *,
        seek: OverviewSeekHandler,
        nudge: TimelineNudgeHandler,
    ) -> None:
        self._seek_handler = seek
        self._nudge_handler = nudge

    def set_timeline_geometry(self, timeline_geometry: TimelineGeometry) -> None:
        self._timeline_geometry = timeline_geometry
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._seek_handler is not None:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self._seek_handler(float(event.position().y()), self.height())
            event.accept()
            return
        super().mousePressEvent(event)

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

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)

        outer_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(QColor(PALETTE.panel_border), 1.0))
        painter.setBrush(QColor(PALETTE.panel_bg_alt))
        painter.drawRoundedRect(outer_rect, float(RADII.md), float(RADII.md))

        inner_rect = outer_rect.adjusted(float(SPACE.md), float(SPACE.md), -float(SPACE.md), -float(SPACE.md))
        if inner_rect.width() <= 0 or inner_rect.height() <= 0:
            return

        self._draw_center_line(painter, inner_rect)
        self._draw_waveform(painter, inner_rect)
        self._draw_judgment_line(painter, inner_rect)

    def _draw_center_line(self, painter: QPainter, inner_rect: QRectF) -> None:
        baseline_pen = QPen(QColor(PALETTE.panel_border), 1.0)
        painter.setPen(baseline_pen)
        painter.drawLine(QLineF(inner_rect.center().x(), inner_rect.top(), inner_rect.center().x(), inner_rect.bottom()))

    def _draw_waveform(self, painter: QPainter, inner_rect: QRectF) -> None:
        waveform = self._media_state.waveform
        samples = waveform.peak_values
        duration_ms = effective_duration_ms(self._media_state)
        if not samples or duration_ms <= 0:
            empty_pen = QPen(QColor(PALETTE.text_muted), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(empty_pen)
            painter.drawLine(QLineF(inner_rect.left(), inner_rect.top(), inner_rect.right(), inner_rect.bottom()))
            return

        center_x = inner_rect.center().x()
        half_width = max(1.0, (inner_rect.width() / 2.0) - float(SPACE.sm))
        waveform_pen = QPen(QColor(PALETTE.accent), 1.0)
        painter.setPen(waveform_pen)

        for y_pixel in range(math.ceil(inner_rect.top()), math.floor(inner_rect.bottom()) + 1):
            min_value, max_value = self._amplitude_range_for_y(y_pixel, duration_ms, len(samples))
            if max_value <= min_value:
                continue
            x_left = center_x + (min_value * half_width)
            x_right = center_x + (max_value * half_width)
            painter.drawLine(QLineF(x_left, float(y_pixel), x_right, float(y_pixel)))

    def _draw_judgment_line(self, painter: QPainter, inner_rect: QRectF) -> None:
        line_y = judgment_line_y(self.height(), self._timeline_geometry)
        if line_y < inner_rect.top() or line_y > inner_rect.bottom():
            return
        painter.setPen(QPen(QColor(PALETTE.warning), 2.0))
        painter.drawLine(QLineF(inner_rect.left(), line_y, inner_rect.right(), line_y))

    def _amplitude_range_for_y(self, y_position: int, duration_ms: int, sample_count: int) -> tuple[float, float]:
        if sample_count <= 0 or duration_ms <= 0:
            return (0.0, 0.0)

        start_time_ms = screen_y_to_time(y_position + 0.5, float(self._media_state.position_ms), self.height(), self._timeline_geometry)
        end_time_ms = screen_y_to_time(y_position - 0.5, float(self._media_state.position_ms), self.height(), self._timeline_geometry)
        min_time_ms = max(0.0, min(start_time_ms, end_time_ms))
        max_time_ms = min(float(duration_ms), max(start_time_ms, end_time_ms))
        if max_time_ms <= min_time_ms:
            return (0.0, 0.0)

        start_index = max(0, min(sample_count - 1, int(math.floor((min_time_ms / duration_ms) * sample_count))))
        end_index = max(start_index + 1, min(sample_count, int(math.ceil((max_time_ms / duration_ms) * sample_count))))
        if start_index >= end_index:
            return (0.0, 0.0)
        waveform = self._media_state.waveform
        if waveform.min_values and waveform.max_values:
            return (
                max(-1.0, min(waveform.min_values[start_index:end_index])),
                min(1.0, max(waveform.max_values[start_index:end_index])),
            )
        peak = min(1.0, max(waveform.peak_values[start_index:end_index]))
        return (-peak, peak)


class TransportSeekBarWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._media_state = MediaState()
        self._seek_handler: TransportSeekHandler | None = None
        self._is_dragging = False
        self._display_position_ms = 0.0
        self.setMinimumHeight(SPACE.xl)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    def sizeHint(self) -> QSize:
        return QSize(240, SPACE.xl)

    def bind_actions(self, *, seek: TransportSeekHandler) -> None:
        self._seek_handler = seek

    def set_media_state(self, media_state: MediaState) -> None:
        self._media_state = media_state
        if not self._is_dragging:
            self._display_position_ms = float(media_state.position_ms)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._can_seek():
            self._is_dragging = True
            self._seek_to_x(float(event.position().x()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_dragging and self._can_seek():
            self._seek_to_x(float(event.position().x()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._seek_to_x(float(event.position().x()))
            self._is_dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)

        track_height = float(SPACE.sm)
        handle_diameter = float(SPACE.md)
        track_rect = QRectF(
            float(SPACE.sm),
            (float(self.height()) - track_height) / 2.0,
            max(0.0, float(self.width()) - float(SPACE.lg)),
            track_height,
        )
        if track_rect.width() <= 0.0:
            return

        duration_ms = float(effective_duration_ms(self._media_state))
        progress_ratio = 0.0
        if duration_ms > 0.0:
            progress_ratio = min(1.0, max(0.0, self._display_position_ms / duration_ms))
        progress_width = track_rect.width() * progress_ratio

        painter.setPen(QPen(QColor(PALETTE.panel_border), 1.0))
        painter.setBrush(QColor(PALETTE.panel_bg))
        painter.drawRoundedRect(track_rect, track_height / 2.0, track_height / 2.0)

        if progress_width > 0.0:
            progress_rect = QRectF(track_rect.left(), track_rect.top(), progress_width, track_rect.height())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(PALETTE.accent_soft if self._can_seek() else PALETTE.panel_border))
            painter.drawRoundedRect(progress_rect, track_height / 2.0, track_height / 2.0)

        handle_center_x = track_rect.left() + progress_width
        handle_center_x = min(track_rect.right(), max(track_rect.left(), handle_center_x))
        handle_rect = QRectF(
            handle_center_x - (handle_diameter / 2.0),
            (float(self.height()) - handle_diameter) / 2.0,
            handle_diameter,
            handle_diameter,
        )
        painter.setPen(QPen(QColor(PALETTE.panel_border), 1.0))
        painter.setBrush(QColor(PALETTE.accent if self._can_seek() else PALETTE.text_muted))
        painter.drawEllipse(handle_rect)

    def _can_seek(self) -> bool:
        return effective_duration_ms(self._media_state) > 0 and self._seek_handler is not None

    def _seek_to_x(self, x_position: float) -> None:
        duration_ms = float(effective_duration_ms(self._media_state))
        if duration_ms <= 0.0 or self._seek_handler is None:
            return
        usable_width = max(1.0, float(self.width()) - float(SPACE.lg))
        progress_ratio = min(1.0, max(0.0, (x_position - float(SPACE.sm)) / usable_width))
        target_position_ms = duration_ms * progress_ratio
        self._display_position_ms = target_position_ms
        self._seek_handler(target_position_ms)
        self.update()

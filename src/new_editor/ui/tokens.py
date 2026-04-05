from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..core.models import Chart, Color


@dataclass(frozen=True, slots=True)
class Palette:
    app_bg: str = "#0E1016"
    panel_bg: str = "#171B24"
    panel_bg_alt: str = "#11151D"
    panel_border: str = "#293244"
    accent: str = "#64D7FF"
    accent_soft: str = "#183549"
    accent_strong: str = "#9BE7FF"
    text_primary: str = "#F4F1E8"
    text_secondary: str = "#B4BDCA"
    text_muted: str = "#7D8797"
    success: str = "#77E4A7"
    warning: str = "#FFCC72"
    danger: str = "#FF8C8C"


@dataclass(frozen=True, slots=True)
class SpacingScale:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


@dataclass(frozen=True, slots=True)
class RadiusScale:
    sm: int = 8
    md: int = 12
    lg: int = 18


@dataclass(frozen=True, slots=True)
class TypographyScale:
    eyebrow: int = 11
    body: int = 13
    section: int = 16
    headline: int = 22
    hero: int = 28


@dataclass(frozen=True, slots=True)
class ShellLayout:
    minimum_width: int = 720
    minimum_height: int = 720
    left_panel_width: int = 240
    right_panel_width: int = 288
    transport_height: int = 76


PALETTE = Palette()
SPACE = SpacingScale()
RADII = RadiusScale()
TYPE_SCALE = TypographyScale()
SHELL = ShellLayout()


def format_chart_path(chart: Chart) -> str:
    return chart.chart_path if chart.chart_path else "Unsaved chart"


def format_song_path(chart: Chart) -> str:
    return chart.song_path if chart.song_path else "No song linked yet"


def format_file_name(path_text: str, *, fallback: str) -> str:
    if not path_text:
        return fallback
    return Path(path_text).name or fallback


def color_to_hex(color: Color) -> str:
    return "#" + "".join(f"{channel:02X}" for channel in color)

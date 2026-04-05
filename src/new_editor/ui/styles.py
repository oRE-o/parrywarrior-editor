from __future__ import annotations

from .tokens import PALETTE, RADII, SPACE, TYPE_SCALE


def build_app_stylesheet() -> str:
    return f"""
    QMainWindow {{
        background-color: {PALETTE.app_bg};
        color: {PALETTE.text_primary};
    }}

    QWidget {{
        background-color: transparent;
        color: {PALETTE.text_primary};
        font-family: "Pretendard Variable", "Pretendard", "Apple SD Gothic Neo", "Arial";
        font-size: {TYPE_SCALE.body}px;
    }}

    QDialog {{
        background-color: {PALETTE.panel_bg};
    }}

    QMenuBar {{
        background-color: {PALETTE.panel_bg};
        border-bottom: 1px solid {PALETTE.panel_border};
        padding: {SPACE.xs}px {SPACE.sm}px;
    }}

    QMenuBar::item {{
        background: transparent;
        padding: {SPACE.xs + 2}px {SPACE.md}px;
        border-radius: {RADII.sm}px;
    }}

    QMenuBar::item:selected,
    QMenu::item:selected {{
        background-color: {PALETTE.accent_soft};
        color: {PALETTE.text_primary};
    }}

    QMenu {{
        background-color: {PALETTE.panel_bg};
        border: 1px solid {PALETTE.panel_border};
        padding: {SPACE.sm}px;
    }}

    QStatusBar {{
        background-color: {PALETTE.panel_bg};
        border-top: 1px solid {PALETTE.panel_border};
        color: {PALETTE.text_secondary};
    }}

    QLabel[role="eyebrow"] {{
        color: {PALETTE.accent_strong};
        font-size: {TYPE_SCALE.eyebrow}px;
        font-weight: 700;
    }}

    QLabel[role="headline"] {{
        color: {PALETTE.text_primary};
        font-size: {TYPE_SCALE.hero}px;
        font-weight: 700;
    }}

    QLabel[role="meta"] {{
        color: {PALETTE.text_secondary};
        font-size: {TYPE_SCALE.eyebrow}px;
        font-weight: 600;
    }}

    QLabel[role="section"] {{
        color: {PALETTE.text_primary};
        font-size: {TYPE_SCALE.section}px;
        font-weight: 700;
    }}

    QLabel[role="muted"] {{
        color: {PALETTE.text_muted};
    }}

    QLabel[role="secondary"] {{
        color: {PALETTE.text_secondary};
    }}

    QFrame#panelCard,
    QFrame#placeholderPanel,
    QFrame#transportBar {{
        background-color: {PALETTE.panel_bg};
        border: 1px solid {PALETTE.panel_border};
        border-radius: {RADII.md}px;
    }}

    QFrame#placeholderPanel {{
        background-color: {PALETTE.panel_bg_alt};
    }}

    QFrame#transportBar {{
        background-color: {PALETTE.panel_bg_alt};
    }}

    QPushButton {{
        background-color: {PALETTE.accent_soft};
        color: {PALETTE.text_primary};
        border: 1px solid {PALETTE.panel_border};
        border-radius: {RADII.md}px;
        padding: {SPACE.xs + 2}px {SPACE.md}px;
        font-weight: 600;
        min-height: {SPACE.xl}px;
    }}

    QPushButton:hover {{
        border-color: {PALETTE.accent};
    }}

    QPushButton:disabled {{
        background-color: {PALETTE.panel_bg_alt};
        color: {PALETTE.text_muted};
        border-color: {PALETTE.panel_border};
    }}

    QListWidget,
    QPlainTextEdit,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox {{
        background-color: {PALETTE.panel_bg_alt};
        border: 1px solid {PALETTE.panel_border};
        border-radius: {RADII.md}px;
        padding: {SPACE.xs + 2}px {SPACE.sm}px;
    }}

    QComboBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox {{
        min-height: {SPACE.xl}px;
    }}

    QLineEdit[readOnly="true"] {{
        color: {PALETTE.text_muted};
    }}

    QComboBox::drop-down {{
        border: 0;
        width: {SPACE.xxl}px;
    }}

    QComboBox QAbstractItemView,
    QListWidget::item:selected {{
        background-color: {PALETTE.accent_soft};
        color: {PALETTE.text_primary};
        border-radius: {RADII.sm}px;
    }}

    QListWidget::item {{
        padding: {SPACE.xs}px {SPACE.sm}px;
        margin: 0;
    }}

    QCheckBox {{
        spacing: {SPACE.sm}px;
        color: {PALETTE.text_secondary};
    }}

    QCheckBox::indicator {{
        width: {SPACE.lg}px;
        height: {SPACE.lg}px;
        border-radius: {SPACE.xs}px;
        border: 1px solid {PALETTE.panel_border};
        background-color: {PALETTE.panel_bg_alt};
    }}

    QCheckBox::indicator:checked {{
        background-color: {PALETTE.accent};
        border-color: {PALETTE.accent};
    }}

    QSlider::groove:horizontal {{
        background-color: {PALETTE.panel_bg_alt};
        border: 1px solid {PALETTE.panel_border};
        border-radius: {SPACE.xs}px;
        height: {SPACE.sm}px;
    }}

    QSlider::sub-page:horizontal {{
        background-color: {PALETTE.accent_soft};
        border-radius: {SPACE.xs}px;
    }}

    QSlider::add-page:horizontal {{
        background-color: {PALETTE.panel_bg};
        border-radius: {SPACE.xs}px;
    }}

    QSlider::handle:horizontal {{
        background-color: {PALETTE.accent};
        border: 1px solid {PALETTE.panel_border};
        border-radius: {SPACE.sm}px;
        width: {SPACE.md}px;
        margin: -{SPACE.xs}px 0;
    }}

    QSplitter::handle {{
        background-color: {PALETTE.app_bg};
    }}
    """

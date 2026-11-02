from __future__ import annotations

import time

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QFileInfo,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QFileIconProvider,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from logger import log
from search import Entry, SearchIndex, open_entry, web_entry
from visuals import (
    accent_color,
    blur_image,
    force_foreground,
    is_light_theme,
    ui_font,
)

FIELD_HEIGHT = 64
FOOTER_HEIGHT = 38
HEADER_HEIGHT = 32
ROW_HEIGHT = 46
PANEL_MAX_WIDTH = 640
PANEL_MAX_HEIGHT = 440
PANEL_RADIUS = 14.0

GROUP_LABELS = {
    "apps": "APPS",
    "files": "FILES",
    "folders": "FOLDERS",
    "settings": "SETTINGS",
    "web": "WEB",
}


class Theme:
    def __init__(self, light: bool):
        self.light = light
        if light:
            self.text = QColor(22, 22, 26, 242)
            self.subtitle = QColor(22, 22, 26, 145)
            self.input_text = "rgba(22, 22, 26, 242)"
            self.selection_bg = "rgba(80, 120, 220, 66)"
            self.selection_fg = "#16161a"
            self.caret = "#16161a"
            self.placeholder = QColor(22, 22, 26, 96)
            self.glass_tint = QColor(249, 249, 251, 200)
            self.fallback = QColor(250, 250, 252, 244)
            self.border = QColor(0, 0, 0, 30)
            self.divider = QColor(0, 0, 0, 20)
            self.header = QColor(22, 22, 26, 100)
            self.glyph = QColor(22, 22, 26, 118)
            self.icon_glyph = QColor(22, 22, 26, 210)
            self.close = QColor(22, 22, 26)
            self.hover_alpha = 16
            self.keycap_fg = "rgba(22, 22, 26, 170)"
            self.keycap_bg = "rgba(22, 22, 26, 14)"
            self.hint_fg = "rgba(22, 22, 26, 110)"
            self.scroll_handle = "rgba(22, 22, 26, 42)"
            self.scroll_handle_hover = "rgba(22, 22, 26, 72)"
            self.sheen_top = 90
            self.sheen_low = 26
        else:
            self.text = QColor(255, 255, 255, 243)
            self.subtitle = QColor(255, 255, 255, 127)
            self.input_text = "rgba(255, 255, 255, 246)"
            self.selection_bg = "rgba(255, 255, 255, 46)"
            self.selection_fg = "#ffffff"
            self.caret = "#ffffff"
            self.placeholder = QColor(255, 255, 255, 94)
            self.glass_tint = QColor(20, 20, 24, 152)
            self.fallback = QColor(26, 26, 30, 235)
            self.border = QColor(255, 255, 255, 34)
            self.divider = QColor(255, 255, 255, 22)
            self.header = QColor(255, 255, 255, 112)
            self.glyph = QColor(255, 255, 255, 112)
            self.icon_glyph = QColor(255, 255, 255, 222)
            self.close = QColor(255, 255, 255)
            self.hover_alpha = 22
            self.keycap_fg = "rgba(255, 255, 255, 182)"
            self.keycap_bg = "rgba(255, 255, 255, 20)"
            self.hint_fg = "rgba(255, 255, 255, 108)"
            self.scroll_handle = "rgba(255, 255, 255, 50)"
            self.scroll_handle_hover = "rgba(255, 255, 255, 82)"
            self.sheen_top = 17
            self.sheen_low = 6


def input_qss(theme: Theme) -> str:
    return f"""
QLineEdit {{
    background: transparent;
    border: none;
    padding: 0;
    color: {theme.input_text};
    selection-background-color: {theme.selection_bg};
    selection-color: {theme.selection_fg};
    caret-color: {theme.caret};
}}
"""


def scroll_qss(theme: Theme) -> str:
    return f"""
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 6px 2px 6px 0;
}}
QScrollBar::handle:vertical {{
    background: {theme.scroll_handle};
    min-height: 26px;
    border-radius: 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {theme.scroll_handle_hover}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


def keycap_qss(theme: Theme) -> str:
    return f"""
QLabel {{
    color: {theme.keycap_fg};
    background-color: {theme.keycap_bg};
    border-radius: 4px;
    padding: 1px 6px;
    font-family: "Segoe UI Symbol", "Segoe UI";
    font-size: 10px;
    font-weight: 600;
}}
"""


def hint_qss(theme: Theme) -> str:
    return f"""
QLabel {{ color: {theme.hint_fg}; font-size: 11px; }}
"""


class SearchGlyph(QWidget):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setFixedSize(18, 18)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(self._theme.glyph, 1.7)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(3.0, 3.0, 10.2, 10.2))
        painter.drawLine(QPointF(12.3, 12.3), QPointF(16.2, 16.2))


class CloseButton(QAbstractButton):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._hover = 0.0
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip("Close")
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(120)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim.valueChanged.connect(self._on_hover)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def _on_hover(self, value):
        self._hover = float(value)
        self.update()

    def _animate_hover(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(float(self._hover))
        self._anim.setEndValue(float(target))
        self._anim.start()

    def enterEvent(self, event):
        self._animate_hover(1.0)

    def leaveEvent(self, event):
        self._animate_hover(0.0)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._hover > 0.01:
            painter.setPen(Qt.PenStyle.NoPen)
            fill = QColor(self._theme.close)
            fill.setAlpha(int(self._theme.hover_alpha * self._hover))
            painter.setBrush(fill)
            painter.drawEllipse(QRectF(1.5, 1.5, 25, 25))

        color = QColor(self._theme.close)
        color.setAlpha(int(96 + 138 * self._hover))
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(10.4, 10.4), QPointF(17.6, 17.6))
        painter.drawLine(QPointF(17.6, 10.4), QPointF(10.4, 17.6))


class Divider(QWidget):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setFixedHeight(1)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(
            QRect(16, 0, max(0, self.width() - 32), 1),
            self._theme.divider,
        )


class GroupHeader(QWidget):
    def __init__(self, text: str, theme: Theme, parent=None):
        super().__init__(parent)
        self._text = text
        self._theme = theme
        self.setFixedHeight(HEADER_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._font = ui_font(10, QFont.Weight.DemiBold)
        self._font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(self._font)
        painter.setPen(self._theme.header)
        painter.drawText(
            QRectF(12, 6, max(0, self.width() - 24), 24),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._text,
        )


class ResultRow(QWidget):
    def __init__(
        self,
        entry: Entry,
        icon: QPixmap | None,
        glyph_family: str,
        accent: QColor,
        theme: Theme,
        parent=None,
    ):
        super().__init__(parent)
        self.entry = entry
        self._icon = icon
        self._accent = accent
        self._theme = theme
        self._active = False
        self.index = -1
        self.on_hover = None
        self.on_click = None

        self.setFixedHeight(ROW_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

        self._title_font = ui_font(14, QFont.Weight.Medium)
        self._subtitle_font = ui_font(12)
        self._title_metrics = QFontMetrics(self._title_font)
        self._subtitle_metrics = QFontMetrics(self._subtitle_font)
        self._glyph_font = QFont(glyph_family)
        self._glyph_font.setPixelSize(20)

    def set_active(self, active: bool) -> None:
        if self._active != active:
            self._active = active
            self.update()

    def enterEvent(self, event):
        if callable(self.on_hover):
            self.on_hover(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if callable(self.on_click):
                self.on_click(self)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        width = self.width()
        height = self.height()
        theme = self._theme

        if self._active:
            highlight = QColor(self._accent)
            highlight.setAlphaF(0.26)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(highlight)
            painter.drawRoundedRect(
                QRectF(self.rect()).adjusted(2.0, 1.0, -2.0, -1.0), 8.0, 8.0
            )

        icon_rect = QRectF(12.0, (height - 26) / 2.0, 26.0, 26.0)
        if self._icon is not None and not self._icon.isNull():
            painter.drawPixmap(icon_rect, self._icon, QRectF(self._icon.rect()))
        elif self.entry.glyph:
            painter.setFont(self._glyph_font)
            painter.setPen(theme.icon_glyph)
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self.entry.glyph)

        text_x = 50.0
        text_width = max(10, int(width - text_x - 12))

        painter.setFont(self._title_font)
        painter.setPen(theme.text)
        title = self._title_metrics.elidedText(
            self.entry.title, Qt.TextElideMode.ElideRight, text_width
        )
        painter.drawText(
            QRectF(text_x, 5.0, text_width, 19.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )

        painter.setFont(self._subtitle_font)
        painter.setPen(theme.subtitle)
        subtitle = self._subtitle_metrics.elidedText(
            self.entry.subtitle, Qt.TextElideMode.ElideRight, text_width
        )
        painter.drawText(
            QRectF(text_x, 23.0, text_width, 16.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            subtitle,
        )


class GlassPanel(QWidget):
    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._background = QImage()
        self.setMinimumSize(1, 1)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_background(self, image: QImage) -> None:
        self._background = image
        self.update()

    def mousePressEvent(self, event):
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, PANEL_RADIUS, PANEL_RADIUS)
        theme = self._theme

        painter.save()
        painter.setClipPath(path)
        if not self._background.isNull():
            painter.drawImage(self.rect(), self._background)
        else:
            painter.fillRect(self.rect(), theme.fallback)
        painter.fillRect(self.rect(), theme.glass_tint)

        sheen = QLinearGradient(0, 0, 0, self.height())
        sheen.setColorAt(0.0, QColor(255, 255, 255, theme.sheen_top))
        sheen.setColorAt(0.12, QColor(255, 255, 255, theme.sheen_low))
        sheen.setColorAt(0.5, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), sheen)
        painter.restore()

        painter.setPen(QPen(theme.border, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class SpotlightOverlay(QWidget):
    def __init__(self, index: SearchIndex, parent=None):
        super().__init__(parent)
        self.index = index
        self._accent = accent_color()
        self.theme = Theme(light=is_light_theme())
        self._icon_provider = QFileIconProvider()
        self._icon_cache: dict[tuple[str, int], QPixmap] = {}
        self._bg_cache: dict[tuple[int, int], QImage] = {}
        self._snapshot = QImage()
        self._snap_scale = 1.0
        self._snap_offset = (0.0, 0.0)
        self._screen = None

        families = set(QFontDatabase.families())
        self._glyph_family = (
            "Segoe Fluent Icons" if "Segoe Fluent Icons" in families else "Segoe MDL2 Assets"
        )

        self._backdrop = 0.0
        self._enter_progress = 1.0
        self._base_height = float(FIELD_HEIGHT)
        self._target_height = float(FIELD_HEIGHT)
        self._opened_at = 0.0

        self._results: list[Entry] = []
        self._rows: list[ResultRow] = []
        self._active_index = -1

        self.setWindowTitle("Spotlight")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._build_ui()
        self._build_animations()

        self.index.updated.connect(self._on_index_updated)

    def _build_ui(self) -> None:
        self.panel = GlassPanel(self.theme, self)

        self.field = QWidget(self.panel)
        self.field.setFixedHeight(FIELD_HEIGHT)
        field_layout = QHBoxLayout(self.field)
        field_layout.setContentsMargins(20, 0, 14, 0)
        field_layout.setSpacing(12)

        self.search_glyph = SearchGlyph(self.theme, self.field)

        self.input = QLineEdit(self.field)
        self.input.setFrame(False)
        self.input.setPlaceholderText("Search apps, files, folders and settings")
        self.input.setFont(ui_font(18))
        self.input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.close_button = CloseButton(self.theme, self.field)

        field_layout.addWidget(
            self.search_glyph, 0, Qt.AlignmentFlag.AlignVCenter
        )
        field_layout.addWidget(self.input, 1, Qt.AlignmentFlag.AlignVCenter)
        field_layout.addWidget(
            self.close_button, 0, Qt.AlignmentFlag.AlignVCenter
        )

        self._divider = Divider(self.theme, self.panel)

        self._scroll = QScrollArea(self.panel)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._scroll.viewport().setStyleSheet("background: transparent;")

        self._content = QWidget()
        self._content.setObjectName("scrollContent")
        self._content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 8, 8)
        self._content_layout.setSpacing(2)
        self._scroll.setWidget(self._content)

        self._footer = self._build_footer(self.panel)

        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.field)
        layout.addWidget(self._divider)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._footer)

        self._divider.hide()
        self._scroll.hide()
        self._footer.hide()

        self.input.installEventFilter(self)
        self.input.textChanged.connect(self._on_query_changed)
        self.close_button.clicked.connect(self.close_spotlight)
        self._apply_styles()

    def _apply_styles(self) -> None:
        self.input.setStyleSheet(input_qss(self.theme))
        palette = self.input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, self.theme.placeholder)
        self.input.setPalette(palette)
        self._scroll.setStyleSheet(scroll_qss(self.theme))
        for label in self._keycap_labels:
            label.setStyleSheet(keycap_qss(self.theme))
        for label in self._hint_labels:
            label.setStyleSheet(hint_qss(self.theme))

    def _sync_theme(self) -> None:
        theme = Theme(light=is_light_theme())
        if theme.light == self.theme.light:
            return
        self.theme = theme
        self._accent = accent_color()
        self.panel.set_theme(theme)
        self.search_glyph.set_theme(theme)
        self.close_button.set_theme(theme)
        self._divider.set_theme(theme)
        self._apply_styles()
        self._bg_cache.clear()

    def _build_footer(self, parent: QWidget) -> QWidget:
        footer = QWidget(parent)
        footer.setFixedHeight(FOOTER_HEIGHT)
        footer.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(7)

        self._keycap_labels: list[QLabel] = []
        self._hint_labels: list[QLabel] = []

        def keycap(text: str) -> QLabel:
            label = QLabel(text, footer)
            label.setStyleSheet(keycap_qss(self.theme))
            label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._keycap_labels.append(label)
            return label

        def hint(text: str) -> QLabel:
            label = QLabel(text, footer)
            label.setStyleSheet(hint_qss(self.theme))
            label.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._hint_labels.append(label)
            return label

        layout.addWidget(keycap("↑ ↓"), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(hint("Navigate"), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(10)
        layout.addWidget(keycap("↵"), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(hint("Open"), 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)
        return footer

    def _build_animations(self) -> None:
        self._fade_anim = QVariantAnimation(self)
        self._fade_anim.setDuration(160)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._fade_anim.valueChanged.connect(self._on_fade)

        self._enter_anim = QVariantAnimation(self)
        self._enter_anim.setDuration(180)
        self._enter_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._enter_anim.valueChanged.connect(self._on_enter)

        self._opacity_effect = QGraphicsOpacityEffect(self.panel)
        self._opacity_effect.setOpacity(1.0)
        self.panel.setGraphicsEffect(self._opacity_effect)

        self._opacity_anim = QPropertyAnimation(
            self._opacity_effect, b"opacity", self
        )
        self._opacity_anim.setDuration(180)
        self._opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(40)
        self._search_timer.timeout.connect(self._run_search)

    def show_spotlight(self) -> None:
        if self.isVisible():
            self._focus_input()
            return

        self._sync_theme()
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return

        self._screen = screen
        self.setGeometry(screen.geometry())
        self._capture_snapshot(screen)
        self._reset_state()

        self._opened_at = time.monotonic()
        self.show()
        self.raise_()
        self.activateWindow()
        try:
            force_foreground(int(self.winId()))
        except Exception as exc:  # pragma: no cover - platform guard
            log(f"force_foreground failed: {exc}")
        self._focus_input()

        self._fade_anim.stop()
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

        self._enter_anim.stop()
        self._enter_anim.setStartValue(0.0)
        self._enter_anim.setEndValue(1.0)
        self._enter_anim.start()

        self._opacity_anim.stop()
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.start()

        QTimer.singleShot(0, self._focus_input)
        # O Win+Espaço faz o menu Iniciar abrir e roubar o foco; recupere-o.
        for delay in (140, 320, 620):
            QTimer.singleShot(delay, self._reclaim_focus)
        QTimer.singleShot(1100, self._close_if_inactive)
        log("overlay shown")

    def _reclaim_focus(self) -> None:
        if not self.isVisible():
            return
        self.activateWindow()
        try:
            force_foreground(int(self.winId()))
        except Exception as exc:  # pragma: no cover - platform guard
            log(f"reclaim focus failed: {exc}")
        self._focus_input()

    def _close_if_inactive(self) -> None:
        if self.isVisible() and not self.isActiveWindow():
            self.close_spotlight()

    def close_spotlight(self) -> None:
        if not self.isVisible():
            return
        self._search_timer.stop()
        for animation in (
            self._fade_anim,
            self._enter_anim,
            self._opacity_anim,
        ):
            animation.stop()
        self.hide()
        log("overlay hidden")

    def toggle(self) -> None:
        if self.isVisible():
            self.close_spotlight()
        else:
            self.show_spotlight()

    def _focus_input(self) -> None:
        self.input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.input.deselect()

    def _capture_snapshot(self, screen) -> None:
        self._snapshot = QImage()
        self._snap_scale = 1.0
        self._snap_offset = (0.0, 0.0)

        try:
            pixmap = screen.grabWindow(0)
        except Exception:
            return
        if pixmap.isNull():
            return

        image = pixmap.toImage()
        if image.isNull():
            return

        geometry = screen.geometry()
        virtual = QRect()
        for candidate in QGuiApplication.screens():
            virtual = virtual.united(candidate.geometry())
        dpr = max(1.0, float(screen.devicePixelRatio()))

        whole_desktop = (
            virtual.width() > geometry.width()
            and abs(image.width() - virtual.width() * dpr) <= max(4, int(dpr * 2))
            and abs(image.height() - virtual.height() * dpr) <= max(4, int(dpr * 2))
        )

        if whole_desktop:
            self._snap_offset = (
                float(virtual.x() - geometry.x()),
                float(virtual.y() - geometry.y()),
            )
            logical_width = float(virtual.width())
        else:
            self._snap_offset = (0.0, 0.0)
            logical_width = float(max(1, geometry.width()))

        self._snap_scale = image.width() / logical_width
        self._snapshot = image

    def _reset_state(self) -> None:
        self._search_timer.stop()

        self.input.blockSignals(True)
        self.input.clear()
        self.input.blockSignals(False)

        self._clear_content()
        self._results = []
        self._rows = []
        self._active_index = -1
        self._divider.hide()
        self._scroll.hide()
        self._footer.hide()

        self._target_height = float(FIELD_HEIGHT)
        self._base_height = float(FIELD_HEIGHT)
        self._enter_progress = 0.0
        self._backdrop = 0.0
        self._opacity_effect.setOpacity(0.0)

        self._bg_cache.clear()
        self._refresh_glass()
        self._apply_geometry()

    def _panel_width(self) -> int:
        return max(320, min(PANEL_MAX_WIDTH, self.width() - 80))

    def _max_panel_height(self) -> int:
        return max(
            FIELD_HEIGHT,
            min(PANEL_MAX_HEIGHT, int(self.height() * 0.68), self.height() - 80),
        )

    def _panel_rect(self, width: int, height: int) -> QRect:
        return QRect(
            int(round((self.width() - width) / 2)),
            int(round((self.height() - height) / 2)),
            width,
            height,
        )

    def _refresh_glass(self) -> None:
        width = self._panel_width()
        height = max(1, int(round(self._target_height)))
        self.panel.set_background(self._glass_background(width, height))
        self.update()

    def _glass_background(self, width: int, height: int) -> QImage:
        key = (width, height)
        if key in self._bg_cache:
            return self._bg_cache[key]

        empty = QImage()
        if self._snapshot.isNull() or width <= 0 or height <= 0:
            self._bg_cache[key] = empty
            return empty

        scale = self._snap_scale or 1.0
        offset_x, offset_y = self._snap_offset
        rect = self._panel_rect(width, height)
        margin = 72

        left = int(round((rect.x() - offset_x - margin) * scale))
        top = int(round((rect.y() - offset_y - margin) * scale))
        crop_width = int(round((width + margin * 2) * scale))
        crop_height = int(round((height + margin * 2) * scale))
        crop_rect = QRect(left, top, crop_width, crop_height).intersected(
            self._snapshot.rect()
        )
        if crop_rect.width() < 16 or crop_rect.height() < 16:
            self._bg_cache[key] = empty
            return empty

        crop = self._snapshot.copy(crop_rect)
        dimmer = QPainter(crop)
        dimmer.fillRect(crop.rect(), QColor(0, 0, 0, 41))
        dimmer.end()

        blurred = blur_image(crop, 24.0 * scale, downscale=2)

        panel_x = int(round((rect.x() - offset_x) * scale)) - crop_rect.x()
        panel_y = int(round((rect.y() - offset_y) * scale)) - crop_rect.y()
        panel_w = max(1, int(round(width * scale)))
        panel_h = max(1, int(round(height * scale)))
        center = blurred.copy(
            QRect(panel_x, panel_y, panel_w, panel_h).intersected(blurred.rect())
        )
        if center.isNull() or center.width() < 4 or center.height() < 4:
            self._bg_cache[key] = empty
            return empty

        background = center.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        if len(self._bg_cache) > 28:
            self._bg_cache.clear()
        self._bg_cache[key] = background
        return background

    def _on_fade(self, value) -> None:
        self._backdrop = float(value)
        self.update()

    def _on_enter(self, value) -> None:
        self._enter_progress = float(value)
        self._apply_geometry()

    def _apply_geometry(self) -> None:
        width = self._panel_width()
        scale = 0.96 + 0.04 * self._enter_progress
        panel_width = max(1, int(round(width * scale)))
        panel_height = max(1, int(round(self._base_height * scale)))
        x = int(round((self.width() - panel_width) / 2))
        y = int(round((self.height() - panel_height) / 2 + (1.0 - self._enter_progress) * 10))
        self.panel.setGeometry(x, y, panel_width, panel_height)
        self.update()

    def _set_height(self, target: float) -> None:
        target = max(float(FIELD_HEIGHT), float(round(target)))
        self._target_height = target
        self._base_height = target
        self._apply_geometry()

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_results(self, groups) -> None:
        self._search_timer.stop()
        self._clear_content()
        self._results = []
        self._rows = []
        self._active_index = -1

        entries_found = any(entries for _, entries in groups)
        if not entries_found:
            self._divider.hide()
            self._scroll.hide()
            self._footer.hide()
            self._set_height(FIELD_HEIGHT)
            self._refresh_glass()
            self.update()
            return

        row_index = 0
        group_count = 0
        for group, entries in groups:
            if not entries:
                continue
            group_count += 1
            self._content_layout.addWidget(
                GroupHeader(GROUP_LABELS[group], self.theme, self._content)
            )
            for entry in entries:
                row = ResultRow(
                    entry,
                    self._icon_for(entry),
                    self._glyph_family,
                    self._accent,
                    self.theme,
                    self._content,
                )
                row.index = row_index
                row.on_hover = self._hover_row
                row.on_click = self._click_row
                self._content_layout.addWidget(row)
                self._rows.append(row)
                self._results.append(entry)
                row_index += 1

        item_count = group_count + row_index
        content_height = (
            12
            + HEADER_HEIGHT * group_count
            + ROW_HEIGHT * row_index
            + 2 * max(0, item_count - 1)
        )
        target = FIELD_HEIGHT + 1 + content_height + FOOTER_HEIGHT
        target = min(target, float(self._max_panel_height()))

        self._divider.show()
        self._scroll.show()
        self._footer.show()
        self._scroll.verticalScrollBar().setValue(0)

        self._set_height(target)
        self._refresh_glass()
        self._set_active(0, scroll=False)
        self.update()

    def _icon_for(self, entry: Entry) -> QPixmap | None:
        if entry.kind in ("setting", "web"):
            return None

        dpr = int(round(self.devicePixelRatioF() * 100))
        key = (entry.target, dpr)
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached

        icon = self._icon_provider.icon(QFileInfo(entry.target))
        if icon.isNull():
            fallback = (
                QFileIconProvider.IconType.Folder
                if entry.kind == "folder"
                else QFileIconProvider.IconType.File
            )
            icon = self._icon_provider.icon(fallback)

        try:
            pixmap = icon.pixmap(QSize(26, 26), dpr / 100.0)
        except TypeError:
            pixmap = icon.pixmap(QSize(26, 26))
        self._icon_cache[key] = pixmap
        return pixmap

    def _hover_row(self, row: ResultRow) -> None:
        if not self.isVisible():
            return
        if 0 <= row.index < len(self._rows):
            self._set_active(row.index, scroll=False)

    def _click_row(self, row: ResultRow) -> None:
        if 0 <= row.index < len(self._rows):
            self._set_active(row.index, scroll=False)
            self._activate(row.index)

    def _set_active(self, index: int, scroll: bool = False) -> None:
        if not self._rows:
            self._active_index = -1
            return
        index %= len(self._rows)
        self._active_index = index
        for position, row in enumerate(self._rows):
            row.set_active(position == index)
        if scroll:
            self._scroll.ensureWidgetVisible(self._rows[index], 0, 12)

    def _move(self, delta: int) -> None:
        if not self._rows:
            return
        self._set_active(self._active_index + delta, scroll=True)

    def _activate(self, index: int) -> None:
        if not self._results:
            return
        if index < 0 or index >= len(self._results):
            index = 0
        entry = self._results[index]
        self.close_spotlight()
        QTimer.singleShot(10, lambda current=entry: open_entry(current))

    def _on_query_changed(self, text: str) -> None:
        if not self.isVisible():
            return
        if not text.strip():
            self._search_timer.stop()
            if self._rows:
                self._render_results([])
            return
        self._search_timer.start()

    def _run_search(self) -> None:
        if not self.isVisible():
            return
        query = self.input.text().strip()
        if not query:
            if self._rows:
                self._render_results([])
            return
        groups = self.index.search(query)
        if not any(entries for _, entries in groups):
            groups = [("web", [web_entry(query)])]
        self._render_results(groups)

    def _on_index_updated(self) -> None:
        if self.isVisible() and self.input.text().strip():
            self._search_timer.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(
            self.rect(), QColor(0, 0, 0, int(round(255 * 0.16 * self._backdrop)))
        )

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_spotlight()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._rows:
                self._activate(self._active_index)
                return
        if key == Qt.Key.Key_Down and self._rows:
            self._move(1)
            return
        if key == Qt.Key.Key_Up and self._rows:
            self._move(-1)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.close_spotlight()
            event.accept()
            return
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close_spotlight()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._rows:
                self._activate(self._active_index)
                return True
            if key == Qt.Key.Key_Down and self._rows:
                self._move(1)
                return True
            if key == Qt.Key.Key_Up and self._rows:
                self._move(-1)
                return True
        return super().eventFilter(obj, event)

    def event(self, event):
        if (
            event.type() == QEvent.Type.WindowDeactivate
            and self.isVisible()
            and (time.monotonic() - self._opened_at) > 1.0
        ):
            self.close_spotlight()
        return super().event(event)

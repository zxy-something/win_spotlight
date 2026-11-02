from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
)


def ui_font(pixel_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Arial"])
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def accent_color() -> QColor:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            value, _ = winreg.QueryValueEx(key, "ColorizationColor")
        color = QColor(value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF)
        if not color.isValid():
            raise ValueError
        if color.lightnessF() < 0.5:
            color = color.lighter(135)
        return color
    except (OSError, ValueError):
        return QColor("#3E82F7")


def is_light_theme() -> bool:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return bool(value)
    except (OSError, ValueError):
        return False


def app_icon() -> QIcon:
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    accent = accent_color()
    gradient = QLinearGradient(16, 16, 240, 240)
    gradient.setColorAt(0.0, accent.lighter(130))
    gradient.setColorAt(1.0, accent.darker(140))
    path = QPainterPath()
    path.addRoundedRect(QRectF(16, 16, 224, 224), 54, 54)
    painter.fillPath(path, gradient)

    pen = QPen(QColor(255, 255, 255, 245), 16)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(76, 70, 96, 96))
    painter.drawLine(QPointF(152, 146), QPointF(196, 192))
    painter.end()

    return QIcon(pixmap)


def blur_image(source: QImage, radius: float, downscale: int = 2) -> QImage:
    if source.isNull():
        return source

    small = source
    if downscale > 1 and source.width() > downscale * 8 and source.height() > downscale * 8:
        small = source.scaled(
            source.width() // downscale,
            source.height() // downscale,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(small))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(max(1.0, radius / max(1, downscale)))
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    scene.setSceneRect(QRectF(0, 0, small.width(), small.height()))

    output = QImage(small.size(), QImage.Format.Format_ARGB32_Premultiplied)
    output.fill(Qt.GlobalColor.transparent)
    painter = QPainter(output)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(
        painter,
        QRectF(0, 0, output.width(), output.height()),
        QRectF(0, 0, small.width(), small.height()),
    )
    painter.end()

    if small is not source:
        output = output.scaled(
            source.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return output


def make_shadow(
    width: int,
    height: int,
    radius: float = 14.0,
    blur: float = 34.0,
    color: QColor | None = None,
    padding: int = 60,
) -> QImage:
    color = QColor(0, 0, 0, 140) if color is None else color
    canvas = QImage(
        max(1, width + padding * 2),
        max(1, height + padding * 2),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawRoundedRect(
        QRectF(padding, padding + 9, width, height), radius, radius
    )
    painter.end()

    return blur_image(canvas, blur, downscale=1)


def force_foreground(hwnd: int) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]

    foreground = user32.GetForegroundWindow()
    if not foreground:
        user32.SetForegroundWindow(hwnd)
        return

    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    attached = False
    if foreground_thread and foreground_thread != current_thread:
        attached = bool(user32.AttachThreadInput(current_thread, foreground_thread, True))
    try:
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(current_thread, foreground_thread, False)

import sys
import traceback

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from hotkey import HotkeyManager
from logger import log
from overlay import SpotlightOverlay
from search import SearchIndex
from visuals import app_icon, ui_font

SERVER_NAME = "Spotlight_Local_Overlay_v1"


def _notify_existing(show: bool = True) -> bool:
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if not socket.waitForConnected(200):
        return False
    if show:
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(200)
    socket.disconnectFromServer()
    return True


def _wire_server(server: QLocalServer, overlay: SpotlightOverlay) -> None:
    def on_connection() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                continue

            def on_ready(conn=connection) -> None:
                data = bytes(conn.readAll())
                if b"show" in data:
                    overlay.show_spotlight()
                conn.disconnectFromServer()

            connection.readyRead.connect(on_ready)
            if connection.bytesAvailable() > 0:
                on_ready(connection)
            connection.disconnected.connect(connection.deleteLater)

    server.newConnection.connect(on_connection)


def _build_tray(app: QApplication, overlay: SpotlightOverlay):
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(app_icon(), app)
    tray.setToolTip("Spotlight")

    menu = QMenu()
    tray._menu = menu
    open_action = menu.addAction("Open Spotlight\tWin + Space")
    open_action.triggered.connect(overlay.show_spotlight)
    menu.addSeparator()
    quit_action = menu.addAction("Quit")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(menu)

    tray.activated.connect(
        lambda reason: overlay.show_spotlight()
        if reason
        in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        )
        else None
    )
    tray.show()
    return tray


def _excepthook(exc_type, exc_value, tb) -> None:
    log("unhandled: " + "".join(traceback.format_exception(exc_type, exc_value, tb)))
    sys.__excepthook__(exc_type, exc_value, tb)


def main() -> int:
    sys.excepthook = _excepthook
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Spotlight")
    app.setApplicationDisplayName("Spotlight")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(ui_font(12))
    app.setWindowIcon(app_icon())

    startup_launch = "--startup" in sys.argv
    if _notify_existing(show=not startup_launch):
        log("second instance forwarded show" if not startup_launch else "second startup instance ignored")
        return 0

    server = QLocalServer()
    QLocalServer.removeServer(SERVER_NAME)
    if not server.listen(SERVER_NAME):
        log(f"single-instance server failed: {server.errorString()}")

    index = SearchIndex()
    overlay = SpotlightOverlay(index)
    _wire_server(server, overlay)

    hotkey = HotkeyManager()
    hotkey.activated.connect(overlay.toggle)
    started = hotkey.start()
    log(f"hotkey started={started} mode={hotkey.mode} error={hotkey.error}")
    index.start()

    tray = _build_tray(app, overlay)
    if tray is not None and not startup_launch:
        if not started:
            QTimer.singleShot(
                700,
                lambda: tray.showMessage(
                    "Spotlight",
                    f"Win + Space is unavailable ({hotkey.error}). Open it from the tray icon.",
                    QSystemTrayIcon.MessageIcon.Warning,
                    7000,
                ),
            )
        else:
            QTimer.singleShot(
                700,
                lambda: tray.showMessage(
                    "Spotlight",
                    "Spotlight is ready. Press Win + Space to search.",
                    app_icon(),
                    4000,
                ),
            )

    if not startup_launch:
        QTimer.singleShot(250, overlay.show_spotlight)

    app.aboutToQuit.connect(hotkey.stop)
    app.aboutToQuit.connect(server.close)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

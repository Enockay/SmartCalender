from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QShowEvent, QPainter, QBrush, QLinearGradient, QColor
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout

from app.ui.widgets.login_widget import LoginWidget
from app.models.auth_response import AuthResponse


class _GradientBackground(QWidget):
    """A widget that paints a blue-to-purple gradient as its background.
    
    QMainWindow itself cannot reliably paint a qlineargradient background via
    QSS on all platforms (macOS in particular ignores it). Using a dedicated
    QWidget that overrides paintEvent is the cross-platform fix.
    """

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        gradient = QLinearGradient(0, 0, self.width(), self.height())
        # Match the blue background used in login.qss for QMainWindow
        gradient.setColorAt(0.0,  QColor("#334155"))  # top-left slate
        gradient.setColorAt(0.35, QColor("#1D4ED8"))  # rich mid blue
        gradient.setColorAt(0.75, QColor("#1E40AF"))  # deeper blue
        gradient.setColorAt(1.0,  QColor("#0F172A"))  # bottom-right dark

        painter.fillRect(self.rect(), QBrush(gradient))
        painter.end()


class LoginWindow(QMainWindow):
    """Login window that shows before the main application."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Smart Calender - Login")
        self.setFixedSize(1000, 750)

        # Use Qt.Window so the window has a normal frame but no extra buttons.
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)

        # ── Background widget ──────────────────────────────────────────────
        # This is the true central widget; it paints the gradient itself so
        # the gradient is guaranteed to appear on every platform.
        self._bg = _GradientBackground(self)
        self._bg.setObjectName("LoginWindowCentral")

        bg_layout = QVBoxLayout(self._bg)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.setSpacing(0)

        # ── Login widget ───────────────────────────────────────────────────
        self._login_widget = LoginWidget(self._bg)
        self._login_widget.loginSuccessful.connect(self._on_login_success)
        self._auth_response: AuthResponse | None = None

        bg_layout.addWidget(self._login_widget)

        self.setCentralWidget(self._bg)

        # Apply QSS *after* all widgets are parented so selectors resolve.
        self._load_qss()

        # Defer positioning until the window has been fully laid out.
        QTimer.singleShot(0, self._move_to_top_right)

    # ── Stylesheet ─────────────────────────────────────────────────────────

    def _load_qss(self) -> None:
        """Load login.qss and apply it to both the window and the login widget."""
        # login_window.py is at app/ui/windows/login_window.py
        # Go up 3 levels: windows -> ui -> app -> root
        # parents[0] = app/ui/windows, parents[1] = app/ui, parents[2] = app, parents[3] = root
        root = Path(__file__).resolve().parents[2]  # Gets to app/
        qss_path = root / "ui" / "resources" / "qss" / "login.qss"
        if not qss_path.exists():
            from app.core.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"QSS file not found: {qss_path}")
            return

        style = qss_path.read_text(encoding="utf-8")

        # Apply to the window so QMainWindow-scoped selectors work.
        self.setStyleSheet(style)

        # Also apply directly to LoginWidget so its child selectors resolve
        # even when the widget's own style scope shadows the parent's sheet.
        self._login_widget.setStyleSheet(style)
        
        # Force style refresh
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.style().unpolish(self)
            app.style().polish(self)
            app.style().unpolish(self._login_widget)
            app.style().polish(self._login_widget)
            self.update()
            self._login_widget.update()

    # ── Positioning ────────────────────────────────────────────────────────

    def _move_to_top_right(self) -> None:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        self.move(available.right() - frame.width(), available.top())

    # ── Signals ────────────────────────────────────────────────────────────

    def _on_login_success(self, auth_response: AuthResponse) -> None:
        self._auth_response = auth_response
        self.close()

    def get_auth_response(self) -> AuthResponse | None:
        return self._auth_response

    # ── Event overrides ────────────────────────────────────────────────────

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        # Re-apply the sheet once the window is actually visible in case the
        # platform deferred style resolution until show time.
        QTimer.singleShot(100, self._load_qss)
        QTimer.singleShot(200, self._force_style_refresh)
    
    def _force_style_refresh(self) -> None:
        """Force a complete style refresh of all widgets."""
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if not app:
            return
        
        # Refresh all widgets in the window
        def refresh_widget(widget):
            app.style().unpolish(widget)
            app.style().polish(widget)
            widget.update()
            for child in widget.findChildren(QWidget):
                refresh_widget(child)
        
        refresh_widget(self)

    def closeEvent(self, event) -> None:  # noqa: N802
        super().closeEvent(event)

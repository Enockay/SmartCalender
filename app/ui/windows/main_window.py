from __future__ import annotations

from datetime import date, datetime, time, timedelta
from calendar import monthrange
from pathlib import Path

from PySide6.QtCore import Qt, QDate, QSize, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QDesktopServices, QPixmap, QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QPushButton,
    QSizePolicy,
    QMessageBox,
    QDialog,
    QFrame,
    QLineEdit,
)

from app.controllers.meeting_controller import MeetingController
from app.controllers.calendar_controller import CalendarController
from app.controllers.task_controller import TaskController
from app.services.meeting_service import MeetingService
from app.services.calendar_service import CalendarService
from app.services.task_service import TaskService
from app.services.auth_service import AuthService
from app.services.device_service import DeviceService
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtNetwork import QAbstractSocket
from app.core.logger import get_logger
from app.ui.widgets.dashboard_widget import DashboardWidget
from app.ui.widgets.day_view_widget import DayViewWidget
from app.ui.widgets.week_view_widget import WeekViewWidget
from app.ui.widgets.month_view_widget import MonthViewWidget
from app.ui.widgets.year_view_widget import YearViewWidget
from app.ui.widgets.mini_calendar_widget import MiniCalendarWidget
from app.ui.widgets.task_board_widget import TaskBoardWidget
from app.ui.widgets.reminder_widget import ReminderDashboardWidget
from app.services.settings_service import SettingsService
from app.ui.windows.settings_window import SettingsWindow
from app.ui.dialogs.meeting_details_dialog import MeetingDetailsDialog
from app.ui.dialogs.meeting_dialog import MeetingDialog
from app.ui.dialogs.create_task_dialog import CreateTaskDialog
from app.ui.widgets.todo_list_widget import TodoEvent
from app.database.db_manager import DatabaseManager
from app.database.schema import User
from app.core.app_config import get_base_dir
from sqlalchemy import select


class MainWindow(QMainWindow):
    """Main application window with a Monthboard-style layout."""
    
    # Cross-thread safe UI refresh trigger (e.g. from websocket background worker)
    subscriptionUiRefreshRequested = Signal()

    def __init__(self, settings: SettingsService | None = None) -> None:
        super().__init__()
        self._logger = get_logger(__name__)
        self.subscriptionUiRefreshRequested.connect(self._refresh_subscription_ui)
        self.setWindowTitle("SmartCalender")
        # Avoid clipping/pushed sidebar content on Windows high-DPI displays.
        # Use a comfortable default size but allow resizing.
        self.resize(1100, 780)
        self.setMinimumSize(1000, 750)
        self._apply_window_controls()

        self._settings = settings or SettingsService()
        self._current_date = date.today()
        self._db = DatabaseManager()
        
        # Cached logged-in user info for sidebar / title
        self._current_user = None
        self._auth_service = AuthService(settings_service=self._settings)
        self._device_service = DeviceService(self._db)
        self._ws: QWebSocket | None = None
        self._ws_reconnect_timer: QTimer | None = None
        self._ws_reconnect_backoff_ms: int = 1000

        self._meeting_service = MeetingService(settings_service=self._settings)
        self._calendar_service = CalendarService(self._meeting_service)
        self._task_service = TaskService()
        self._meeting_controller = MeetingController(self, self._meeting_service)
        self._calendar_controller = CalendarController(self._calendar_service)
        self._task_controller = TaskController(self, self._task_service)

        self._calendar_controller.on_day_meetings_changed = self._on_day_meetings_changed
        self._meeting_controller.on_meetings_changed = self._on_meetings_changed

        self._init_central_layout()
        self._apply_default_view()
        self._reload_current_day()
        self._sync_title()

        # After the window is up, enforce subscription status. This dialog
        # is modal and cannot be bypassed from within the app.
        QTimer.singleShot(200, self._check_subscription_status)
        # Do NOT connect the subscription websocket at startup.
        # We only open it when subscription is overdue (paywall) or when the user
        # explicitly clicks Renew/Upgrade.

        # Periodically re-check subscription status while the app is open,
        # so mid-session expiries are also enforced.
        self._subscription_timer = QTimer(self)
        self._subscription_timer.timeout.connect(self._refresh_subscription_and_check)
        self._subscription_timer.start(15 * 60 * 1000)  # every 15 minutes

    def _apply_window_controls(self) -> None:
        """Force close/minimize only and block fullscreen/maximize hints."""
        self.setWindowFlags(
            Qt.Window
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMinimizeButtonHint
        )
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        # Always remove the macOS green-button fullscreen capability (no hasattr guard
        # needed – PySide6 exposes this flag on all supported versions).
        self.setWindowFlag(Qt.WindowFullscreenButtonHint, False)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # NOTE: Do NOT call _apply_window_controls() here.
        # Calling setWindowFlags() on a visible window forces macOS to
        # recreate the native window handle, which wipes out all painted
        # content and produces a blank/dark screen. Window flags are already
        # set correctly in __init__, so this call is both redundant and harmful.
        # Keep position reliable without delayed visible jump.
        self._move_to_top_right()
        if self.windowState() & Qt.WindowFullScreen:
            self.setWindowState(self.windowState() & ~Qt.WindowFullScreen)

    def changeEvent(self, event) -> None:  # noqa: N802
        """Hard-block fullscreen on all platforms (macOS/Windows/Linux)."""
        super().changeEvent(event)
        if self.windowState() & Qt.WindowFullScreen:
            # Defer the revert by one event-loop tick so that macOS can finish
            # its native fullscreen transition before we cancel it.  Reverting
            # synchronously here causes the macOS "not in fullscreen state"
            # console warning.
            QTimer.singleShot(0, self._exit_fullscreen)

    def _exit_fullscreen(self) -> None:
        """Revert to normal window state, cancelling any fullscreen transition."""
        if self.windowState() & Qt.WindowFullScreen:
            self.setWindowState(self.windowState() & ~Qt.WindowFullScreen)

    def _refresh_subscription_and_check(self) -> None:
        """Refresh the current user from DB and re-run subscription check."""
        from app.database.schema import User
        from sqlalchemy import select

        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User)
                    .where(User.is_logged_in == True)
                    .order_by(User.last_login_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                self._current_user = user
        except Exception:
            # If refresh fails, keep whatever we had before.
            pass

        # Also sync subscription from server (best-effort) before enforcing.
        self._sync_subscription_from_server(best_effort=True)
        self._check_subscription_status()

    # --- Realtime subscription socket (no polling) --------------------------

    def _ensure_subscription_socket(self) -> None:
        """Ensure websocket is connected for payment/subscription events."""
        # Only connect if we have a logged-in user + token
        try:
            if not self._current_user or not getattr(self._current_user, "access_token", None):
                # Try refresh from DB in case current user wasn't loaded yet
                self._refresh_subscription_and_check()
            if not self._current_user or not getattr(self._current_user, "access_token", None):
                return
        except Exception:
            return

        if self._ws is None:
            self._ws = QWebSocket()
            self._ws.textMessageReceived.connect(self._on_ws_message)
            self._ws.connected.connect(self._on_ws_connected)
            self._ws.disconnected.connect(self._on_ws_disconnected)

        if self._ws.state() == QAbstractSocket.ConnectedState:
            return

        token = self._current_user.access_token
        device_id = self._device_service.get_or_create_device_id()
        # Backend should accept token for websocket auth. Query-param auth works cross-platform.
        ws_url = QUrl(f"wss://api.deskhab.com/v1/ws?token={token}&device_id={device_id}")
        # Log without leaking token (QUrl.toString only supports ComponentFormattingOption here)
        self._logger.info("Opening subscription socket: wss://api.deskhab.com/v1/ws?token=***")
        self._ws.open(ws_url)

    def _on_ws_connected(self) -> None:
        # Reset reconnect backoff on success
        self._ws_reconnect_backoff_ms = 1000
        # Optionally subscribe to user channel if backend requires it
        try:
            if not self._current_user:
                return
            user_id = self._current_user.api_user_id or str(self._current_user.id)
            msg = (
                '{"type":"subscribe","topic":"user","user_id":"'
                + str(user_id)
                + '"}'
            )
            self._logger.info(f"Subscription socket connected; subscribing to user_id={user_id}")
            self._ws.sendTextMessage(msg)
        except Exception:
            pass

    def _on_ws_disconnected(self) -> None:
        """Reconnect with exponential backoff."""
        self._logger.warning(
            f"Subscription socket disconnected. Reconnecting in {self._ws_reconnect_backoff_ms}ms"
        )
        if self._ws_reconnect_timer is None:
            self._ws_reconnect_timer = QTimer(self)
            self._ws_reconnect_timer.setSingleShot(True)
            self._ws_reconnect_timer.timeout.connect(self._ensure_subscription_socket)

        self._ws_reconnect_timer.start(self._ws_reconnect_backoff_ms)
        self._ws_reconnect_backoff_ms = min(self._ws_reconnect_backoff_ms * 2, 30000)

    def _on_ws_message(self, message: str) -> None:
        """Handle subscription/payment events from server."""
        import json as _json
        try:
            payload = _json.loads(message)
        except Exception:
            return

        if not isinstance(payload, dict):
            return

        name = str(payload.get("name") or payload.get("event") or payload.get("type") or "").lower()
        # Accept a few likely event names from backend
        interesting = {
            "subscription.updated",
            "payment.completed",
            "payment.succeeded",
            "subscription.active",
        }

        if name in interesting or payload.get("subscription_status") or payload.get("subscription"):
            # Log current visible state before syncing
            before_status = getattr(self._current_user, "subscription_status", None) if self._current_user else None
            before_exp = getattr(self._current_user, "subscription_expires_at", None) if self._current_user else None
            self._logger.info(
                "Subscription socket event received: "
                f"{payload.get('name') or payload.get('event') or payload.get('type')} "
                f"(before: status={before_status}, expires_at={before_exp})"
            )
            # Refresh subscription from server and re-check gate.
            # Run in background to avoid blocking UI thread.
            import threading

            def worker():
                updated = self._sync_subscription_from_server(best_effort=True)
                after_status = getattr(self._current_user, "subscription_status", None) if self._current_user else None
                after_exp = getattr(self._current_user, "subscription_expires_at", None) if self._current_user else None
                self._logger.info(
                    f"Subscription sync completed (updated={updated}) "
                    f"(after: status={after_status}, expires_at={after_exp})"
                )
                # Schedule UI refresh on the main thread safely
                self.subscriptionUiRefreshRequested.emit()

            threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def _refresh_subscription_ui(self) -> None:
        """Refresh UI that displays subscription/user data (sidebar + settings)."""
        # Re-check paywall gate first/also
        self._check_subscription_status()

        # Sidebar expiry label
        try:
            if getattr(self, "_sub_expiry_label", None) is not None and self._current_user:
                exp = self._current_user.subscription_expires_at
                if exp:
                    exp_str = exp.strftime("%b %d, %Y")
                    self._sub_expiry_label.setText(f"Subscription: Ends {exp_str}")
                    self._logger.info(f"UI refreshed: sidebar subscription expiry set to {exp_str}")

                    days_left = (exp.date() - date.today()).days
                    if days_left <= 0:
                        state = "expired"
                    elif days_left <= 15:
                        state = "near"
                    else:
                        state = "ok"
                    self._sub_expiry_label.setProperty("state", state)
                    self._sub_expiry_label.style().unpolish(self._sub_expiry_label)
                    self._sub_expiry_label.style().polish(self._sub_expiry_label)
                else:
                    self._sub_expiry_label.setText("")
        except Exception:
            pass

        # Settings → Account view (if constructed)
        try:
            if getattr(self, "_settings_view", None) is not None:
                self._settings_view.refresh_account()
                self._logger.info("UI refreshed: Settings → Account reloaded from DB")
        except Exception:
            pass

    def _sync_subscription_from_server(self, best_effort: bool = False) -> bool:
        """Sync subscription fields from remote server into local DB.

        Returns True if an update was applied, False otherwise.
        """
        from sqlalchemy import select
        from app.database.schema import User

        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User)
                    .where(User.is_logged_in == True)
                    .order_by(User.last_login_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if not user or not user.access_token:
                    return False

                payload = self._auth_service.fetch_subscription_status(user.access_token)
                auth_like = self._auth_service._parse_response(payload)  # reuse parsing rules

                user.subscription_tier = auth_like.subscription_tier
                user.subscription_status = auth_like.subscription_status
                user.subscription_expires_at = auth_like.subscription_expires_at
                import json as _json
                user.subscription_features = _json.dumps(auth_like.subscription_features or [])
                user.token_expires_at = auth_like.token_expires_at or user.token_expires_at
                session.commit()

                self._current_user = user
                return True
        except Exception as exc:
            if not best_effort:
                raise
            # best-effort: ignore transient network errors
            return False

    # --- Subscription / licensing -------------------------------------------

    def _open_subscription_renewal_url(self) -> None:
        """Open browser to the hosted renewal flow for the current user."""
        from app.database.schema import User
        from sqlalchemy import select

        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User)
                    .where(User.is_logged_in == True)
                    .order_by(User.last_login_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if not user:
                    return
                user_id = user.api_user_id or str(user.id)
                token = user.access_token
                if not token:
                    return
        except Exception:
            return

        url = QUrl(f"https://www.deskhab.com/renew-smartcalender/{user_id}")
        url.setQuery(f"token={token}")
        QDesktopServices.openUrl(url)
        # Ensure realtime socket is connected so payment completion unlocks immediately.
        QTimer.singleShot(0, self._ensure_subscription_socket)

    def _check_subscription_status(self) -> None:
        """If the subscription is expired, block usage until user upgrades."""
        if not self._current_user:
            return

        sub_status = (self._current_user.subscription_status or "").lower()
        expires_at = self._current_user.subscription_expires_at

        expired = False
        if sub_status in {"expired", "cancelled"}:
            expired = True
        elif expires_at:
            today = datetime.utcnow().date()
            expired = expires_at.date() < today

        if not expired:
            return

        # Subscription is overdue: open websocket so payment events can unlock immediately.
        QTimer.singleShot(0, self._ensure_subscription_socket)

        # Build a blocking dialog similar to the reference screenshot.
        dlg = QDialog(self)
        dlg.setModal(True)
        dlg.setWindowFlag(Qt.FramelessWindowHint, True)
        dlg.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame(dlg)
        card.setObjectName("InlineInfoCard")
        card.setMinimumWidth(460)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        icon = QLabel("⚠️", card)
        icon.setAlignment(Qt.AlignHCenter)
        layout.addWidget(icon)

        title = QLabel("Payment Required", card)
        title.setObjectName("InlineInfoTitle")
        title.setAlignment(Qt.AlignHCenter)
        layout.addWidget(title)

        body = QLabel(
            "Your subscription has expired. To continue using Smart Calender,\n"
            "please renew your subscription.",
            card,
        )
        body.setObjectName("InlineInfoBody")
        body.setAlignment(Qt.AlignHCenter)
        body.setWordWrap(True)
        layout.addWidget(body)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        upgrade_btn = QPushButton("Upgrade Plan", card)
        upgrade_btn.setObjectName("InlineInfoPrimaryButton")
        upgrade_btn.setCursor(Qt.PointingHandCursor)
        upgrade_btn.clicked.connect(self._open_subscription_renewal_url)
        upgrade_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(upgrade_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        outer.addWidget(card)

        # Center over main window
        dlg.adjustSize()
        parent_geo = self.frameGeometry()
        dlg_geo = dlg.frameGeometry()
        dlg.move(
            parent_geo.center().x() - dlg_geo.width() // 2,
            parent_geo.center().y() - dlg_geo.height() // 2,
        )
        dlg.exec()

    def _move_to_top_right(self) -> None:
        """Position the main window in the top-right corner of the current screen."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        if not screen:
            return

        available = screen.availableGeometry()
        frame = self.frameGeometry()

        x = available.right() - frame.width()
        y = available.top()
        self.move(x, y)

    # --- Inline notice helpers ----------------------------------------------

    def _show_inline_notice(self, title: str, message: str, detail: str | None = None) -> None:
        """Show a small, styled in-app notice centered over the main window."""
        from PySide6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setObjectName("InlineInfoDialog")
        dlg.setModal(True)
        dlg.setWindowFlag(Qt.FramelessWindowHint, True)
        dlg.setAttribute(Qt.WA_TranslucentBackground, True)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame(dlg)
        card.setObjectName("InlineInfoCard")
        card.setMinimumWidth(420)

        # Layout mimics the earlier system alert: icon on the left,
        # stacked text on the right, actions row below.
        main_row = QHBoxLayout(card)
        main_row.setContentsMargins(20, 16, 20, 16)
        main_row.setSpacing(14)

        icon_label = QLabel("⚠️", card)
        icon_label.setObjectName("InlineInfoIcon")
        main_row.addWidget(icon_label, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        title_label = QLabel(title, card)
        title_label.setObjectName("InlineInfoTitle")
        title_label.setWordWrap(True)
        text_col.addWidget(title_label)

        body_label = QLabel(message, card)
        body_label.setObjectName("InlineInfoBody")
        body_label.setWordWrap(True)
        text_col.addWidget(body_label)

        if detail:
            detail_label = QLabel(detail, card)
            detail_label.setObjectName("InlineInfoDetail")
            detail_label.setWordWrap(True)
            text_col.addWidget(detail_label)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        ok_button = QPushButton("OK", card)
        ok_button.setObjectName("InlineInfoPrimaryButton")
        ok_button.clicked.connect(dlg.accept)
        button_row.addWidget(ok_button)
        text_col.addLayout(button_row)

        main_row.addLayout(text_col, 1)
        outer.addWidget(card)

        dlg.adjustSize()
        # Center over the main window
        parent_geo = self.frameGeometry()
        dlg_geo = dlg.frameGeometry()
        dlg.move(
            parent_geo.center().x() - dlg_geo.width() // 2,
            parent_geo.center().y() - dlg_geo.height() // 2,
        )
        dlg.exec()

    def _init_central_layout(self) -> None:
        central = QWidget(self)
        # Required on macOS: without WA_StyledBackground the central widget is
        # fully transparent and none of its children paint their backgrounds.
        central.setAttribute(Qt.WA_StyledBackground, True)

        # Root layout: header bar on top, then body row (sidebar + main content)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Top header bar spanning full width ---
        header_bar = QWidget(central)
        header_bar.setObjectName("HeaderBar")
        # Required on macOS for QSS gradient backgrounds on child QWidgets.
        header_bar.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(12)

        # App logo / title on the left
        logo_label = QLabel(header_bar)
        logo_label.setObjectName("AppLogo")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedSize(44, 44)

        # Use bundled logo image (never rely on emoji so branding stays consistent
        # in the packaged app).
        logo_path = get_base_dir() / "assets" / "logo.svg"
        renderer = QSvgRenderer(str(logo_path))
        if renderer.isValid():
            pixmap = QPixmap(44, 44)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)  # render SVG into the painter's surface
            painter.end()
            logo_label.setPixmap(
                pixmap.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            # Fallback for development or missing file
            logo_label.setText("📆")

        header_layout.addWidget(logo_label)

        self._header_title = QLabel("Smart Calender", header_bar)
        self._header_title.setObjectName("AppTitle")
        header_layout.addWidget(self._header_title)

        header_layout.addStretch(1)

        # Add Task button (shown when Tasks Board is active)
        self._add_task_button = QPushButton("+ Add Task", header_bar)
        self._add_task_button.setObjectName("AddTaskButton")
        self._add_task_button.clicked.connect(self._on_add_task_clicked)
        self._add_task_button.setVisible(False)
        header_layout.addWidget(self._add_task_button)

        # Day / Week / Month buttons in the header
        self._day_button = QPushButton("Day", header_bar)
        self._day_button.setCheckable(True)
        self._day_button.setObjectName("SegmentButton")
        self._day_button.clicked.connect(lambda: self._set_view(1))

        self._week_button = QPushButton("Week", header_bar)
        self._week_button.setCheckable(True)
        self._week_button.setObjectName("SegmentButton")
        self._week_button.clicked.connect(lambda: self._set_view(2))

        self._month_button = QPushButton("Month", header_bar)
        self._month_button.setCheckable(True)
        self._month_button.setObjectName("SegmentButton")
        self._month_button.clicked.connect(lambda: self._set_view(3))

        self._year_button = QPushButton("Year", header_bar)
        self._year_button.setCheckable(True)
        self._year_button.setObjectName("SegmentButton")
        self._year_button.clicked.connect(lambda: self._set_view(4))

        self._day_button.setChecked(True)

        header_layout.addWidget(self._day_button)
        header_layout.addWidget(self._week_button)
        header_layout.addWidget(self._month_button)
        header_layout.addWidget(self._year_button)

        # Small search bar on the far right
        search_container = QWidget(header_bar)
        search_container.setObjectName("SearchContainer")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(8, 4, 8, 4)
        search_layout.setSpacing(6)

        search_icon = QLabel("🔍", search_container)
        search_icon.setObjectName("SearchIcon")
        search_layout.addWidget(search_icon)

        self._search_input = QLineEdit(search_container)
        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText("Search...")
        self._search_input.setFixedWidth(180)
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.returnPressed.connect(self._on_search_executed)
        search_layout.addWidget(self._search_input)

        header_layout.addWidget(search_container)

        root_layout.addWidget(header_bar)

        # --- Body row: sidebar + main content ---
        body_container = QWidget(central)
        body_container.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QHBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._build_sidebar(body_container, body_layout)
        self._build_main_content(body_container, body_layout)

        root_layout.addWidget(body_container, stretch=1)

        self.setCentralWidget(central)

        # Load global/main stylesheet last
        self._load_main_qss()

    def _build_sidebar(self, parent: QWidget, root_layout: QHBoxLayout) -> None:
        """Create the left navigation sidebar."""
        import getpass, os

        sidebar_container = QWidget(parent)
        sidebar_container.setObjectName("LeftSidebar")
        sidebar_container.setFixedWidth(250)

        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # ── Navigation list ──
        self._nav_list = QListWidget(sidebar_container)
        self._nav_list.setObjectName("NavList")
        self._nav_list.setSpacing(0)
        self._nav_list.setIconSize(QSize(20, 20))
        self._nav_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Keep sidebar navigation fixed: ignore mouse-wheel scrolling on this list.
        self._nav_list.viewport().installEventFilter(self)

        for label in [
            "  🏠  Dashboard",
            "  📅  Todo List",
            "  📋  Tasks Board",
            "  ⏰  Reminders",
            "  ⚙️  Settings",
        ]:
            item = QListWidgetItem(label, self._nav_list)
            item.setSizeHint(QSize(0, 48))

        # Use dynamic height based on size hint instead of a strict per-row
        # formula. On Windows (especially with DPI scaling and emoji fonts),
        # fixed 48px rows + QSS padding can clip the first item ("Dashboard").
        # Keep a little extra room for top/bottom padding from sidebar.qss.
        self._nav_list.setFixedHeight(self._nav_list.sizeHintForRow(0) * self._nav_list.count() + 14)

        self._nav_list.setCurrentRow(0)
        self._nav_list.scrollToTop()
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self._nav_list)

        # Keep the mini calendar closer to the navigation list; push the user
        # card down instead (added below).
        # Nudge the mini calendar slightly downward to visually center it
        # between the nav list and the user card.
        sidebar_layout.addSpacing(14)

        # ── Mini calendar ──
        self._mini_calendar_widget = MiniCalendarWidget(sidebar_container)
        self._mini_calendar_widget.setObjectName("MiniCalendarRoot")
        self._mini_calendar_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._mini_calendar = self._mini_calendar_widget.calendar
        self._mini_calendar.selectionChanged.connect(self._on_sidebar_date_changed)
        sidebar_layout.addWidget(self._mini_calendar_widget, alignment=Qt.AlignHCenter)
        # Flexible space below the mini calendar so the user card stays at
        # the bottom of the sidebar.
        sidebar_layout.addStretch(1)

        # ── User card at the bottom ──
        # Get the actual system username
        # Prefer the last logged-in app user from the database
        display_name = "User"
        email = ""
        sub_expiry_str = ""
        days_left = None
        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User)
                    .where(User.is_logged_in == True)
                    .order_by(User.last_login_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if user:
                    self._current_user = user
                    display_name = user.name or "User"
                    email = user.email or ""
                    if user.subscription_expires_at:
                        sub_expiry = user.subscription_expires_at.date()
                        today = date.today()
                        days_left = (sub_expiry - today).days
                        sub_expiry_str = sub_expiry.strftime("%b %d, %Y")
        except Exception:
            pass
        
        if not display_name:
            try:
                sys_user = getpass.getuser()
            except Exception:
                sys_user = os.environ.get("USER", os.environ.get("USERNAME", "User"))
            display_name = sys_user.replace("_", " ").replace("-", " ").title()
        
        initial = display_name[0].upper() if display_name else "U"

        user_card = QFrame(sidebar_container)
        user_card.setObjectName("SidebarUserCard")

        card_lay = QHBoxLayout(user_card)
        card_lay.setContentsMargins(14, 10, 14, 10)
        card_lay.setSpacing(10)

        # Avatar circle
        avatar = QLabel(initial, user_card)
        avatar.setObjectName("SidebarAvatar")
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignCenter)
        card_lay.addWidget(avatar)

        # Name + status column
        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        info_col.setContentsMargins(0, 0, 0, 0)

        self._user_id_label = QLabel(display_name, user_card)
        self._user_id_label.setObjectName("SidebarUserName")
        
        self._status_label = QLabel("● Online", user_card)
        self._status_label.setObjectName("SidebarUserStatus")
        
        if sub_expiry_str:
            sub_text = f"Subscription: Ends {sub_expiry_str}"
        else:
            sub_text = ""
        self._sub_expiry_label = QLabel(sub_text, user_card)
        self._sub_expiry_label.setObjectName("SidebarUserSubExpiry")
        # Set state for QSS color: ok / near / expired
        if days_left is not None:
            if days_left <= 0:
                state = "expired"
            elif days_left <= 15:
                state = "near"
            else:
                state = "ok"
            self._sub_expiry_label.setProperty("state", state)
        
        info_col.addWidget(self._user_id_label)
        info_col.addWidget(self._status_label)
        info_col.addWidget(self._sub_expiry_label)
        card_lay.addLayout(info_col, 1)

        sidebar_layout.addWidget(user_card)

        root_layout.addWidget(sidebar_container)

        # Load sidebar-only stylesheet first
        self._load_sidebar_qss(sidebar_container)

    def eventFilter(self, watched, event):  # type: ignore[override]
        """Block wheel scrolling on sidebar nav list to avoid visual stretch/shift."""
        if hasattr(self, "_nav_list") and watched is self._nav_list.viewport():
            if event.type() == event.Type.Wheel:
                event.ignore()
                return True
        return super().eventFilter(watched, event)

    def _build_main_content(self, parent: QWidget, root_layout: QHBoxLayout) -> None:
        """Create the header and central stacked views."""
        main_container = QWidget(parent)
        main_container.setObjectName("MainContent")

        main_layout = QVBoxLayout(main_container)
        # Remove outer padding so content touches the main area edges.
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Stacked views where the main content is rendered
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._stack = QStackedWidget(main_container)

        self._dashboard = DashboardWidget(main_container)
        self._day_view = DayViewWidget(main_container)
        self._week_view = WeekViewWidget(main_container)
        self._month_view = MonthViewWidget(main_container)
        self._year_view = YearViewWidget(main_container)
        self._task_board = TaskBoardWidget(main_container)

        self._settings_view = SettingsWindow(self._settings, main_container)
        self._settings_view.renewSubscriptionRequested.connect(
            lambda: QTimer.singleShot(0, self._ensure_subscription_socket)
        )
        self._reminder_view = ReminderDashboardWidget(main_container)

        self._stack.addWidget(self._dashboard)      # index 0
        self._stack.addWidget(self._day_view)       # index 1
        self._stack.addWidget(self._week_view)      # index 2
        self._stack.addWidget(self._month_view)     # index 3
        self._stack.addWidget(self._year_view)      # index 4
        self._stack.addWidget(self._task_board)     # index 5
        self._stack.addWidget(self._settings_view)  # index 6
        self._stack.addWidget(self._reminder_view)  # index 7
        self._stack.setCurrentIndex(0)

        content_layout.addWidget(self._stack, stretch=1)
        main_layout.addLayout(content_layout)

        # Connect todo table interactions (double-click) from all views
        self._day_view.todo_table.eventClicked.connect(
            lambda t, text: self._on_time_slot_activated("day", t, text)
        )
        # Week view emits a MeetingModel to edit
        self._week_view.meetingActivated.connect(self._open_meeting_for_edit)
        # Week view single-click on a day navigates to that day in Day view
        self._week_view.daySelected.connect(self._on_week_day_selected)
        # Week view also emits an exact time slot when a cell is clicked
        self._week_view.timeSlotSelected.connect(self._on_week_slot_selected)
        # Month view day click should jump to the corresponding week/day
        self._month_view.daySelected.connect(self._on_month_day_selected)
        # Year view emits a month selection (first day of month)
        self._year_view.monthSelected.connect(self._on_year_month_selected)
        # Month/year views fetch directly from DB based on current date

        # Connect task board interactions
        self._task_controller.on_tasks_changed = self._reload_tasks
        self._task_board.taskClicked.connect(self._on_task_clicked)
        self._task_board.taskDeleted.connect(self._on_task_deleted)
        self._task_board.taskStatusChanged.connect(self._on_task_status_changed)
        self._reload_tasks()

        # Connect dashboard navigation signals
        self._dashboard.navigateToTaskBoard.connect(self._on_dashboard_view_tasks)
        self._dashboard.navigateToTask.connect(self._on_dashboard_open_task)
        self._dashboard.navigateToTodoList.connect(self._on_dashboard_view_events)
        self._dashboard.navigateToEventDay.connect(self._on_dashboard_open_event)
        self._dashboard.navigateToReminders.connect(self._on_dashboard_view_reminders)
        self._dashboard.navigateToOverdue.connect(self._on_dashboard_view_overdue)

        root_layout.addWidget(main_container, stretch=1)

    def _load_sidebar_qss(self, sidebar: QWidget) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "sidebar.qss"
        if qss_path.exists():
            style = qss_path.read_text(encoding="utf-8")
            sidebar.setStyleSheet(style)

    def _load_main_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "main_window.qss"
        if qss_path.exists():
            style = qss_path.read_text(encoding="utf-8")
            self.setStyleSheet(style)

    # --- Navigation logic ------------------------------------------------

    def _sync_title(self) -> None:
        text = self._current_date.strftime("%A, %B %d, %Y")
        self.setWindowTitle(f"SmartCalender – {text}")
        if hasattr(self, "_header_date_label"):
            self._header_date_label.setText(text)

    def _go_today(self) -> None:
        self._current_date = date.today()
        self._mini_calendar.setSelectedDate(QDate.currentDate())
        self._sync_title()
        self._reload_current_day()

    def _go_previous(self) -> None:
        current = self._stack.currentIndex()
        if current == 1:    # Day view
            delta = -1
        elif current == 2:  # Week view
            delta = -7
        elif current == 3:  # Month view
            delta = -30
        elif current == 4:  # Year view
            delta = -365
        else:
            delta = -1

        self._current_date = date.fromordinal(self._current_date.toordinal() + delta)
        self._mini_calendar.setSelectedDate(
            QDate(self._current_date.year, self._current_date.month, self._current_date.day)
        )
        self._sync_title()
        self._reload_current_day()
        # Also refresh the active week/month/year view
        if current == 2 and hasattr(self, "_week_view"):
            self._week_view.set_date(self._current_date)
        elif current == 3 and hasattr(self, "_month_view"):
            self._month_view.set_date(self._current_date)
        elif current == 4 and hasattr(self, "_year_view"):
            self._year_view.set_date(self._current_date)

    def _go_next(self) -> None:
        current = self._stack.currentIndex()
        if current == 1:    # Day view
            delta = 1
        elif current == 2:  # Week view
            delta = 7
        elif current == 3:  # Month view
            delta = 30
        elif current == 4:  # Year view
            delta = 365
        else:
            delta = 1

        self._current_date = date.fromordinal(self._current_date.toordinal() + delta)
        self._mini_calendar.setSelectedDate(
            QDate(self._current_date.year, self._current_date.month, self._current_date.day)
        )
        self._sync_title()
        self._reload_current_day()
        # Also refresh the active week/month/year view
        if current == 2 and hasattr(self, "_week_view"):
            self._week_view.set_date(self._current_date)
        elif current == 3 and hasattr(self, "_month_view"):
            self._month_view.set_date(self._current_date)
        elif current == 4 and hasattr(self, "_year_view"):
            self._year_view.set_date(self._current_date)

    def _set_view(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if hasattr(self, "_day_button"):
            self._day_button.setChecked(index == 1)
        if hasattr(self, "_week_button"):
            self._week_button.setChecked(index == 2)
        if hasattr(self, "_month_button"):
            self._month_button.setChecked(index == 3)
        if hasattr(self, "_year_button"):
            self._year_button.setChecked(index == 4)
        
        # Show/hide buttons based on view
        is_task_board = index == 5
        is_dashboard = index == 0
        is_settings = index == 6
        is_reminders = index == 7
        show_calendar_btns = not is_task_board and not is_dashboard and not is_settings and not is_reminders
        if hasattr(self, "_add_task_button"):
            self._add_task_button.setVisible(is_task_board)
        if hasattr(self, "_day_button"):
            self._day_button.setVisible(show_calendar_btns)
        if hasattr(self, "_week_button"):
            self._week_button.setVisible(show_calendar_btns)
        if hasattr(self, "_month_button"):
            self._month_button.setVisible(show_calendar_btns)
        if hasattr(self, "_year_button"):
            self._year_button.setVisible(show_calendar_btns)
        
        # Refresh the view being switched to with the current date
        if is_dashboard and hasattr(self, "_dashboard"):
            self._dashboard.refresh()
        elif index == 1 and hasattr(self, "_day_view"):
            self._reload_current_day()
        elif index == 2 and hasattr(self, "_week_view"):
            self._week_view.set_date(self._current_date)
        elif index == 3 and hasattr(self, "_month_view"):
            self._month_view.set_date(self._current_date)
        elif index == 4 and hasattr(self, "_year_view"):
            self._year_view.set_date(self._current_date)
        elif index == 5 and hasattr(self, "_task_board"):
            self._task_board.set_date(self._current_date)
        
        self._sync_title()

    def _apply_default_view(self) -> None:
        # Default to dashboard view
        self._set_view(0)

    def _on_sidebar_date_changed(self) -> None:
        qdate = self._mini_calendar.selectedDate()
        self._current_date = date(qdate.year(), qdate.month(), qdate.day())
        self._sync_title()
        self._reload_current_day()
        # Refresh week/month/year widgets from DB based on new date
        if hasattr(self, "_week_view"):
            self._week_view.set_date(self._current_date)
        if hasattr(self, "_month_view"):
            self._month_view.set_date(self._current_date)
        if hasattr(self, "_year_view"):
            self._year_view.set_date(self._current_date)
        if hasattr(self, "_task_board"):
            self._task_board.set_date(self._current_date)

        # If date is clicked from dashboard, jump into Day view.
        # Keep Task Board users on Task Board.
        current_idx = self._stack.currentIndex()
        if current_idx == 0:
            self._set_view(1)

    def _on_nav_changed(self, index: int) -> None:
        if index == 0:
            self._set_view(0)  # Dashboard
        elif index == 1:
            self._set_view(1)  # Day view (Todo List)
        elif index == 2:
            self._set_view(5)  # Tasks Board
        elif index == 3:
            self._set_view(7)  # Reminders dashboard
        elif index == 4:
            self._set_view(6)  # Settings (embedded in stack)

    # --- Dashboard navigation handlers ------------------------------------

    def _on_dashboard_view_tasks(self) -> None:
        """Navigate from dashboard to the Task Board."""
        self._nav_list.setCurrentRow(2)  # Tasks Board nav item

    def _on_dashboard_open_task(self, task_id: int) -> None:
        """Navigate to Task Board and highlight a specific task."""
        self._nav_list.setCurrentRow(2)  # Tasks Board nav item
        # Highlight the specific task card after a short delay for view to load
        QTimer.singleShot(200, lambda: self._task_board.highlight_task(task_id))
        # Also open the edit dialog for the task
        QTimer.singleShot(300, lambda: self._on_task_clicked(task_id))

    def _on_dashboard_view_events(self) -> None:
        """Navigate from dashboard to the Todo/Day view."""
        self._nav_list.setCurrentRow(1)  # Todo List nav item

    def _on_dashboard_open_event(self, event_date) -> None:
        """Navigate to the Day view for a specific event date."""
        if event_date is not None:
            self._current_date = event_date
            qdate = QDate(event_date.year, event_date.month, event_date.day)
            self._mini_calendar.setSelectedDate(qdate)
        # Switch to Day view to show the event
        self._set_view(1)  # Day view
        self._reload_current_day()

    def _on_dashboard_view_reminders(self) -> None:
        """Navigate from dashboard to the Reminders view."""
        self._nav_list.setCurrentRow(3)  # Reminders nav item → index 7

    def _on_dashboard_view_overdue(self) -> None:
        """Navigate from dashboard to the Task Board to see overdue tasks."""
        self._nav_list.setCurrentRow(2)  # Tasks Board nav item

    # --- Data binding ----------------------------------------------------

    def _reload_current_day(self) -> None:
        self._calendar_controller.load_day(self._current_date)
        # Reload tasks for the current date
        self._reload_tasks()

    def _on_meetings_changed(self) -> None:
        self._set_view(0)
        self._reload_current_day()
        # Refresh reminder view to show newly created meeting reminders
        if hasattr(self, "_reminder_view"):
            self._reminder_view.refresh()

    def _reload_tasks(self) -> None:
        """Reload tasks and update the task board for the current date."""
        # Set the date on the task board
        self._task_board.set_date(self._current_date)
        
        # Load tasks for the current date
        tasks = self._task_service.list_tasks_by_date(self._current_date)
        self._task_board.set_tasks(tasks)

    def _on_task_clicked(self, task_id: int) -> None:
        """Handle task card click - open edit dialog."""
        task = self._task_service.get_task(task_id)
        if task:
            # Get task_date - handle both datetime and date types
            if task.task_date:
                if isinstance(task.task_date, datetime):
                    task_date = task.task_date.date()
                elif isinstance(task.task_date, date):
                    task_date = task.task_date
                else:
                    task_date = self._current_date
            else:
                task_date = self._current_date
            
            dialog = CreateTaskDialog(self, task, task_date=task_date)
            if dialog.exec() == QDialog.Accepted:
                task_data = dialog.get_task_data()
                if task_data:
                    # Update task
                    task.name = task_data["name"]
                    task.description = task_data.get("description")
                    task.deadline = task_data.get("deadline")
                    task.task_date = task_data.get("task_date")
                    task.priority = task_data.get("priority")
                    
                    # Calculate and save progress based on subtasks
                    subtasks_list = task_data.get("subtasks", [])
                    if subtasks_list:
                        total = len(subtasks_list)
                        completed = sum(1 for st in subtasks_list if st.get("completed", False))
                        if total > 0:
                            calculated_progress = (completed / total * 100.0)
                            # Cap progress based on status
                            status = getattr(task, "status", "backlog")
                            if status == "completed":
                                task.progress = 100.0
                            elif status == "in_progress":
                                task.progress = min(calculated_progress, 50.0)
                            else:
                                task.progress = min(calculated_progress, 0.0)
                        else:
                            task.progress = task_data.get("progress", task.progress)
                    else:
                        # Use progress from dialog or keep existing
                        task.progress = task_data.get("progress", task.progress)
                    
                    from app.models.task import SubtaskModel, AttachmentModel, TagModel
                    task.subtasks = [
                        SubtaskModel(id=None, name=st["name"], completed=st.get("completed", False))
                        for st in subtasks_list
                    ]
                    task.attachments = [
                        AttachmentModel(
                            id=None,
                            file_path=att["file_path"],
                            file_name=att["file_name"],
                            file_type=att.get("file_type"),
                            file_size=att.get("file_size"),
                        )
                        for att in task_data.get("attachments", [])
                    ]
                    task.tags = [
                        TagModel(id=None, tag_name=tag_name)
                        for tag_name in task_data.get("tags", [])
                    ]
                    self._task_controller.update_task(task)

    def _on_task_status_changed(self, task_id: int, new_status: str) -> None:
        """Handle task status change from drag-and-drop."""
        # Update task status and progress in database
        task = self._task_service.get_task(task_id)
        if task:
            # Map old "review" status to "in_progress" for backward compatibility
            if new_status == "review":
                new_status = "in_progress"
            
            # Update progress based on status
            status_progress_map = {
                "backlog": 0.0,
                "in_progress": 50.0,
                "completed": 100.0,
            }
            task.status = new_status
            task.progress = status_progress_map.get(new_status, task.progress)
            self._task_controller.update_task(task)

    def _on_task_deleted(self, task_id: int) -> None:
        """Handle task deletion."""
        self._task_controller.delete_task(task_id)

    def _on_add_task_clicked(self) -> None:
        """Handle Add Task button click."""
        # Pass the current date to the dialog
        dialog = CreateTaskDialog(self, task=None, task_date=self._current_date)
        if dialog.exec() == QDialog.Accepted:
            task_data = dialog.get_task_data()
            if task_data:
                self._task_controller.create_task(task_data)

    def _on_search_changed(self, text: str) -> None:
        """Handle search text changes - filter results in real-time."""
        if not text.strip():
            # If search is empty, reload normal view
            self._reload_current_day()
            return
        
        # Filter tasks and meetings based on search query
        search_query = text.strip().lower()
        
        # Search in tasks
        all_tasks = self._task_service.list_all_tasks()
        matching_tasks = [
            task for task in all_tasks
            if search_query in (task.name or "").lower()
            or search_query in (task.description or "").lower()
        ]
        
        # Search in meetings - use a wide date range to get all meetings
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2100, 12, 31)
        all_meetings = self._meeting_service.list_meetings_between(start_date, end_date)
        matching_meetings = [
            meeting for meeting in all_meetings
            if search_query in (meeting.title or "").lower()
            or search_query in (meeting.description or "").lower()
            or (meeting.location and search_query in meeting.location.lower())
        ]
        
        # Update task board with filtered tasks
        if hasattr(self, "_task_board"):
            self._task_board.set_tasks(matching_tasks)

    def _on_search_executed(self) -> None:
        """Handle search execution (Enter key pressed)."""
        search_text = self._search_input.text().strip()
        if search_text:
            self._on_search_changed(search_text)

    def _get_user_name(self) -> str:
        """Get the logged-in user's name, or 'User' if none."""
        try:
            with self._db.session() as session:
                # Get the first active user (typically user_id=1)
                user = session.execute(select(User).where(User.is_active == True).limit(1)).scalar_one_or_none()
                if user and user.name:
                    return user.name
                return "User"
        except Exception:
            return "User"

    # --- Recurrence helpers -----------------------------------------------

    def _generate_recurrence_starts(
        self, start: datetime, recurrence: str, occurrences: int = 10
    ) -> list[datetime]:
        """Expand a recurrence choice into concrete start datetimes."""
        recurrence = (recurrence or "None").lower()
        starts: list[datetime] = [start]

        if recurrence == "none":
            return starts

        if recurrence == "daily":
            delta = timedelta(days=1)
            for i in range(1, occurrences):
                starts.append(start + i * delta)
        elif recurrence == "weekly":
            delta = timedelta(weeks=1)
            for i in range(1, occurrences):
                starts.append(start + i * delta)
        elif recurrence == "monthly":
            for i in range(1, occurrences):
                month_index = start.month - 1 + i
                year = start.year + month_index // 12
                month = month_index % 12 + 1
                last_day = monthrange(year, month)[1]
                day = min(start.day, last_day)
                starts.append(
                    start.replace(year=year, month=month, day=day)
                )

        return starts

    def _on_day_meetings_changed(self, d, meetings) -> None:
        # Remember meetings for editing when clicking existing events
        from collections import defaultdict

        self._meetings_by_hour: dict[time, list] = defaultdict(list)

        # Build a shared events map by hour so all views display the same
        # underlying todos. Each meeting is expanded across its duration in
        # whole-hour blocks.
        events_text: dict[time, str] = {}
        for m in meetings:
            start_dt = m.start_time
            end_dt = m.end_time

            start_hour = start_dt.time().replace(minute=0, second=0, microsecond=0)
            end_hour_value = end_dt.hour
            if end_dt.minute or end_dt.second:
                end_hour_value += 1

            for hour in range(start_hour.hour, min(end_hour_value, 24)):
                slot_time = time(hour=hour, minute=0)
                self._meetings_by_hour[slot_time].append(m)

                label = m.title
                if slot_time in events_text:
                    events_text[slot_time] += f" | {label}"
                else:
                    events_text[slot_time] = label

        # Color the same data differently per view
        def _meeting_to_color(m) -> str:
            return getattr(m, "color_gradient", None) or "#2563EB"

        # Use meeting-specified colors (fallback to blue) so UI matches user choice
        day_events = {
            t: TodoEvent(text=txt, color=_meeting_to_color(self._meetings_by_hour[t][0]))
            for t, txt in events_text.items()
        }

        week_events = day_events
        month_events = day_events
        year_events = day_events

        self._day_view.set_day(d, meetings)
        self._day_view.set_events(day_events)
        # Week/month/year views fetch their own data from DB; set_date triggers refresh
        self._week_view.set_date(d)
        self._month_view.set_date(d)
        self._year_view.set_date(d)

    def _on_year_month_selected(self, target: date) -> None:
        """When a month cell is clicked in the year view, jump to that week.

        If the selected month is the current month, navigate to today.
        Otherwise pick today's day-of-month (clamped to month length).
        """
        today = date.today()
        if target.year == today.year and target.month == today.month:
            nav_date = today
        else:
            # Use today's day number clamped to the selected month length
            _, last_day = monthrange(target.year, target.month)
            day = min(today.day, last_day)
            nav_date = date(target.year, target.month, day)

        qdate = QDate(nav_date.year, nav_date.month, nav_date.day)
        self._mini_calendar.setSelectedDate(qdate)
        self._current_date = nav_date
        self._sync_title()
        self._reload_current_day()
        # Switch to week view so the user sees the week context.
        self._set_view(2)
        self._week_view.focus_day(nav_date)

    def _on_week_day_selected(self, target: date) -> None:
        """When a day is clicked in the week grid, jump to that specific day."""
        qdate = QDate(target.year, target.month, target.day)
        self._mini_calendar.setSelectedDate(qdate)
        self._set_view(0)

    def _on_month_day_selected(self, target: date) -> None:
        """When a day is clicked in the month grid, jump to that week focused on that day."""
        qdate = QDate(target.year, target.month, target.day)
        self._mini_calendar.setSelectedDate(qdate)
        self._current_date = target
        self._sync_title()
        self._reload_current_day()
        # Switch to week view so the user sees that exact day/meeting in context.
        self._set_view(1)
        # Visually highlight the focused day in the week header.
        self._week_view.focus_day(target)

    def _on_week_slot_selected(self, slot_dt: datetime) -> None:
        """When a specific time cell is clicked in the week grid, jump to that day/time and open the add-meeting dialog."""
        from PySide6.QtCore import QDate, QTime

        # Update the "current day" and UI selection.
        target_date = slot_dt.date()
        self._current_date = target_date
        qdate = QDate(target_date.year, target_date.month, target_date.day)
        self._mini_calendar.setSelectedDate(qdate)
        self._set_view(0)
        self._reload_current_day()

        # Open a new MeetingDialog pre-filled with this date and time.
        dlg = MeetingDialog(self)
        dlg._date_edit.setDate(QDate(slot_dt.year, slot_dt.month, slot_dt.day))
        dlg._time_edit.setTime(QTime(slot_dt.hour, slot_dt.minute))

        if not dlg.exec():
            return

        data = dlg.get_data()
        if data is None:
            return

        (
            title,
            start,
            duration_minutes,
            category,
            recurrence,
            description,
            color_gradient,
            reminder_minutes,
        ) = data
        starts = self._generate_recurrence_starts(start, recurrence)

        for s in starts:
            end = s + timedelta(minutes=duration_minutes)
            self._meeting_service.create_meeting(
                title=title,
                start_time=s,
                end_time=end,
                description=description or None,
                color_gradient=color_gradient,
                reminder_minutes=reminder_minutes,
            )
        self._reload_current_day()

    def _open_meeting_for_edit(self, meeting) -> None:
        """Open an existing meeting in MeetingDialog and persist updates."""
        from PySide6.QtCore import QDate, QTime

        if meeting is None:
            return
        dlg = MeetingDialog(self)
        start_dt = meeting.start_time
        end_dt = meeting.end_time
        dlg._date_edit.setDate(QDate(start_dt.year, start_dt.month, start_dt.day))
        dlg._time_edit.setTime(QTime(start_dt.hour, start_dt.minute))
        dlg._title_edit.setText(meeting.title)
        dlg._description_edit.setText(getattr(meeting, "description", "") or "")

        duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
        if duration_minutes % 60 == 0:
            dlg._duration_unit.setCurrentText("hours")
            dlg._duration_spin.setValue(max(1, duration_minutes // 60))
        else:
            dlg._duration_unit.setCurrentText("minutes")
            dlg._duration_spin.setValue(max(1, duration_minutes))

        # Color gradient
        if getattr(meeting, "color_gradient", None):
            idx = dlg._color_combo.findData(meeting.color_gradient)
            if idx >= 0:
                dlg._color_combo.setCurrentIndex(idx)

        if not dlg.exec():
            return

        data = dlg.get_data()
        if data is None:
            return

        (
            title,
            start,
            duration_minutes,
            category,
            recurrence,
            description,
            color_gradient,
            _reminder_minutes,
        ) = data
        meeting.title = title
        meeting.description = description or None
        meeting.start_time = start
        meeting.end_time = start + timedelta(minutes=duration_minutes)
        meeting.color_gradient = color_gradient
        # For now, editing a meeting does not change any previously
        # generated recurrence instances; it only updates this one.
        self._meeting_service.update_meeting(meeting)
        self._reload_current_day()

    def _on_time_slot_activated(self, scope: str, slot_time: time, existing_text: str) -> None:
        """Open an existing meeting for editing, or create a new one for that slot."""
        from PySide6.QtCore import QDate, QTime

        # Block editing/creating meetings in the past. For days before today,
        # the whole day is read‑only; for today, hours earlier than now are
        # also treated as read‑only. Show a compact, styled inline dialog.
        today = date.today()
        now = datetime.now()
        if self._current_date < today or (
            self._current_date == today and slot_time.hour < now.hour
        ):
            self._show_inline_notice(
                "Past time",
                "You can't create or edit meetings in the past.",
                "Please choose a future time slot.",
            )
            return

        # If there is already a meeting in this hour, open it for editing instead.
        meetings_at_time = getattr(self, "_meetings_by_hour", {}).get(
            time(hour=slot_time.hour, minute=0), []
        )
        if meetings_at_time:
            # Edit the first existing meeting in this slot (no recurrence changes here).
            meeting = meetings_at_time[0]
            dlg = MeetingDialog(self)
            # Pre-fill from existing meeting
            start_dt = meeting.start_time
            end_dt = meeting.end_time
            dlg._date_edit.setDate(QDate(start_dt.year, start_dt.month, start_dt.day))
            dlg._time_edit.setTime(QTime(start_dt.hour, start_dt.minute))
            dlg._title_edit.setText(meeting.title)
            if hasattr(dlg, "_description_edit"):
                dlg._description_edit.setText(getattr(meeting, "description", "") or "")

            # Try to map duration back into value + unit
            duration_minutes = int((end_dt - start_dt).total_seconds() // 60)
            if duration_minutes % 60 == 0:
                dlg._duration_unit.setCurrentText("hours")
                dlg._duration_spin.setValue(duration_minutes // 60)
            else:
                dlg._duration_unit.setCurrentText("minutes")
                dlg._duration_spin.setValue(duration_minutes)

            if not dlg.exec():
                return

            data = dlg.get_data()
            if data is None:
                return

            (
                title,
                start,
                duration_minutes,
                category,
                recurrence,
                description,
                color_gradient,
                _reminder_minutes,
            ) = data
            meeting.title = title
            meeting.description = description or None
            meeting.start_time = start
            meeting.end_time = start + timedelta(minutes=duration_minutes)
            meeting.color_gradient = color_gradient
            # Recurrence edits are not propagated to other instances.
            self._meeting_service.update_meeting(meeting)
        else:
            # No existing meeting: create a new one pre-filled with this slot.
            dlg = MeetingDialog(self)
            dlg._date_edit.setDate(QDate(self._current_date.year, self._current_date.month, self._current_date.day))
            dlg._time_edit.setTime(QTime(slot_time.hour, slot_time.minute))
            if existing_text:
                dlg._title_edit.setText(existing_text)

            if not dlg.exec():
                return

            data = dlg.get_data()
            if data is None:
                return

            (
                title,
                start,
                duration_minutes,
                category,
                recurrence,
                description,
                color_gradient,
                reminder_minutes,
            ) = data
            starts = self._generate_recurrence_starts(start, recurrence)

            for s in starts:
                end = s + timedelta(minutes=duration_minutes)
                self._meeting_service.create_meeting(
                    title=title,
                    start_time=s,
                    end_time=end,
                    description=description or None,
                    color_gradient=color_gradient,
                    reminder_minutes=reminder_minutes,
                )
        self._reload_current_day()

    def _open_settings(self) -> None:
        """Switch to the settings view in the main stack."""
        self._settings_view._load_from_settings()  # refresh values
        self._set_view(6)

    def _open_meeting_details(self, item) -> None:
        meeting = self._day_view.meeting_for_item(item)
        if meeting is None:
            return
        dlg = MeetingDetailsDialog(meeting, self)
        dlg.exec()
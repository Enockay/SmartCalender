from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import QShowEvent, QPainter, QColor, QPen, QFont, QBrush, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.task_service import TaskService
from app.services.meeting_service import MeetingService
from app.services.weather_service import WeatherService, WeatherData
from app.services.reminder_service import ReminderService
from app.database.db_manager import DatabaseManager
from app.database.schema import User
from sqlalchemy import select


class ClickableItemFrame(QFrame):
    """A clickable frame widget for dashboard items."""
    
    clicked = Signal()
    
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to emit clicked signal."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class DonutChartWidget(QWidget):
    """A custom-painted donut chart showing task status distribution."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._segments: list[tuple[float, QColor, str]] = []  # (value, color, label)
        self._total = 0.0
        self._center_text = ""
        self._center_sub = ""
        self.setFixedSize(170, 170)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")

    def set_data(
        self,
        segments: list[tuple[float, QColor, str]],
        center_text: str = "",
        center_sub: str = "",
    ) -> None:
        """Set donut chart data.

        Args:
            segments: list of (value, color, label) tuples.
            center_text: bold text in the centre.
            center_sub: smaller text below centre text.
        """
        self._segments = segments
        self._total = sum(s[0] for s in segments) or 1.0
        self._center_text = center_text
        self._center_sub = center_sub
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        size = min(w, h)
        outer_radius = size / 2 - 4
        inner_radius = outer_radius * 0.58  # donut thickness ratio
        arc_width = outer_radius - inner_radius

        center_x = w / 2
        center_y = h / 2

        rect = QRectF(
            center_x - outer_radius + arc_width / 2,
            center_y - outer_radius + arc_width / 2,
            (outer_radius - arc_width / 2) * 2,
            (outer_radius - arc_width / 2) * 2,
        )

        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen.setWidthF(arc_width)

        if not self._segments or self._total == 0:
            # Draw empty ring
            pen.setColor(QColor("#E0E4EE"))
            painter.setPen(pen)
            painter.drawEllipse(rect)
        else:
            start_angle = 90 * 16  # Start from top (12 o'clock)
            for value, color, _label in self._segments:
                if value <= 0:
                    continue
                span = int(round((value / self._total) * 360 * 16))
                pen.setColor(color)
                painter.setPen(pen)
                painter.drawArc(rect, start_angle, -span)  # negative = clockwise
                start_angle -= span

        # Draw centre background circle
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
        centre_r = inner_radius - 2
        painter.drawEllipse(
            QRectF(center_x - centre_r, center_y - centre_r, centre_r * 2, centre_r * 2)
        )

        # Draw centre text
        if self._center_text:
            font = QFont("Segoe UI", 18, QFont.Bold)
            painter.setFont(font)
            painter.setPen(QColor("#3A3A6A"))
            painter.drawText(
                QRectF(center_x - centre_r, center_y - centre_r - 4, centre_r * 2, centre_r * 2),
                Qt.AlignCenter,
                self._center_text,
            )

        if self._center_sub:
            font = QFont("Segoe UI", 9, QFont.Normal)
            painter.setFont(font)
            painter.setPen(QColor("#8B95CC"))
            painter.drawText(
                QRectF(center_x - centre_r, center_y + 4, centre_r * 2, centre_r * 2 - 8),
                Qt.AlignHCenter | Qt.AlignTop,
                self._center_sub,
            )

        painter.end()


class DashboardCard(QFrame):
    """Reusable dashboard card."""

    def __init__(self, title: str, icon_or_parent: str | QWidget | None = None, parent: QWidget | None = None) -> None:
        # Handle backward compatibility: if second arg is QWidget, it's the parent
        if isinstance(icon_or_parent, QWidget):
            parent = icon_or_parent
            icon = ""
        else:
            icon = icon_or_parent or ""
        
        super().__init__(parent)
        self.setObjectName("DashboardCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._main_layout = QVBoxLayout(self)
        # Inner padding so content has breathing room inside each card
        self._main_layout.setContentsMargins(14, 12, 14, 14)
        self._main_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 8)
        header_layout.setSpacing(8)

        # Add icon if provided
        if icon:
            icon_label = QLabel(self)
            icon_label.setText(icon)
            icon_label.setObjectName("DashboardCardIcon")
            header_layout.addWidget(icon_label, alignment=Qt.AlignVCenter)

        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("DashboardCardTitle")
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        self._action_button = QPushButton("View All", self)
        self._action_button.setObjectName("DashboardCardAction")
        self._action_button.setVisible(False)
        self._action_button.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self._action_button)

        self._main_layout.addLayout(header_layout)

        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)
        self._main_layout.addLayout(self._content_layout, stretch=1)

    def set_action_button(self, text: str, callback=None, button_id: str = None) -> None:
        self._action_button.setText(text)
        self._action_button.setVisible(True)
        # Set unique object name for styling
        if button_id:
            self._action_button.setObjectName(button_id)
            # Force stylesheet reapplication after changing object name
            self._action_button.style().unpolish(self._action_button)
            self._action_button.style().polish(self._action_button)
            self._action_button.update()
        try:
            if self._action_button.receivers(self._action_button.clicked) > 0:
                self._action_button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        if callback:
            self._action_button.clicked.connect(callback)

    def add_content(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_stretch(self, stretch: int = 1) -> None:
        self._content_layout.addStretch(stretch)

    def clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            layout = item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif layout is not None:
                self._clear_layout(layout)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)


class DashboardWidget(QWidget):
    """Dashboard overview widget matching the target design more closely."""

    # Navigation signals
    navigateToTaskBoard = Signal()              # "View All" tasks
    navigateToTask = Signal(int)                # "Open" specific task (task_id)
    navigateToTodoList = Signal()               # "View All" events
    navigateToEventDay = Signal(object)         # "Open" specific event (date)
    navigateToReminders = Signal()              # Reminders "Show – Today"
    navigateToOverdue = Signal()                # Overdue "View Report"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DashboardRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._task_service = TaskService()
        self._meeting_service = MeetingService()
        self._reminder_service = ReminderService()
        self._weather_service = WeatherService()
        self._db = DatabaseManager()
        self._current_date = date.today()

        self._build_ui()
        self._load_qss()
        self._refresh_data()
        self._fetch_weather_async()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_data)
        self._refresh_timer.start(300000)

        # Refresh weather every 30 minutes
        self._weather_timer = QTimer(self)
        self._weather_timer.timeout.connect(self._fetch_weather_async)
        self._weather_timer.start(1800000)
        
        # Ensure QSS is applied after widget is shown (to override any parent styles)
        QTimer.singleShot(100, self._load_qss)

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------
    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Hero/Header
        header = QWidget(self)
        header.setObjectName("DashboardHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)

        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        self._greeting_label = QLabel(f"{self._get_greeting()}, {self._get_user_name()}", header)
        self._greeting_label.setObjectName("DashboardGreeting")
        top_row.addWidget(self._greeting_label)

        top_row.addStretch()

        self._status_label = QLabel("🌡  Loading weather…", header)
        self._status_label.setObjectName("DashboardStatus")
        top_row.addWidget(self._status_label)

        header_layout.addLayout(top_row)

        self._date_label = QLabel(self._get_date_string(), header)
        self._date_label.setObjectName("DashboardDate")
        header_layout.addWidget(self._date_label)

        self._hero_note = QLabel("Appointments, tasks, and reminders for today", header)
        self._hero_note.setObjectName("DashboardHeroNote")
        header_layout.addWidget(self._hero_note)

        root_layout.addWidget(header)

        # Scroll content
        scroll = QScrollArea(self)
        scroll.setObjectName("DashboardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("DashboardContent")
        content_layout = QVBoxLayout(content)
        # Remove outer padding so dashboard grid is flush
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        grid = QGridLayout()
        grid.setHorizontalSpacing(1)
        grid.setVerticalSpacing(1)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        self._today_tasks_card = DashboardCard("Today's Tasks", "✓", content)
        self._today_tasks_card.set_action_button("View All", self._on_view_tasks, "DashboardCardActionTasks")

        self._upcoming_events_card = DashboardCard("Upcoming Events", "🗓️", content)
        self._upcoming_events_card.set_action_button("View All", self._on_view_events, "DashboardCardActionEvents")

        self._reminders_card = DashboardCard("Reminders", content)
        self._reminders_card.set_action_button("Show – Today", self._on_manage_reminders, "DashboardCardActionReminders")

        self._overdue_card = DashboardCard("Overdue", content)
        self._overdue_card.set_action_button("✓ View Report", self._on_review_overdue, "DashboardCardActionOverdue")

        grid.addWidget(self._today_tasks_card, 0, 0)
        grid.addWidget(self._upcoming_events_card, 0, 1)
        grid.addWidget(self._reminders_card, 1, 0)
        grid.addWidget(self._overdue_card, 1, 1)

        content_layout.addLayout(grid, stretch=1)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    def _get_greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        if hour < 17:
            return "Good afternoon"
        return "Good evening"

    def _get_date_string(self) -> str:
        today = date.today()
        return today.strftime("%A, %B %d")
    
    def _get_user_name(self) -> str:
        """Get the logged-in user's name, or 'User' if none."""
        try:
            with self._db.session() as session:
                # Prefer the user who is currently logged in.
                user = session.execute(
                    select(User)
                    .where(User.is_logged_in == True)
                    .order_by(User.last_login_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if not user:
                    # Fallback: first active user
                    user = session.execute(
                        select(User).where(User.is_active == True).limit(1)
                    ).scalar_one_or_none()
                if user and user.name:
                    return user.name
                return "User"
        except Exception:
            return "User"

    # ---------------------------------------------------------
    # Refresh
    # ---------------------------------------------------------
    def _refresh_data(self) -> None:
        self._greeting_label.setText(f"{self._get_greeting()}, {self._get_user_name()}")
        self._date_label.setText(self._get_date_string())

        self._load_today_tasks()
        self._load_upcoming_events()
        self._load_reminders()
        self._load_overdue()

    # ---------------------------------------------------------
    # Weather (async — runs in a background thread)
    # ---------------------------------------------------------
    def _fetch_weather_async(self) -> None:
        """Kick off a background thread to fetch weather data."""
        self._status_label.setText("🌡  Loading weather…")
        thread = threading.Thread(target=self._weather_worker, daemon=True)
        thread.start()

    def _weather_worker(self) -> None:
        """Run in a background thread — fetch weather, then update UI via QTimer."""
        try:
            data = self._weather_service.get_current_weather()
        except Exception:
            data = WeatherData(description="Unavailable", icon="🌡")
        # Schedule UI update on the main thread
        QTimer.singleShot(0, lambda: self._apply_weather(data))

    def _apply_weather(self, data: WeatherData) -> None:
        """Apply weather data to the header label (runs on main thread)."""
        if data.city:
            text = f"{data.icon}  {data.description} • {data.temperature_c:.0f}°C / {data.temperature_f:.0f}°F  —  {data.city}"
        else:
            text = f"{data.icon}  {data.description} • {data.temperature_c:.0f}°C / {data.temperature_f:.0f}°F"
        self._status_label.setText(text)
        self._status_label.setToolTip(
            f"Humidity: {data.humidity}%\n"
            f"Wind: {data.wind_speed_kmh:.0f} km/h\n"
            f"Temp: {data.temperature_c:.1f}°C / {data.temperature_f:.1f}°F"
        )

    # ---------------------------------------------------------
    # Today's Tasks
    # ---------------------------------------------------------
    def _load_today_tasks(self) -> None:
        self._today_tasks_card.clear_content()

        try:
            tasks = self._task_service.list_tasks_by_date(self._current_date)
            today_tasks = [t for t in tasks if getattr(t, "status", "") != "completed"][:3]

            if not today_tasks:
                self._today_tasks_card.add_content(self._create_empty_box("No tasks for today"))
                return

            # Add tasks with proper spacing
            for index, task in enumerate(today_tasks):
                task_item = self._create_task_item(task, highlighted=True)
                self._today_tasks_card.add_content(task_item)
            
            # If there's only one task, add some bottom spacing for better appearance
            if len(today_tasks) == 1:
                self._today_tasks_card.add_stretch()

        except Exception:
            self._today_tasks_card.add_content(self._create_empty_box("Unable to load tasks"))

    def _create_task_item(self, task, highlighted: bool = False) -> QWidget:
        # Use clickable frame if highlighted, otherwise regular frame
        if highlighted:
            task_id = getattr(task, "id", None)
            if task_id is not None:
                item = ClickableItemFrame()
                item.clicked.connect(lambda: self.navigateToTask.emit(task_id))
            else:
                item = QFrame()
        else:
            item = QFrame()
        
        # Set priority-based object name for styling
        priority = getattr(task, "priority", "").lower() if getattr(task, "priority", None) else ""
        if priority == "high":
            item.setObjectName("DashboardTaskItemHigh")
        elif priority == "medium":
            item.setObjectName("DashboardTaskItemMedium")
        elif priority == "low":
            item.setObjectName("DashboardTaskItemLow")
        else:
            item.setObjectName("DashboardTaskItem")

        layout = QHBoxLayout(item)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Task icon
        icon_label = QLabel("✓", item)
        icon_label.setObjectName("DashboardTaskIcon")
        layout.addWidget(icon_label, alignment=Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title = QLabel(task.name or "Untitled Task", item)
        title.setObjectName("DashboardItemTitle")
        text_col.addWidget(title)

        meta_parts = []
        if getattr(task, "deadline", None):
            meta_parts.append(task.deadline.strftime("%I:%M %p").lstrip("0"))
        if getattr(task, "priority", None):
            meta_parts.append(str(task.priority).capitalize())

        meta = QLabel(" • ".join(meta_parts) if meta_parts else "Pending", item)
        meta.setObjectName("DashboardItemMeta")
        text_col.addWidget(meta)

        layout.addLayout(text_col, stretch=1)

        return item

    # ---------------------------------------------------------
    # Upcoming Events
    # ---------------------------------------------------------
    def _load_upcoming_events(self) -> None:
        self._upcoming_events_card.clear_content()

        try:
            start = datetime.combine(self._current_date, datetime.min.time())
            end = start + timedelta(days=7)

            events = self._meeting_service.list_meetings_between(start, end)
            events.sort(key=lambda x: x.start_time)
            events = events[:3]

            if not events:
                self._upcoming_events_card.add_content(self._create_empty_box("No upcoming events"))
                return

            for index, meeting in enumerate(events):
                self._upcoming_events_card.add_content(self._create_event_item(meeting, highlighted=True))

        except Exception:
            self._upcoming_events_card.add_content(self._create_empty_box("Unable to load events"))

    def _create_event_item(self, meeting, highlighted: bool = False) -> QWidget:
        # Use clickable frame if highlighted, otherwise regular frame
        if highlighted:
            # Navigate to the day of this event
            event_date = None
            if getattr(meeting, "start_time", None):
                event_date = meeting.start_time.date() if hasattr(meeting.start_time, "date") else meeting.start_time
            
            item = ClickableItemFrame()
            if event_date:
                item.clicked.connect(lambda: self.navigateToEventDay.emit(event_date))
            else:
                item.clicked.connect(lambda: self.navigateToTodoList.emit())
        else:
            item = QFrame()
        
        item.setObjectName("DashboardEventItem")

        layout = QHBoxLayout(item)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        # Event icon
        icon_label = QLabel("📅", item)
        icon_label.setObjectName("DashboardEventIcon")
        layout.addWidget(icon_label, alignment=Qt.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        title = QLabel(meeting.title or "Untitled Event", item)
        title.setObjectName("DashboardItemTitle")
        text_col.addWidget(title)

        meta_parts = []
        if getattr(meeting, "start_time", None):
            meta_parts.append(meeting.start_time.strftime("%I:%M %p").lstrip("0"))
        if getattr(meeting, "location", None):
            meta_parts.append(str(meeting.location))

        meta = QLabel(" • ".join(meta_parts) if meta_parts else "Scheduled", item)
        meta.setObjectName("DashboardItemMeta")
        text_col.addWidget(meta)

        layout.addLayout(text_col, stretch=1)

        return item

    # ---------------------------------------------------------
    # Reminders
    # ---------------------------------------------------------
    def _load_reminders(self) -> None:
        self._reminders_card.clear_content()

        # Fetch real reminders from database - get today's and upcoming reminders
        try:
            # Get today's reminders
            today_reminders = self._reminder_service.get_by_filter("today")
            # Get upcoming reminders (next 7 days)
            upcoming_reminders = self._reminder_service.get_by_filter("upcoming")
            
            # Combine and limit to 8 most relevant reminders
            all_reminders = list(today_reminders) + list(upcoming_reminders)
            # Remove duplicates by ID
            seen_ids = set()
            unique_reminders = []
            for r in all_reminders:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    unique_reminders.append(r)
            
            # Sort by remind_at date/time and take first 8
            unique_reminders.sort(key=lambda x: x.remind_at)
            reminders_to_show = unique_reminders[:8]
            
        except Exception as e:
            # Fallback to empty list if there's an error
            reminders_to_show = []
            from app.core.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"Error loading reminders: {e}", exc_info=True)

        top_list = QVBoxLayout()
        top_list.setContentsMargins(0, 0, 0, 0)
        top_list.setSpacing(10)

        if reminders_to_show:
            for reminder in reminders_to_show:
                # Determine icon and color based on reminder status and category
                icon, icon_type = self._get_reminder_icon(reminder)
                # Format reminder text with time
                time_str = reminder.remind_at.strftime("%I:%M %p").lstrip("0")
                reminder_text = f"{reminder.title} - {time_str}"
                if reminder.meeting_title:
                    reminder_text = f"{reminder.meeting_title} - {time_str}"
                
                top_list.addWidget(self._create_reminder_row(icon, icon_type, reminder_text))
        else:
            top_list.addWidget(self._create_empty_box("No reminders"))

        top_widget = QWidget()
        top_widget.setLayout(top_list)
        self._reminders_card.add_content(top_widget)
        self._reminders_card.add_stretch()
    
    def _get_reminder_icon(self, reminder) -> tuple[str, str]:
        """Get icon and icon type (color) for a reminder based on its status and category."""
        status = reminder.status or "active"
        category = reminder.category or ""
        
        # Status-based icons
        if status == "completed":
            return ("✓", "green")
        elif status == "overdue":
            return ("⚠", "purple")
        elif status == "snoozed":
            return ("⏰", "blue")
        
        # Category-based icons
        if "email" in category.lower() or "Email" in (reminder.notification_type or ""):
            return ("✓", "purple")
        elif "meeting" in category.lower() or reminder.meeting_id:
            return ("✓", "green")
        elif "work" in category.lower():
            return ("📶", "blue")
        elif "personal" in category.lower():
            return ("✓", "green")
        
        # Default for active reminders
        return ("✓", "green")

    def _create_reminder_row(self, icon: str, icon_type: str, text: str) -> QWidget:
        item = QWidget()
        item.setObjectName("DashboardReminderRow")
        item.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        if icon_type == "green":
            # Green circular checkmark needs a container
            icon_container = QFrame(item)
            icon_container.setObjectName("DashboardReminderIconGreenContainer")
            icon_container.setFixedSize(20, 20)
            icon_layout = QVBoxLayout(icon_container)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            icon_layout.setAlignment(Qt.AlignCenter)
            
            icon_label = QLabel(icon, icon_container)
            icon_label.setObjectName("DashboardReminderIconGreen")
            icon_layout.addWidget(icon_label)
            
            layout.addWidget(icon_container, alignment=Qt.AlignVCenter)
        else:
            icon_label = QLabel(icon, item)
            if icon_type == "purple":
                icon_label.setObjectName("DashboardReminderIconPurple")
            else:  # blue
                icon_label.setObjectName("DashboardReminderIconBlue")
            layout.addWidget(icon_label, alignment=Qt.AlignVCenter)

        label = QLabel(text, item)
        label.setObjectName("DashboardReminderText")
        layout.addWidget(label, stretch=1)

        return item


    # ---------------------------------------------------------
    # Overdue
    # ---------------------------------------------------------
    def _load_overdue(self) -> None:
        self._overdue_card.clear_content()

        try:
            all_tasks = self._task_service.list_all_tasks()
            now = datetime.now()

            overdue_tasks = [
                t for t in all_tasks
                if getattr(t, "deadline", None) and t.deadline < now and getattr(t, "status", "") != "completed"
            ][:4]

            body = QWidget()
            body_layout = QHBoxLayout(body)
            body_layout.setContentsMargins(0, 0, 0, 0)
            body_layout.setSpacing(18)

            # Left column — overdue task list
            left_col = QVBoxLayout()
            left_col.setContentsMargins(0, 0, 0, 0)
            left_col.setSpacing(10)

            if overdue_tasks:
                for task in overdue_tasks:
                    left_col.addWidget(self._create_overdue_item(task))
            else:
                no_items = QLabel("✅  All caught up!")
                no_items.setStyleSheet(
                    "color: #10B981; font-size: 13px; font-weight: 600; "
                    "font-family: 'Segoe UI', 'Inter', Arial, sans-serif; "
                    "background: transparent; padding: 8px 0;"
                )
                left_col.addWidget(no_items)

            left_col.addStretch()

            # Right column — donut chart (always shown)
            right_col = QVBoxLayout()
            right_col.setContentsMargins(0, 0, 0, 0)
            right_col.setSpacing(10)

            chart = self._create_donut_chart(all_tasks)
            right_col.addStretch()
            right_col.addWidget(chart, alignment=Qt.AlignCenter)
            right_col.addStretch()

            body_layout.addLayout(left_col, stretch=3)
            body_layout.addLayout(right_col, stretch=2)

            self._overdue_card.add_content(body)

        except Exception:
            self._overdue_card.add_content(self._create_empty_box("Unable to load overdue items"))

    def _create_overdue_item(self, task) -> QWidget:
        item = QWidget()
        layout = QHBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        checkbox = QFrame(item)
        checkbox.setFixedSize(16, 16)
        days_overdue = max(1, (datetime.now() - task.deadline).days)

        if days_overdue > 7:
            checkbox.setObjectName("DashboardOverdueCheckboxRed")
        elif days_overdue > 3:
            checkbox.setObjectName("DashboardOverdueCheckboxBlue")
        else:
            checkbox.setObjectName("DashboardOverdueCheckboxGreen")

        name = QLabel(task.name or "Untitled Task", item)
        name.setObjectName("DashboardOverdueText")

        layout.addWidget(checkbox)
        layout.addWidget(name, stretch=1)

        return item

    def _create_donut_chart(self, all_tasks: list | None = None) -> QWidget:
        """Build a real donut chart reflecting task status distribution."""
        container = QFrame()
        container.setObjectName("DashboardChartWrap")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ---- Gather data ----
        if all_tasks is None:
            try:
                all_tasks = self._task_service.list_all_tasks()
            except Exception:
                all_tasks = []

        now = datetime.now()
        completed = 0
        in_progress = 0
        overdue = 0
        backlog = 0

        for t in all_tasks:
            status = getattr(t, "status", "backlog")
            if status == "completed":
                completed += 1
            elif status == "in_progress":
                if getattr(t, "deadline", None) and t.deadline < now:
                    overdue += 1
                else:
                    in_progress += 1
            else:
                if getattr(t, "deadline", None) and t.deadline < now:
                    overdue += 1
                else:
                    backlog += 1

        total = completed + in_progress + overdue + backlog
        segments: list[tuple[float, QColor, str]] = [
            (completed, QColor("#10B981"), "Completed"),
            (in_progress, QColor("#4A6CF7"), "In Progress"),
            (backlog, QColor("#F59E0B"), "Backlog"),
            (overdue, QColor("#EF4444"), "Overdue"),
        ]

        # ---- Donut ----
        donut = DonutChartWidget(container)
        if total == 0:
            donut.set_data([], center_text="0", center_sub="tasks")
        else:
            pct = int(round(completed / total * 100)) if total else 0
            donut.set_data(segments, center_text=f"{pct}%", center_sub="done")

        layout.addWidget(donut, alignment=Qt.AlignCenter)

        # ---- Legend ----
        legend = QWidget(container)
        legend_layout = QGridLayout(legend)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(4)

        for idx, (count, color, label) in enumerate(segments):
            row = idx // 2
            col = (idx % 2) * 2

            dot = QFrame(legend)
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 5px; border: none;"
            )
            legend_layout.addWidget(dot, row, col, Qt.AlignVCenter)

            text = QLabel(f"{label}  {int(count)}", legend)
            text.setStyleSheet(
                "color: #5A5E8A; font-size: 10px; font-weight: 500; "
                "font-family: 'Segoe UI', 'Inter', Arial, sans-serif; background: transparent;"
            )
            legend_layout.addWidget(text, row, col + 1, Qt.AlignVCenter)

        layout.addWidget(legend, alignment=Qt.AlignCenter)
        return container

    # ---------------------------------------------------------
    # Shared
    # ---------------------------------------------------------
    def _create_empty_box(self, text: str) -> QWidget:
        label = QLabel(text)
        label.setObjectName("DashboardEmpty")
        label.setAlignment(Qt.AlignCenter)
        return label

    # ---------------------------------------------------------
    # Actions
    # ---------------------------------------------------------
    def _on_view_tasks(self) -> None:
        """Navigate to the Task Board."""
        self.navigateToTaskBoard.emit()

    def _on_view_events(self) -> None:
        """Navigate to the Todo List / Day view."""
        self.navigateToTodoList.emit()

    def _on_manage_reminders(self) -> None:
        """Navigate to Reminders view."""
        self.navigateToReminders.emit()

    def _on_review_overdue(self) -> None:
        """Navigate to Task Board (overdue tasks view)."""
        self.navigateToOverdue.emit()

    # ---------------------------------------------------------
    # QSS
    # ---------------------------------------------------------
    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "dashboard.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def refresh(self) -> None:
        self._refresh_data()
    
    def showEvent(self, event: QShowEvent) -> None:
        """Override showEvent to ensure QSS is applied when widget becomes visible."""
        super().showEvent(event)
        # Reload QSS to ensure it overrides any parent styles
        self._load_qss()
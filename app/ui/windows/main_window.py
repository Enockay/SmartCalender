from __future__ import annotations

from datetime import date, datetime, time, timedelta
from calendar import monthrange
from pathlib import Path

from PySide6.QtCore import Qt, QDate, QSize, QTimer
from PySide6.QtGui import QGuiApplication
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
)

from app.controllers.meeting_controller import MeetingController
from app.controllers.calendar_controller import CalendarController
from app.services.meeting_service import MeetingService
from app.services.calendar_service import CalendarService
from app.ui.widgets.day_view_widget import DayViewWidget
from app.ui.widgets.week_view_widget import WeekViewWidget
from app.ui.widgets.month_view_widget import MonthViewWidget
from app.ui.widgets.year_view_widget import YearViewWidget
from app.ui.widgets.mini_calendar_widget import MiniCalendarWidget
from app.services.settings_service import SettingsService
from app.ui.windows.settings_window import SettingsWindow
from app.ui.dialogs.meeting_details_dialog import MeetingDetailsDialog
from app.ui.dialogs.meeting_dialog import MeetingDialog
from app.ui.widgets.todo_list_widget import TodoEvent


class MainWindow(QMainWindow):
    """Main application window with a Monthboard-style layout."""

    def __init__(self, settings: SettingsService | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Smart Calender")
        self.setFixedSize(1000, 750)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        if hasattr(Qt, "WindowFullscreenButtonHint"):
            self.setWindowFlag(Qt.WindowFullscreenButtonHint, False)

        self._settings = settings or SettingsService()
        self._current_date = date.today()

        self._meeting_service = MeetingService(settings_service=self._settings)
        self._calendar_service = CalendarService(self._meeting_service)
        self._meeting_controller = MeetingController(self, self._meeting_service)
        self._calendar_controller = CalendarController(self._calendar_service)

        self._calendar_controller.on_day_meetings_changed = self._on_day_meetings_changed
        self._meeting_controller.on_meetings_changed = self._on_meetings_changed

        self._init_central_layout()
        self._apply_default_view()
        self._reload_current_day()
        self._sync_title()

        # Defer positioning until the window has been shown so we can
        # reliably use the final frame geometry and screen information.
        QTimer.singleShot(0, self._move_to_top_right)

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

    def _init_central_layout(self) -> None:
        central = QWidget(self)

        # Root layout: header bar on top, then body row (sidebar + main content)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # --- Top header bar spanning full width ---
        header_bar = QWidget(central)
        header_bar.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(16, 8, 16, 8)
        header_layout.setSpacing(12)

        # App logo / title on the left
        logo_label = QLabel("📅", header_bar)
        logo_label.setObjectName("AppLogo")
        header_layout.addWidget(logo_label)

        self._header_title = QLabel("Smart Calender", header_bar)
        self._header_title.setObjectName("AppTitle")
        header_layout.addWidget(self._header_title)

        header_layout.addStretch(1)

        # Day / Week / Month buttons in the header
        self._day_button = QPushButton("Day", header_bar)
        self._day_button.setCheckable(True)
        self._day_button.setObjectName("SegmentButton")
        self._day_button.clicked.connect(lambda: self._set_view(0))

        self._week_button = QPushButton("Week", header_bar)
        self._week_button.setCheckable(True)
        self._week_button.setObjectName("SegmentButton")
        self._week_button.clicked.connect(lambda: self._set_view(1))

        self._month_button = QPushButton("Month", header_bar)
        self._month_button.setCheckable(True)
        self._month_button.setObjectName("SegmentButton")
        self._month_button.clicked.connect(lambda: self._set_view(2))

        self._year_button = QPushButton("Year", header_bar)
        self._year_button.setCheckable(True)
        self._year_button.setObjectName("SegmentButton")
        self._year_button.clicked.connect(lambda: self._set_view(3))

        self._day_button.setChecked(True)

        header_layout.addWidget(self._day_button)
        header_layout.addWidget(self._week_button)
        header_layout.addWidget(self._month_button)
        header_layout.addWidget(self._year_button)

        root_layout.addWidget(header_bar)

        # --- Body row: sidebar + main content ---
        body_container = QWidget(central)
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
        sidebar_container = QWidget(parent)
        sidebar_container.setObjectName("LeftSidebar")
        sidebar_container.setFixedWidth(250)

        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(2)

        self._nav_list = QListWidget(sidebar_container)
        self._nav_list.setObjectName("NavList")
        self._nav_list.setSpacing(5)
        self._nav_list.setIconSize(QSize(22, 22))
        self._nav_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        for label in ["📊 Todo List", "✅ Tasks", "📅 Calendar", "⏰ Reminders", "⚙️ Settings",]:
            QListWidgetItem(label, self._nav_list)

        # Keep height reasonable so the mini calendar can sit higher
        # in the sidebar instead of being pushed far down.
        visible_rows = self._nav_list.count() or 5
        row_h = 60
        total_h = visible_rows * row_h + (2 * self._nav_list.frameWidth())
        self._nav_list.setFixedHeight(total_h)

        self._nav_list.setCurrentRow(0)
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self._nav_list)

        # Spacer so the calendar sits slightly below the nav list
        sidebar_layout.addSpacing(18)

        self._mini_calendar_widget = MiniCalendarWidget(sidebar_container)
        self._mini_calendar_widget.setObjectName("MiniCalendarRoot")
        self._mini_calendar_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._mini_calendar = self._mini_calendar_widget.calendar
        self._mini_calendar.selectionChanged.connect(self._on_sidebar_date_changed)
        sidebar_layout.addWidget(self._mini_calendar_widget, alignment=Qt.AlignHCenter)

        # Small flexible spacer so the user area is not glued to the bottom but
        # still leaves some breathing room under the calendar.
        sidebar_layout.addSpacing(6)

        user_container = QWidget(sidebar_container)
        user_container.setObjectName("SidebarUserArea")

        user_layout = QHBoxLayout(user_container)
        user_layout.setContentsMargins(8, 4, 8, 8)
        user_layout.setSpacing(8)
        user_layout.setAlignment(Qt.AlignCenter)

        user_icon_label = QLabel("🛎️", user_container)
        user_icon_label.setObjectName("UserHomeIcon")
        user_layout.addWidget(user_icon_label)

        id_icon_label = QLabel("🪪", user_container)
        id_icon_label.setObjectName("UserIdIcon")
        user_layout.addWidget(id_icon_label)

        self._user_id_label = QLabel("B024", user_container)
        self._user_id_label.setObjectName("UserIdLabel")
        self._user_id_label.setAlignment(Qt.AlignCenter)
        user_layout.addWidget(self._user_id_label)
        sidebar_layout.addWidget(user_container)

        root_layout.addWidget(sidebar_container)

        # Load sidebar-only stylesheet first
        self._load_sidebar_qss(sidebar_container)

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

        self._day_view = DayViewWidget(main_container)
        self._week_view = WeekViewWidget(main_container)
        self._month_view = MonthViewWidget(main_container)
        self._year_view = YearViewWidget(main_container)

        self._stack.addWidget(self._day_view)   # index 0
        self._stack.addWidget(self._week_view)  # index 1
        self._stack.addWidget(self._month_view) # index 2
        self._stack.addWidget(self._year_view)  # index 3
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
        self.setWindowTitle(f"Monthboard Desktop – {text}")
        if hasattr(self, "_header_date_label"):
            self._header_date_label.setText(text)

    def _go_today(self) -> None:
        self._current_date = date.today()
        self._mini_calendar.setSelectedDate(QDate.currentDate())
        self._sync_title()
        self._reload_current_day()

    def _go_previous(self) -> None:
        if self._stack.currentIndex() == 0:
            delta = -1
        elif self._stack.currentIndex() == 1:
            delta = -7
        else:
            delta = -30

        self._current_date = date.fromordinal(self._current_date.toordinal() + delta)
        self._mini_calendar.setSelectedDate(
            QDate(self._current_date.year, self._current_date.month, self._current_date.day)
        )
        self._sync_title()
        self._reload_current_day()

    def _go_next(self) -> None:
        if self._stack.currentIndex() == 0:
            delta = 1
        elif self._stack.currentIndex() == 1:
            delta = 7
        else:
            delta = 30

        self._current_date = date.fromordinal(self._current_date.toordinal() + delta)
        self._mini_calendar.setSelectedDate(
            QDate(self._current_date.year, self._current_date.month, self._current_date.day)
        )
        self._sync_title()
        self._reload_current_day()

    def _set_view(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        if hasattr(self, "_day_button"):
            self._day_button.setChecked(index == 0)
        if hasattr(self, "_week_button"):
            self._week_button.setChecked(index == 1)
        if hasattr(self, "_month_button"):
            self._month_button.setChecked(index == 2)
        if hasattr(self, "_year_button"):
            self._year_button.setChecked(index == 3)
        self._sync_title()

    def _apply_default_view(self) -> None:
        view = self._settings.get_default_view()
        index = {"day": 0, "week": 1, "month": 2}[view]
        self._set_view(index)

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

    def _on_nav_changed(self, index: int) -> None:
        if index == 0:
            self._set_view(2)
        elif index == 1:
            self._set_view(1)
        elif index == 2:
            self._set_view(0)
        elif index == 3:
            self._open_settings()

    # --- Data binding ----------------------------------------------------

    def _reload_current_day(self) -> None:
        self._calendar_controller.load_day(self._current_date)

    def _on_meetings_changed(self) -> None:
        self._set_view(0)
        self._reload_current_day()

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
        """When a month cell is clicked in the year view, jump near that month's meetings.

        If the month has meetings, we navigate to the first meeting date so the
        user lands "where the meetings are". Otherwise we fall back to the first
        day of the month.
        """
        # Determine the date to focus: first meeting in that month if any.
        start = date(target.year, target.month, 1)
        if target.month == 12:
            end = date(target.year + 1, 1, 1)
        else:
            end = date(target.year, target.month + 1, 1)

        meetings = self._meeting_service.list_meetings_between(
            datetime.combine(start, time.min),
            datetime.combine(end, time.min),
        )

        if meetings:
            focus_date = meetings[0].start_time.date()
        else:
            focus_date = start

        qdate = QDate(focus_date.year, focus_date.month, focus_date.day)
        # This will trigger _on_sidebar_date_changed which refreshes all views.
        self._mini_calendar.setSelectedDate(qdate)
        # Switch to week view focused on that date.
        self._set_view(1)

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
        dlg = SettingsWindow(self._settings, self)
        if dlg.exec():
            dlg.apply_changes()

    def _open_meeting_details(self, item) -> None:
        meeting = self._day_view.meeting_for_item(item)
        if meeting is None:
            return
        dlg = MeetingDetailsDialog(meeting, self)
        dlg.exec()
from __future__ import annotations

import calendar
from datetime import datetime, date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.reminder_service import ReminderService, ReminderData, SNOOZE_OPTIONS, ADVANCE_OPTIONS


# ── Colours ────────────────────────────────────────────────────
_STATUS_DOT = {
    "active":    "#22C55E",
    "snoozed":   "#F59E0B",
    "completed": "#94A3B8",
    "overdue":   "#EF4444",
}

_PRIORITY_BADGE = {
    "Critical": ("#FEE2E2", "#DC2626"),
    "High":     ("#FEF3C7", "#D97706"),
    "Medium":   ("#DBEAFE", "#2563EB"),
    "Low":      ("#F0FDF4", "#16A34A"),
}

_CATEGORY_ICON = {
    "Work": "\U0001F4BC", "Personal": "\U0001F3E0", "Health": "\u2764\uFE0F",
    "Meetings": "\U0001F91D", "Finance": "\U0001F4B0", "Bills": "\U0001F9FE",
}

_CATEGORY_DOT_COLOR = {
    "Work": "#3B82F6",
    "Personal": "#A78BFA",
    "Health": "#EF4444",
    "Meetings": "#22C55E",
    "Finance": "#F59E0B",
    "Bills": "#F97316",
}

_FILTER_ICON = {
    "all":       "\u2630",
    "active":    "\u25A1",
    "today":     "\u229E",
    "completed": "\u2611",
    "overdue":   "\u25A3",
}

_STAT_PILL_COLORS = {
    "active":    ("#E0F2FE", "#0369A1"),
    "today":     ("#E0F2FE", "#0369A1"),
    "completed": ("#D1FAE5", "#059669"),
    "overdue":   ("#FEE2E2", "#DC2626"),
    "alert":     ("#FEF3C7", "#D97706"),
}


# ══════════════════════════════════════════════════════════════════
#  MINI CALENDAR with dots
# ══════════════════════════════════════════════════════════════════
class _ReminderMiniCalendar(QWidget):
    """Tiny calendar widget that draws coloured dots for reminder dates."""

    monthChanged = Signal(int, int)  # year, month

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReminderMiniCal")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._year = date.today().year
        self._month = date.today().month
        self._dots: dict[int, list[str]] = {}   # day -> [category, ...]
        self.setMinimumSize(260, 200)
        self.setMaximumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def set_month(self, year: int, month: int) -> None:
        self._year = year
        self._month = month
        self.update()

    def set_dots(self, dots: dict[int, list[str]]) -> None:
        self._dots = dots
        self.update()

    def go_prev(self) -> None:
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self.monthChanged.emit(self._year, self._month)
        self.update()

    def go_next(self) -> None:
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self.monthChanged.emit(self._year, self._month)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Header
        header_h = 28
        month_name = f"{calendar.month_name[self._month]} {self._year}"
        hdr_font = QFont("Helvetica Neue", 11, QFont.Bold)
        hdr_font.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        p.setFont(hdr_font)
        p.setPen(QColor("#1E293B"))
        # Chevron placeholder (drawn as text)
        p.drawText(8, 2, w - 16, header_h, Qt.AlignLeft | Qt.AlignVCenter, f"{month_name}  \u25BE")

        # Weekday headers
        top = header_h + 2
        cell_w = w / 7
        cell_h = (h - top - 14) / 7  # 1 row weekday + max 6 rows
        day_font = QFont("Helvetica Neue", 9)
        day_font.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        p.setFont(day_font)
        p.setPen(QColor("#94A3B8"))
        for i, dn in enumerate(["S", "M", "T", "W", "T", "F", "S"]):
            x = i * cell_w
            p.drawText(int(x), int(top), int(cell_w), int(cell_h), Qt.AlignCenter, dn)

        # Days
        top += cell_h
        first_wd, n_days = calendar.monthrange(self._year, self._month)
        # calendar.monthrange returns weekday of first day (Mon=0), adjust for Sun=0
        first_col = (first_wd + 1) % 7

        today = date.today()
        num_font = QFont("Helvetica Neue", 9)
        num_font.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        p.setFont(num_font)

        day = 1
        for row in range(6):
            for col in range(7):
                if row == 0 and col < first_col:
                    continue
                if day > n_days:
                    break
                x = col * cell_w
                y = top + row * cell_h
                cx = x + cell_w / 2
                cy = y + cell_h * 0.42

                # Today highlight
                is_today = (self._year == today.year and self._month == today.month and day == today.day)
                if is_today:
                    p.setBrush(QColor("#6366F1"))
                    p.setPen(Qt.NoPen)
                    r = min(cell_w, cell_h) * 0.38
                    p.drawEllipse(int(cx - r), int(cy - r), int(2 * r), int(2 * r))
                    p.setPen(QColor("#FFFFFF"))
                else:
                    p.setPen(QColor("#334155"))

                p.drawText(int(x), int(y), int(cell_w), int(cell_h * 0.85), Qt.AlignCenter, str(day))

                # Dots for reminders
                cats = self._dots.get(day, [])
                if cats:
                    dot_y = y + cell_h * 0.78
                    total = min(len(cats), 3)
                    start_x = cx - (total * 6) / 2
                    for di, cat in enumerate(cats[:3]):
                        color = _CATEGORY_DOT_COLOR.get(cat, "#94A3B8")
                        p.setBrush(QColor(color))
                        p.setPen(Qt.NoPen)
                        p.drawEllipse(int(start_x + di * 6), int(dot_y), 5, 5)

                day += 1

        # Legend
        legend_y = h - 14
        leg_font = QFont("Helvetica Neue", 8)
        leg_font.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        p.setFont(leg_font)
        lx = 8
        for cat, color in list(_CATEGORY_DOT_COLOR.items())[:4]:
            p.setBrush(QColor(color))
            p.setPen(Qt.NoPen)
            p.drawEllipse(int(lx), int(legend_y + 1), 5, 5)
            p.setPen(QColor("#64748B"))
            p.drawText(int(lx + 8), int(legend_y - 1), 60, 12, Qt.AlignLeft | Qt.AlignVCenter, cat)
            lx += 60

        p.end()


# ══════════════════════════════════════════════════════════════════
#  ENHANCED REMINDER CARD
# ══════════════════════════════════════════════════════════════════
class ReminderCardWidget(QFrame):
    """Single reminder card with meeting info."""

    editClicked = Signal(int)
    deleteClicked = Signal(int)
    completeClicked = Signal(int)
    snoozeClicked = Signal(int, int)

    def __init__(self, data: ReminderData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data = data
        self.setObjectName("ReminderCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._build()

    def _build(self) -> None:
        d = self._data
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        # Top row: title + time
        top = QHBoxLayout()
        top.setSpacing(8)

        # Status dot
        dot = QLabel(self)
        dot.setFixedSize(10, 10)
        color = _STATUS_DOT.get(d.status, "#94A3B8")
        dot.setStyleSheet(f"background: {color}; border-radius: 5px; border: none;")
        top.addWidget(dot, 0, Qt.AlignTop)

        # Title
        title_text = d.title
        if d.meeting_title and d.meeting_id:
            title_text = d.meeting_title if d.title.startswith("Meeting:") else d.title
        title = QLabel(title_text, self)
        title.setObjectName("ReminderCardTitle")
        _font = QFont("Helvetica Neue", 14, QFont.Bold)
        _font.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        title.setFont(_font)
        if d.status == "completed":
            title.setStyleSheet("text-decoration: line-through; color: #94A3B8;")
        top.addWidget(title, 1)

        # Time badge (right aligned)
        time_str = d.remind_at.strftime("%I:%M %p")
        time_lbl = QLabel(time_str, self)
        time_lbl.setObjectName("ReminderCardTimeBadge")
        top.addWidget(time_lbl, 0, Qt.AlignRight | Qt.AlignTop)

        root.addLayout(top)

        # Info row: date, meeting time range, advance, location
        info_parts = []
        now = datetime.now()
        r_date = d.remind_at.date()
        if r_date == now.date():
            info_parts.append("Today")
        elif r_date == now.date() + timedelta(days=1):
            info_parts.append("Tomorrow")
        elif r_date == now.date() - timedelta(days=1):
            info_parts.append("Yesterday")
        else:
            info_parts.append(r_date.strftime("%b %d"))

        if d.meeting_start:
            info_parts.append(f"\U0001F552 {d.meeting_start.strftime('%I:%M %p')}")
        if d.meeting_location:
            info_parts.append(f"\U0001F4CD {d.meeting_location}")
        if d.advance_minutes and d.advance_minutes > 0:
            info_parts.append(f"\U0001F514 {d.advance_minutes}m before")

        info_lbl = QLabel("  \u2022  ".join(info_parts), self)
        info_lbl.setObjectName("ReminderCardInfo")
        root.addWidget(info_lbl)

        # Badges row
        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        badge_row.setContentsMargins(0, 2, 0, 0)

        if d.repeat_type and d.repeat_type != "None":
            rep_badge = self._badge(f"\u25A0 {d.repeat_type}", "#E0F2FE", "#0369A1")
            badge_row.addWidget(rep_badge)

        cat_icon = _CATEGORY_ICON.get(d.category, "\U0001F4CC")
        cat_badge = self._badge(f"{cat_icon} {d.category}", "#F1F5F9", "#475569")
        badge_row.addWidget(cat_badge)

        p_bg, p_fg = _PRIORITY_BADGE.get(d.priority, ("#F1F5F9", "#475569"))
        pri_badge = self._badge(d.priority, p_bg, p_fg)
        badge_row.addWidget(pri_badge)

        if d.notification_type:
            n_icon = "\U0001F50A" if "Sound" in d.notification_type else "\U0001F514"
            notif_badge = self._badge(f"{n_icon} {d.notification_type}", "#FEF3C7", "#92400E")
        badge_row.addWidget(notif_badge)

        badge_row.addStretch()

        # Action buttons
        if d.status != "completed":
            edit_btn = QPushButton("\u2261\u2571", self)
            edit_btn.setObjectName("ReminderCardActionBtn")
            edit_btn.setToolTip("Edit")
            edit_btn.setFixedSize(32, 28)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.clicked.connect(lambda: self.editClicked.emit(d.id))
            badge_row.addWidget(edit_btn)

            snooze_btn = QPushButton("\u2795", self)
            snooze_btn.setObjectName("ReminderCardActionBtn")
            snooze_btn.setToolTip("Snooze")
            snooze_btn.setFixedSize(32, 28)
            snooze_btn.setCursor(Qt.PointingHandCursor)
            snooze_btn.clicked.connect(lambda: self._show_snooze_menu(snooze_btn))
            badge_row.addWidget(snooze_btn)
        else:
            edit_btn = QPushButton("\u2261\u2571", self)
            edit_btn.setObjectName("ReminderCardActionBtn")
            edit_btn.setToolTip("Edit")
            edit_btn.setFixedSize(32, 28)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.clicked.connect(lambda: self.editClicked.emit(d.id))
            badge_row.addWidget(edit_btn)

        root.addLayout(badge_row)

    def _badge(self, text: str, bg: str, fg: str) -> QLabel:
        lbl = QLabel(f" {text} ", self)
        lbl.setObjectName("ReminderBadgeInline")
        lbl.setStyleSheet(
            f"background: {bg}; color: {fg}; border-radius: 4px; "
            f"padding: 2px 8px; font-size: 11px; font-weight: 600; border: none;"
        )
        return lbl

    def _show_snooze_menu(self, btn: QPushButton) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 4px; }
            QMenu::item { color: #334155; padding: 8px 20px; font-size: 13px; }
            QMenu::item:selected { background: #EFF6FF; border-radius: 4px; }
        """)
        for minutes, label in SNOOZE_OPTIONS:
            action = menu.addAction(f"\u23F1  {label}")
            action.triggered.connect(lambda checked, m=minutes: self.snoozeClicked.emit(self._data.id, m))
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))


# ══════════════════════════════════════════════════════════════════
#  MAIN REMINDER DASHBOARD (two-column layout)
# ══════════════════════════════════════════════════════════════════
class ReminderDashboardWidget(QWidget):
    """Full-featured Reminder screen with two-column layout.

    Uses an internal QStackedWidget:
      page 0 = two-column list view (left: cards, right: stats/calendar/filters)
      page 1 = inline form (create / edit)
    """

    reminderChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReminderRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._service = ReminderService()
        self._current_filter = "all"
        self._search_query = ""

        self._build_ui()
        self._load_qss()
        self._refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60_000)

    # ── UI Build ──────────────────────────────────────────────────
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._pages = QStackedWidget(self)
        outer.addWidget(self._pages)

        # ════════ PAGE 0: List view ════════
        list_page = QWidget()
        list_page.setObjectName("ReminderRoot")
        lp_lay = QVBoxLayout(list_page)
        lp_lay.setContentsMargins(0, 0, 0, 0)
        lp_lay.setSpacing(0)

        # ── Header bar ──
        header = QWidget(list_page)
        header.setObjectName("ReminderHeader")
        header.setFixedHeight(60)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 0, 24, 0)

        title = QLabel("Reminders", header)
        title.setObjectName("ReminderHeaderTitle")
        _hfont = QFont("Helvetica Neue", 20, QFont.Bold)
        _hfont.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        title.setFont(_hfont)
        h_lay.addWidget(title)
        h_lay.addStretch()

        # Search in header
        self._search_edit = QLineEdit(header)
        self._search_edit.setObjectName("ReminderSearchField")
        self._search_edit.setPlaceholderText("\U0001F50D  All Reminders")
        self._search_edit.setFixedWidth(220)
        self._search_edit.textChanged.connect(self._on_search)
        h_lay.addWidget(self._search_edit)

        h_lay.addSpacing(10)

        # Category dropdown
        self._cat_combo = QComboBox(header)
        self._cat_combo.setObjectName("ReminderCatCombo")
        self._cat_combo.addItem("All Categories")
        from app.services.reminder_service import CATEGORIES
        for c in CATEGORIES:
            self._cat_combo.addItem(c)
        self._cat_combo.currentTextChanged.connect(self._on_category_changed)
        h_lay.addWidget(self._cat_combo)

        h_lay.addSpacing(10)

        add_btn = QPushButton("  + Add Reminder  ", header)
        add_btn.setObjectName("ReminderAddBtn")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.clicked.connect(self._on_add)
        h_lay.addWidget(add_btn)
        lp_lay.addWidget(header)

        # ── Filter tabs bar ──
        filter_bar = QWidget(list_page)
        filter_bar.setObjectName("ReminderFilterBar")
        filter_bar.setFixedHeight(44)
        fb_lay = QHBoxLayout(filter_bar)
        fb_lay.setContentsMargins(24, 0, 24, 0)
        fb_lay.setSpacing(4)

        self._filter_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("all", "All"), ("today", "Today"), ("upcoming", "Upcoming"),
            ("completed", "Completed"), ("overdue", "Overdue"),
        ]:
            btn = QPushButton(label, filter_bar)
            btn.setObjectName("ReminderFilterBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(key == "all")
            btn.clicked.connect(lambda checked, k=key: self._set_filter(k))
            fb_lay.addWidget(btn)
            self._filter_buttons[key] = btn

        # Today count badge (updated dynamically)
        self._today_badge = QLabel("", filter_bar)
        self._today_badge.setObjectName("ReminderTodayBadge")
        self._today_badge.setVisible(False)
        fb_lay.addWidget(self._today_badge)

        fb_lay.addStretch()
        lp_lay.addWidget(filter_bar)

        # ── Two-column body ──
        body = QWidget(list_page)
        body.setObjectName("ReminderBody")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # ──── LEFT COLUMN: Reminder list ────
        left_col = QWidget(body)
        left_col.setObjectName("ReminderLeftCol")
        left_lay = QVBoxLayout(left_col)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        # Section header "Today (N)"
        self._section_header = QLabel("Today (0)", left_col)
        self._section_header.setObjectName("ReminderSectionHeader")
        _shf = QFont("Helvetica Neue", 14, QFont.Bold)
        _shf.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        self._section_header.setFont(_shf)
        self._section_header.setContentsMargins(24, 4, 24, 6)
        left_lay.addWidget(self._section_header)

        # Scrollable card list
        self._scroll = QScrollArea(left_col)
        self._scroll.setObjectName("ReminderListScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_widget.setObjectName("ReminderListContainer")
        self._list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(10)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        left_lay.addWidget(self._scroll, 1)

        body_lay.addWidget(left_col, 70)

        # ──── RIGHT COLUMN: Stats, Calendar, Category sidebar ────
        right_col = QWidget(body)
        right_col.setObjectName("ReminderRightCol")
        right_lay = QVBoxLayout(right_col)
        right_lay.setContentsMargins(12, 8, 12, 8)
        right_lay.setSpacing(8)

        # Stats pills row
        stats_frame = QWidget(right_col)
        stats_frame.setObjectName("ReminderStatsFrame")
        stats_lay = QHBoxLayout(stats_frame)
        stats_lay.setContentsMargins(0, 0, 0, 0)
        stats_lay.setSpacing(4)

        self._stat_pills: dict[str, QLabel] = {}
        for key, label in [("active", "Active"), ("today", "Today's"), ("completed", "Completed"), ("overdue", "Overdue")]:
            pill = QLabel(f"{label} 0", stats_frame)
            pill.setObjectName(f"ReminderPill_{key}")
            pill.setAlignment(Qt.AlignCenter)
            stats_lay.addWidget(pill)
            self._stat_pills[key] = pill

        # Alert bell badge
        self._alert_pill = QLabel("\U0001F514 0", stats_frame)
        self._alert_pill.setObjectName("ReminderPill_alert")
        self._alert_pill.setAlignment(Qt.AlignCenter)
        stats_lay.addWidget(self._alert_pill)

        right_lay.addWidget(stats_frame)

        # Mini calendar with dots
        cal_header = QHBoxLayout()
        cal_header.setSpacing(4)

        self._mini_cal = _ReminderMiniCalendar(right_col)
        right_lay.addWidget(self._mini_cal)

        # Search + category combo (right panel)
        search_row = QHBoxLayout()
        search_row.setSpacing(4)
        self._right_search = QLineEdit(right_col)
        self._right_search.setObjectName("ReminderSearchField")
        self._right_search.setPlaceholderText("\U0001F50D Search")
        self._right_search.textChanged.connect(self._on_search)
        search_row.addWidget(self._right_search)

        self._right_cat = QComboBox(right_col)
        self._right_cat.setObjectName("ReminderCatCombo")
        self._right_cat.addItem("All")
        for c in CATEGORIES:
            self._right_cat.addItem(c)
        self._right_cat.currentTextChanged.connect(self._on_right_cat_changed)
        search_row.addWidget(self._right_cat)
        right_lay.addLayout(search_row)

        # Category filter buttons (sidebar style)
        filter_frame = QFrame(right_col)
        filter_frame.setObjectName("ReminderCategoryFrame")
        ff_lay = QVBoxLayout(filter_frame)
        ff_lay.setContentsMargins(0, 4, 0, 4)
        ff_lay.setSpacing(1)

        self._sidebar_filter_buttons: dict[str, QPushButton] = {}
        for key, icon, label in [
            ("all",       "\u2630", "All Reminders"),
            ("active",    "\u25A1", "Active"),
            ("today",     "\u229E", "Today's"),
            ("completed", "\u2611", "Completed"),
            ("overdue",   "\u25A3", "Overdue"),
        ]:
            btn = QPushButton(f"  {icon}  {label}", filter_frame)
            btn.setObjectName("ReminderSideFilterBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(key == "all")
            btn.clicked.connect(lambda checked, k=key: self._set_filter_from_sidebar(k))
            ff_lay.addWidget(btn)
            self._sidebar_filter_buttons[key] = btn

        right_lay.addWidget(filter_frame)
        right_lay.addStretch()

        body_lay.addWidget(right_col, 30)
        lp_lay.addWidget(body, 1)

        self._pages.addWidget(list_page)  # index 0

        # ════════ PAGE 1: Inline form ════════
        from app.ui.dialogs.reminder_dialog import ReminderFormPanel
        self._form_panel = ReminderFormPanel(self)
        self._form_panel.saved.connect(self._on_form_saved)
        self._form_panel.cancelled.connect(self._show_list)
        self._pages.addWidget(self._form_panel)  # index 1

    # ── Page switching ────────────────────────────────────────────
    def _show_list(self) -> None:
        self._pages.setCurrentIndex(0)
        self._refresh()

    def _show_form(self, reminder: ReminderData | None = None) -> None:
        self._form_panel.set_reminder(reminder)
        self._pages.setCurrentIndex(1)

    def _on_form_saved(self) -> None:
        self._show_list()
        self.reminderChanged.emit()

    # ── Data refresh ──────────────────────────────────────────────
    def _refresh(self) -> None:
        self._service.update_overdue()

        # Update stats
        counts = self._service.get_counts()
        for key, pill in self._stat_pills.items():
            n = counts.get(key, 0)
            labels = {"active": "Active", "today": "Today's", "completed": "Completed", "overdue": "Overdue"}
            pill.setText(f"{labels.get(key, key)} {n}")
        self._alert_pill.setText(f"\U0001F514 {counts.get('overdue', 0)}")

        # Update sidebar filter counts
        for key, btn in self._sidebar_filter_buttons.items():
            icon = _FILTER_ICON.get(key, "")
            labels = {"all": "All Reminders", "active": "Active", "today": "Today's", "completed": "Completed", "overdue": "Overdue"}
            n = counts.get(key, counts.get("total", 0)) if key == "all" else counts.get(key, 0)
            btn.setText(f"  {icon}  {labels.get(key, key)}")
            # Add count label to the right
            btn.setProperty("count", str(n))
            btn.setStyleSheet(btn.styleSheet())  # force re-read

        # Update today badge
        today_n = counts.get("today", 0)
        if today_n > 0:
            fkey = "today"
            if fkey in self._filter_buttons:
                self._filter_buttons[fkey].setText(f"Today  {today_n}")
        self._today_badge.setVisible(today_n > 0)
        self._today_badge.setText(str(today_n))

        # Update section header
        filter_labels = {"all": "All", "today": "Today", "upcoming": "Upcoming", "active": "Active", "completed": "Completed", "overdue": "Overdue"}
        label = filter_labels.get(self._current_filter, "All")

        # Get reminders
        if self._search_query:
            reminders = self._service.search(self._search_query)
        else:
            reminders = self._service.get_by_filter(self._current_filter)

        self._section_header.setText(f"{label} ({len(reminders)})")
        self._populate_list(reminders)

        # Update mini calendar dots
        try:
            date_cats = self._service.get_reminder_dates()
            today = date.today()
            cal_month = self._mini_cal._month
            cal_year = self._mini_cal._year
            dots: dict[int, list[str]] = {}
            for d, cats in date_cats.items():
                if d.year == cal_year and d.month == cal_month:
                    dots[d.day] = cats
            self._mini_cal.set_dots(dots)
        except Exception:
            pass

    def _populate_list(self, reminders: list[ReminderData]) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not reminders:
            empty = QLabel("\U0001F4ED  No reminders found", self._list_widget)
            empty.setObjectName("ReminderEmptyLabel")
            empty.setAlignment(Qt.AlignCenter)
            self._list_layout.insertWidget(0, empty)
            return

        for r in reminders:
            card = ReminderCardWidget(r, self._list_widget)
            card.editClicked.connect(self._on_edit)
            card.deleteClicked.connect(self._on_delete)
            card.completeClicked.connect(self._on_complete)
            card.snoozeClicked.connect(self._on_snooze)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    # ── Filter / Search ───────────────────────────────────────────
    def _set_filter(self, key: str) -> None:
        self._current_filter = key
        for k, btn in self._filter_buttons.items():
            btn.setChecked(k == key)
        for k, btn in self._sidebar_filter_buttons.items():
            btn.setChecked(k == key)
        self._search_query = ""
        self._search_edit.clear()
        self._right_search.clear()
        self._refresh()

    def _set_filter_from_sidebar(self, key: str) -> None:
        self._set_filter(key)

    def _on_search(self, text: str) -> None:
        self._search_query = text.strip()
        # Sync both search boxes
        sender = self.sender()
        if sender == self._search_edit:
            self._right_search.blockSignals(True)
            self._right_search.setText(text)
            self._right_search.blockSignals(False)
        elif sender == self._right_search:
            self._search_edit.blockSignals(True)
            self._search_edit.setText(text)
            self._search_edit.blockSignals(False)

        if self._search_query:
            for btn in self._filter_buttons.values():
                btn.setChecked(False)
            for btn in self._sidebar_filter_buttons.values():
                btn.setChecked(False)
        else:
            self._filter_buttons.get(self._current_filter, self._filter_buttons["all"]).setChecked(True)
            self._sidebar_filter_buttons.get(self._current_filter, self._sidebar_filter_buttons["all"]).setChecked(True)
        self._refresh()

    def _on_category_changed(self, text: str) -> None:
        if text == "All Categories":
            self._search_query = ""
        else:
            self._search_query = text
        self._refresh()

    def _on_right_cat_changed(self, text: str) -> None:
        if text == "All":
            self._search_query = ""
        else:
            self._search_query = text
        self._refresh()

    # ── Actions ───────────────────────────────────────────────────
    def _on_add(self) -> None:
        self._show_form(reminder=None)

    def _on_edit(self, reminder_id: int) -> None:
        all_r = self._service.get_all()
        data = next((r for r in all_r if r.id == reminder_id), None)
        if data:
            self._show_form(reminder=data)

    def _on_delete(self, reminder_id: int) -> None:
        self._service.delete_reminder(reminder_id)
        self._refresh()
        self.reminderChanged.emit()

    def _on_complete(self, reminder_id: int) -> None:
        self._service.mark_completed(reminder_id)
        self._refresh()
        self.reminderChanged.emit()

    def _on_snooze(self, reminder_id: int, minutes: int) -> None:
        self._service.snooze(reminder_id, minutes)
        self._refresh()
        self.reminderChanged.emit()

    # ── Timer tick ────────────────────────────────────────────────
    def _tick(self) -> None:
        self._service.update_overdue()
        if self._pages.currentIndex() == 0:
            self._refresh()
        self._check_due_notifications()

    def _check_due_notifications(self) -> None:
        due = self._service.get_due_reminders()
        for r in due:
            if "Desktop" in (r.notification_type or ""):
                try:
                    from app.ui.windows.reminder_popup import ReminderPopup
                    popup = ReminderPopup(r.title, r.remind_at.strftime("%I:%M %p"), self)
                    popup.show()
                except Exception:
                    pass
            if "Sound" in (r.notification_type or ""):
                QApplication.beep()
            self._service.dismiss(r.id)

    # ── QSS ───────────────────────────────────────────────────────
    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "reminder_main.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._pages.currentIndex() == 0:
            self._refresh()


# ══════════════════════════════════════════════════════════════════
#  SMALL REMINDER WIDGET (for meeting dialog)
# ══════════════════════════════════════════════════════════════════
class ReminderWidget(QWidget):
    """Simple reminder timing widget used inside the MeetingDialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReminderWidgetRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(10)

        lbl = QLabel("\U0001F514 Reminder:", self)
        lbl.setObjectName("ReminderLabel")
        lay.addWidget(lbl)

        self._time_combo = QComboBox(self)
        self._time_combo.setObjectName("ReminderTimeCombo")
        for minutes, label in ADVANCE_OPTIONS:
            self._time_combo.addItem(label, minutes)
        self._time_combo.setCurrentIndex(2)  # "10 minutes before"
        lay.addWidget(self._time_combo)

        lay.addStretch()

    def reminder_minutes(self) -> int:
        return self._time_combo.currentData() or 10

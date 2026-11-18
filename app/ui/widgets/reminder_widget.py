from __future__ import annotations

from app.core import prefs
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

_FILTER_TABS = [
    ("upcoming", "Upcoming"),
    ("today", "Today"),
    ("overdue", "Overdue"),
    ("completed", "Completed"),
]


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
        time_str = prefs.fmt_time(d.remind_at)
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
        self._current_filter = "upcoming"
        self._search_query = ""
        self._category = ""

        # Sync existing meeting reminders on first load
        QTimer.singleShot(500, self._sync_existing_reminders)

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
        self._search_edit.setPlaceholderText("Search reminders")
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

        # ── One row of filter tabs (review A4: no duplicate filters) ──
        filter_bar = QWidget(list_page)
        filter_bar.setObjectName("ReminderFilterBar")
        filter_bar.setFixedHeight(44)
        fb_lay = QHBoxLayout(filter_bar)
        fb_lay.setContentsMargins(24, 0, 24, 0)
        fb_lay.setSpacing(4)

        self._filter_buttons: dict[str, QPushButton] = {}
        for key, label in _FILTER_TABS:
            btn = QPushButton(label, filter_bar)
            btn.setObjectName("ReminderFilterBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(key == self._current_filter)
            btn.setAccessibleName(f"Show {label.lower()} reminders")
            btn.clicked.connect(lambda checked, k=key: self._set_filter(k))
            fb_lay.addWidget(btn)
            self._filter_buttons[key] = btn

        fb_lay.addStretch()
        lp_lay.addWidget(filter_bar)

        # ── Reminder list ──
        body = QWidget(list_page)
        body.setObjectName("ReminderBody")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._section_header = QLabel("", body)
        self._section_header.setObjectName("ReminderSectionHeader")
        _shf = QFont("Helvetica Neue", 14, QFont.Bold)
        _shf.setFamilies(["Inter", "Helvetica Neue", "Segoe UI", "sans-serif"])
        self._section_header.setFont(_shf)
        self._section_header.setContentsMargins(24, 8, 24, 6)
        body_lay.addWidget(self._section_header)

        self._scroll = QScrollArea(body)
        self._scroll.setObjectName("ReminderListScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._list_widget = QWidget()
        self._list_widget.setObjectName("ReminderListContainer")
        self._list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(24, 0, 24, 16)
        self._list_layout.setSpacing(10)
        self._list_layout.addStretch()

        self._scroll.setWidget(self._list_widget)
        body_lay.addWidget(self._scroll, 1)
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
    def _sync_existing_reminders(self) -> None:
        """Sync existing reminders that are linked to meetings."""
        try:
            count = self._service.sync_existing_meeting_reminders()
            if count > 0:
                self._refresh()
        except Exception:
            pass  # Silently fail if sync has issues

    def refresh(self) -> None:
        """Public method to refresh the reminder list."""
        self._refresh()

    def _refresh(self) -> None:
        self._service.update_overdue()

        counts = self._service.get_counts()
        tab_counts = {
            "upcoming": counts.get("active", 0) + counts.get("snoozed", 0),
            "today": counts.get("today", 0),
            "overdue": counts.get("overdue", 0),
            "completed": counts.get("completed", 0),
        }
        for key, label in _FILTER_TABS:
            n = tab_counts.get(key, 0)
            self._filter_buttons[key].setText(f"{label}  {n}" if n else label)

        if self._search_query:
            reminders = self._service.search(self._search_query)
            heading = f'Results for "{self._search_query}"'
        else:
            reminders = self._service.get_by_filter(self._current_filter)
            heading = dict(_FILTER_TABS).get(self._current_filter, "Reminders")
        if self._category:
            reminders = [r for r in reminders if (getattr(r, "category", "") or "") == self._category]
            heading = f"{heading} · {self._category}"

        self._section_header.setText(f"{heading} ({len(reminders)})")
        self._populate_list(reminders)

    def _populate_list(self, reminders: list[ReminderData]) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().hide()  # hide now; deletion happens on the next event loop pass
                item.widget().deleteLater()

        if not reminders:
            self._list_layout.insertWidget(0, self._empty_state())
            return

        for r in reminders:
            card = ReminderCardWidget(r, self._list_widget)
            card.editClicked.connect(self._on_edit)
            card.deleteClicked.connect(self._on_delete)
            card.completeClicked.connect(self._on_complete)
            card.snoozeClicked.connect(self._on_snooze)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _empty_state(self) -> QWidget:
        """Empty lists explain what belongs there and offer the next step (review A3)."""
        messages = {
            "upcoming": "No upcoming reminders. Add one and SmartCalender will notify you at the right time.",
            "today": "Nothing to be reminded about today.",
            "overdue": "Nothing overdue. You are all caught up.",
            "completed": "Reminders you complete will appear here.",
        }
        text = (
            "No reminders match your search."
            if self._search_query
            else messages.get(self._current_filter, "No reminders yet.")
        )
        box = QWidget(self._list_widget)
        box.setObjectName("ReminderEmptyState")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 48, 0, 0)
        lay.setSpacing(12)
        lbl = QLabel(text, box)
        lbl.setObjectName("ReminderEmptyLabel")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        if self._current_filter in ("upcoming", "today") and not self._search_query:
            btn = QPushButton("Add a reminder", box)
            btn.setObjectName("ReminderAddBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self._on_add)
            lay.addWidget(btn, alignment=Qt.AlignHCenter)
        return box

    # ── Filter / Search ───────────────────────────────────────────
    def _set_filter(self, key: str) -> None:
        self._current_filter = key
        for k, btn in self._filter_buttons.items():
            btn.setChecked(k == key)
        self._search_query = ""
        self._search_edit.blockSignals(True)
        self._search_edit.clear()
        self._search_edit.blockSignals(False)
        self._refresh()

    def _on_search(self, text: str) -> None:
        self._search_query = text.strip()
        for k, btn in self._filter_buttons.items():
            btn.setChecked(not self._search_query and k == self._current_filter)
        self._refresh()

    def _on_category_changed(self, text: str) -> None:
        self._category = "" if text == "All Categories" else text
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
                    popup = ReminderPopup(r.title, prefs.fmt_time(r.remind_at), self)
                    popup.show()
                except Exception:
                    pass
            if "Sound" in (r.notification_type or ""):
                try:
                    from app.services.sound_service import SoundService
                    sound_service = SoundService()
                    sound_service.play_sound("Default", repeat=3)
                except Exception:
                    # Fallback: beep 3 times
                    import time
                    for _ in range(3):
                        QApplication.beep()
                        time.sleep(0.3)
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

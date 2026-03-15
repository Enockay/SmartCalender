from __future__ import annotations

from datetime import datetime, date
from pathlib import Path

from PySide6.QtCore import QDate, QTime, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
    QFrame,
    QScrollArea,
)

from app.services.reminder_service import (
    ReminderService,
    ReminderData,
    CATEGORIES,
    PRIORITIES,
    REPEAT_TYPES,
    NOTIFICATION_TYPES,
    ADVANCE_OPTIONS,
)


class ReminderFormPanel(QWidget):
    """Inline create / edit reminder form that lives inside the container."""

    saved = Signal()       # emitted after successful save
    cancelled = Signal()   # emitted when user clicks Cancel / Back

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReminderFormPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._service = ReminderService()
        self._reminder: ReminderData | None = None
        self._build_ui()
        self._load_qss()

    # ── public API ────────────────────────────────────────────
    def set_reminder(self, reminder: ReminderData | None, default_date: date | None = None) -> None:
        """Call before showing.  Pass None for a new reminder."""
        self._reminder = reminder
        self._header_title.setText("Edit Reminder" if reminder else "New Reminder")
        self._save_btn.setText("Save Reminder" if reminder else "Create Reminder")
        self._reset_fields(default_date or date.today())
        if reminder:
            self._populate(reminder)

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header with back arrow
        header = QWidget(self)
        header.setObjectName("ReminderDialogHeader")
        header.setFixedHeight(56)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 0, 20, 0)

        back_btn = QPushButton("←  Back", header)
        back_btn.setObjectName("ReminderBackBtn")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.cancelled.emit)
        h_lay.addWidget(back_btn)

        h_lay.addSpacing(12)

        self._header_title = QLabel("New Reminder", header)
        self._header_title.setObjectName("ReminderDialogTitle")
        _tfont = QFont("Helvetica Neue", 16, QFont.Bold)
        _tfont.setFamilies(["Helvetica Neue", "Segoe UI", "sans-serif"])
        self._header_title.setFont(_tfont)
        h_lay.addWidget(self._header_title)
        h_lay.addStretch()
        root.addWidget(header)

        # Scroll body
        scroll = QScrollArea(self)
        scroll.setObjectName("ReminderDialogScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        body = QWidget()
        body.setObjectName("ReminderDialogBody")
        form = QVBoxLayout(body)
        form.setContentsMargins(24, 18, 24, 18)
        form.setSpacing(14)

        # Title
        form.addWidget(self._section("Reminder Title"))
        self._title_edit = QLineEdit(body)
        self._title_edit.setObjectName("ReminderField")
        self._title_edit.setPlaceholderText("e.g. Submit Project Report")
        form.addWidget(self._title_edit)

        # Description
        form.addWidget(self._section("Description (optional)"))
        self._desc_edit = QTextEdit(body)
        self._desc_edit.setObjectName("ReminderFieldText")
        self._desc_edit.setPlaceholderText("Add details...")
        self._desc_edit.setFixedHeight(60)
        form.addWidget(self._desc_edit)

        # Date + Time row
        dt_row = QHBoxLayout()
        dt_row.setSpacing(12)
        dt_col1 = QVBoxLayout()
        dt_col1.addWidget(self._section("Date"))
        self._date_edit = QDateEdit(body)
        self._date_edit.setObjectName("ReminderField")
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())
        dt_col1.addWidget(self._date_edit)
        dt_col2 = QVBoxLayout()
        dt_col2.addWidget(self._section("Time"))
        self._time_edit = QTimeEdit(body)
        self._time_edit.setObjectName("ReminderField")
        self._time_edit.setDisplayFormat("hh:mm AP")
        self._time_edit.setTime(QTime(9, 0))
        dt_col2.addWidget(self._time_edit)
        dt_row.addLayout(dt_col1, 1)
        dt_row.addLayout(dt_col2, 1)
        form.addLayout(dt_row)

        # Category + Priority row
        cp_row = QHBoxLayout()
        cp_row.setSpacing(12)
        cp1 = QVBoxLayout()
        cp1.addWidget(self._section("Category"))
        self._category_combo = QComboBox(body)
        self._category_combo.setObjectName("ReminderField")
        self._category_combo.addItems(CATEGORIES)
        cp1.addWidget(self._category_combo)
        cp2 = QVBoxLayout()
        cp2.addWidget(self._section("Priority"))
        self._priority_combo = QComboBox(body)
        self._priority_combo.setObjectName("ReminderField")
        self._priority_combo.addItems(PRIORITIES)
        self._priority_combo.setCurrentText("Medium")
        cp2.addWidget(self._priority_combo)
        cp_row.addLayout(cp1, 1)
        cp_row.addLayout(cp2, 1)
        form.addLayout(cp_row)

        # Repeat
        form.addWidget(self._section("Repeat"))
        self._repeat_combo = QComboBox(body)
        self._repeat_combo.setObjectName("ReminderField")
        self._repeat_combo.addItems(REPEAT_TYPES)
        form.addWidget(self._repeat_combo)

        self._repeat_custom_edit = QLineEdit(body)
        self._repeat_custom_edit.setObjectName("ReminderField")
        self._repeat_custom_edit.setPlaceholderText("e.g. Mon,Wed,Fri")
        self._repeat_custom_edit.setVisible(False)
        form.addWidget(self._repeat_custom_edit)
        self._repeat_combo.currentTextChanged.connect(
            lambda t: self._repeat_custom_edit.setVisible(t == "Custom")
        )

        # Notification type + Advance
        na_row = QHBoxLayout()
        na_row.setSpacing(12)
        na1 = QVBoxLayout()
        na1.addWidget(self._section("Notification"))
        self._notif_combo = QComboBox(body)
        self._notif_combo.setObjectName("ReminderField")
        self._notif_combo.addItems(NOTIFICATION_TYPES)
        na1.addWidget(self._notif_combo)
        na2 = QVBoxLayout()
        na2.addWidget(self._section("Advance Notice"))
        self._advance_combo = QComboBox(body)
        self._advance_combo.setObjectName("ReminderField")
        for minutes, label in ADVANCE_OPTIONS:
            self._advance_combo.addItem(label, minutes)
        na2.addWidget(self._advance_combo)
        na_row.addLayout(na1, 1)
        na_row.addLayout(na2, 1)
        form.addLayout(na_row)

        form.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Footer buttons
        footer = QWidget(self)
        footer.setObjectName("ReminderDialogFooter")
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(20, 10, 20, 14)
        f_lay.setSpacing(10)
        f_lay.addStretch()

        cancel_btn = QPushButton("Cancel", footer)
        cancel_btn.setObjectName("ReminderCancelBtn")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.clicked.connect(self.cancelled.emit)
        f_lay.addWidget(cancel_btn)

        self._save_btn = QPushButton("Create Reminder", footer)
        self._save_btn.setObjectName("ReminderSaveBtn")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        f_lay.addWidget(self._save_btn)

        root.addWidget(footer)

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("ReminderSectionLabel")
        return lbl

    # ── Reset / Populate ──────────────────────────────────────
    def _reset_fields(self, default_date: date) -> None:
        self._title_edit.clear()
        self._title_edit.setStyleSheet("")
        self._desc_edit.clear()
        self._date_edit.setDate(QDate(default_date.year, default_date.month, default_date.day))
        self._time_edit.setTime(QTime(9, 0))
        self._category_combo.setCurrentIndex(0)
        self._priority_combo.setCurrentText("Medium")
        self._repeat_combo.setCurrentIndex(0)
        self._repeat_custom_edit.clear()
        self._repeat_custom_edit.setVisible(False)
        self._notif_combo.setCurrentIndex(0)
        self._advance_combo.setCurrentIndex(0)

    def _populate(self, r: ReminderData) -> None:
        self._title_edit.setText(r.title)
        self._desc_edit.setPlainText(r.description)
        self._date_edit.setDate(QDate(r.remind_at.year, r.remind_at.month, r.remind_at.day))
        self._time_edit.setTime(QTime(r.remind_at.hour, r.remind_at.minute))
        idx = self._category_combo.findText(r.category)
        if idx >= 0:
            self._category_combo.setCurrentIndex(idx)
        idx = self._priority_combo.findText(r.priority)
        if idx >= 0:
            self._priority_combo.setCurrentIndex(idx)
        idx = self._repeat_combo.findText(r.repeat_type)
        if idx >= 0:
            self._repeat_combo.setCurrentIndex(idx)
        if r.repeat_type == "Custom":
            self._repeat_custom_edit.setVisible(True)
            self._repeat_custom_edit.setText(r.repeat_custom)
        idx = self._notif_combo.findText(r.notification_type)
        if idx >= 0:
            self._notif_combo.setCurrentIndex(idx)
        for i in range(self._advance_combo.count()):
            if self._advance_combo.itemData(i) == r.advance_minutes:
                self._advance_combo.setCurrentIndex(i)
                break

    # ── Save ──────────────────────────────────────────────────
    def _on_save(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            self._title_edit.setFocus()
            self._title_edit.setStyleSheet("border: 2px solid #EF4444;")
            QTimer.singleShot(2000, lambda: self._title_edit.setStyleSheet(""))
            return

        qd = self._date_edit.date()
        qt = self._time_edit.time()
        remind_at = datetime(qd.year(), qd.month(), qd.day(), qt.hour(), qt.minute())

        kwargs = dict(
            title=title,
            remind_at=remind_at,
            description=self._desc_edit.toPlainText().strip(),
            category=self._category_combo.currentText(),
            priority=self._priority_combo.currentText(),
            repeat_type=self._repeat_combo.currentText(),
            repeat_custom=self._repeat_custom_edit.text().strip() if self._repeat_combo.currentText() == "Custom" else "",
            notification_type=self._notif_combo.currentText(),
            advance_minutes=self._advance_combo.currentData() or 0,
        )

        if self._reminder:
            self._service.update_reminder(self._reminder.id, **kwargs)
        else:
            self._service.create_reminder(**kwargs)

        self.saved.emit()

    # ── QSS ───────────────────────────────────────────────────
    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "reminder_dialog.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

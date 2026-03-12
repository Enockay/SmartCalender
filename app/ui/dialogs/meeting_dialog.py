from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

class MeetingDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Match Outlook-style caption
        self.setWindowTitle("New Meeting")
        self.setObjectName("MeetingDialogRoot")
        # Fixed, compact size similar to the reference dialog
        self.setFixedSize(500, 500)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._build_ui()
        self._load_qss()

    def _build_ui(self) -> None:
        self._title_edit = QLineEdit(self)
        self._title_edit.setPlaceholderText("Enter meeting title")
        self._title_error = QLabel("", self)
        self._title_error.setObjectName("FieldErrorLabel")
        self._title_error.setVisible(False)
        self._title_edit.textChanged.connect(self._clear_title_error)

        self._date_edit = QDateEdit(self)
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate.currentDate())

        self._time_edit = QTimeEdit(self)
        # Default to the current system time and use a clear 24h display
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setTime(QTime.currentTime())

        # Duration: numeric value + unit (minutes or hours)
        self._duration_spin = QSpinBox(self)
        self._duration_spin.setRange(1, 1440)
        self._duration_spin.setValue(60)
        self._duration_spin.setObjectName("DurationSpin")

        self._duration_unit = QComboBox(self)
        self._duration_unit.addItems(["minutes", "hours"])
        self._duration_unit.setCurrentIndex(0)
        self._duration_unit.setObjectName("DurationUnit")

        self._duration_error = QLabel("", self)
        self._duration_error.setObjectName("FieldErrorLabel")
        self._duration_error.setVisible(False)
        self._duration_spin.valueChanged.connect(
            lambda _v: self._clear_duration_error(str(_v))
        )

        self._category_combo = QComboBox(self)
        self._category_combo.addItems(["Work", "Personal", "Urgent"])

        # Meeting color gradient (stored in DB and used for rendering)
        self._color_combo = QComboBox(self)
        self._color_combo.setObjectName("MeetingColorCombo")
        self._color_combo.addItem("Blue", "linear:#2D8CFF:#1F6FF2")
        self._color_combo.addItem("Green", "linear:#22C55E:#16A34A")
        self._color_combo.addItem("Purple", "linear:#8B5CF6:#7C3AED")
        self._color_combo.addItem("Orange", "linear:#FB923C:#F97316")
        self._color_combo.addItem("Red", "linear:#F87171:#EF4444")

        self._recurrence_combo = QComboBox(self)
        self._recurrence_combo.addItems(["None", "Daily", "Weekly", "Monthly"])

        self._description_edit = QTextEdit(self)
        self._description_edit.setPlaceholderText(
            "Add notes, agenda, location, or extra meeting details..."
        )
        self._description_edit.setMinimumHeight(120)

        # Main wrapper – body area only; we rely on the native macOS titlebar
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 16)
        main_layout.setSpacing(10)

        # Form layout
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        # Wrap inputs that can show inline errors in a vertical layout
        title_field = QWidget(self)
        title_layout = QVBoxLayout(title_field)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        title_layout.addWidget(self._title_edit)
        title_layout.addWidget(self._title_error)

        duration_field = QWidget(self)
        duration_layout = QVBoxLayout(duration_field)
        duration_layout.setContentsMargins(0, 0, 0, 0)
        duration_layout.setSpacing(2)

        duration_row = QWidget(self)
        duration_row_layout = QHBoxLayout(duration_row)
        duration_row_layout.setContentsMargins(0, 0, 0, 0)
        duration_row_layout.setSpacing(6)
        duration_row_layout.addWidget(self._duration_spin, 0)
        duration_row_layout.addWidget(self._duration_unit, 0)

        duration_layout.addWidget(duration_row)
        duration_layout.addWidget(self._duration_error)

        form.addRow("Title:", title_field)
        form.addRow("Date:", self._date_edit)

        # Time field row
        form.addRow("Time:", self._time_edit)
        form.addRow("Duration:", duration_field)
        form.addRow("Category:", self._category_combo)
        form.addRow("Color:", self._color_combo)
        form.addRow("Recurrence:", self._recurrence_combo)
        form.addRow("Description:", self._description_edit)

        main_layout.addLayout(form)

        # Divider
        divider = QFrame(self)
        divider.setObjectName("DialogDivider")
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        main_layout.addWidget(divider)

        # Reminder row (simple label + existing reminder widget)
        reminder_row = QHBoxLayout()
        reminder_row.setContentsMargins(0, 0, 0, 0)
        reminder_row.setSpacing(10)

        reminder_label = QLabel("Reminder:", self)
        reminder_label.setObjectName("SectionTitle")
        reminder_row.addWidget(reminder_label)

        from app.ui.widgets.reminder_widget import ReminderWidget

        self._reminder_widget = ReminderWidget(self)
        reminder_row.addWidget(self._reminder_widget, 1)

        main_layout.addLayout(reminder_row)

        # Button box
        buttons = QDialogButtonBox(parent=self)
        buttons.setObjectName("MeetingDialogButtons")

        # Explicit "Save" and "Cancel" buttons to match the reference dialog
        from PySide6.QtWidgets import QPushButton

        save_button = QPushButton("Save", self)
        cancel_button = QPushButton("Cancel", self)
        buttons.addButton(save_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        save_button.clicked.connect(self._on_save_clicked)
        cancel_button.clicked.connect(self.reject)
        main_layout.addWidget(buttons)

    def get_data(self) -> tuple[str, datetime, int, str, str, str, str | None, int] | None:
        # Clear previous error messages
        self._title_error.setVisible(False)
        self._duration_error.setVisible(False)

        title = self._title_edit.text().strip()
        if not title:
            self._title_error.setText("Title is required.")
            self._title_error.setVisible(True)
            return None

        # Duration: convert value + unit into minutes
        duration_value = self._duration_spin.value()
        if duration_value <= 0:
            self._duration_error.setText("Duration must be greater than 0.")
            self._duration_error.setVisible(True)
            return None

        unit = self._duration_unit.currentText()
        if unit == "hours":
            duration_minutes = duration_value * 60
        else:
            duration_minutes = duration_value

        qdate = self._date_edit.date()
        qtime = self._time_edit.time()
        start = datetime(
            qdate.year(),
            qdate.month(),
            qdate.day(),
            qtime.hour(),
            qtime.minute(),
        )

        category = self._category_combo.currentText()
        color_gradient = self._color_combo.currentData()
        recurrence = self._recurrence_combo.currentText()
        description = self._description_edit.toPlainText().strip()
        # Per-meeting reminder offset in minutes from the reminder widget.
        reminder_minutes = getattr(self._reminder_widget, "reminder_minutes", lambda: 10)()

        return (
            title,
            start,
            duration_minutes,
            category,
            recurrence,
            description,
            color_gradient,
            reminder_minutes,
        )

    def _on_save_clicked(self) -> None:
        """Validate inputs before allowing the dialog to close."""
        if self.get_data() is None:
            # Validation failed; keep dialog open
            return
        self.accept()

    def _clear_title_error(self, text: str) -> None:
        if text.strip():
            self._title_error.setVisible(False)

    def _clear_duration_error(self, text: str) -> None:
        if text.strip():
            self._duration_error.setVisible(False)

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_root = root / "ui" / "resources" / "qss"

        styles: list[str] = []
        for name in (
            "meeting_dialog.qss",
            "reminder_widget.qss",
        ):
            qss_path = qss_root / name
            if qss_path.exists():
                styles.append(qss_path.read_text(encoding="utf-8"))

        if styles:
            self.setStyleSheet("\n".join(styles))
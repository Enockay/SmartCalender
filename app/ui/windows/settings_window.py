from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QDialogButtonBox,
)

from app.services.settings_service import SettingsService, ThemeName, ViewName


class SettingsWindow(QDialog):
    def __init__(self, settings: SettingsService, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("Settings")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._theme_combo = QComboBox(self)
        # Theme is fixed to Light in this version; keep combo for future use.
        self._theme_combo.addItems(["Light"])

        self._default_view_combo = QComboBox(self)
        self._default_view_combo.addItems(["Day", "Week", "Month"])

        self._reminder_spin = QSpinBox(self)
        self._reminder_spin.setRange(0, 240)
        self._reminder_spin.setSuffix(" min")

        self._notifications_checkbox = QCheckBox("Enable desktop notifications", self)

        form.addRow("Theme", self._theme_combo)
        form.addRow("Default view", self._default_view_combo)
        form.addRow("Default reminder time", self._reminder_spin)
        form.addRow("", self._notifications_checkbox)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_from_settings()

    def _load_from_settings(self) -> None:
        # Theme is always light; ensure combo reflects that.
        self._theme_combo.setCurrentIndex(0)

        view = self._settings.get_default_view()
        self._default_view_combo.setCurrentIndex(
            {"day": 0, "week": 1, "month": 2}[view]
        )

        self._reminder_spin.setValue(self._settings.get_default_reminder_minutes())
        self._notifications_checkbox.setChecked(
            self._settings.get_notifications_enabled()
        )

    def apply_changes(self) -> None:
        # Theme is fixed to light; styling is applied per-window now.
        theme: ThemeName = "light"
        self._settings.set_theme(theme)

        view_map = {0: "day", 1: "week", 2: "month"}
        view: ViewName = view_map[self._default_view_combo.currentIndex()]  # type: ignore[assignment]
        self._settings.set_default_view(view)

        self._settings.set_default_reminder_minutes(self._reminder_spin.value())
        self._settings.set_notifications_enabled(self._notifications_checkbox.isChecked())

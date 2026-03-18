from __future__ import annotations

import getpass
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTime, Signal, QTimer, QUrl
from PySide6.QtGui import QFont, QColor, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QLabel,
    QWidget,
    QTabWidget,
    QFrame,
    QRadioButton,
    QButtonGroup,
    QTimeEdit,
    QMessageBox,
    QFileDialog,
    QSizePolicy,
    QScrollArea,
    QGraphicsDropShadowEffect,
)

from app.core.logger import get_logger
from app.core.app_config import get_base_dir
from app.services.settings_service import SettingsService, ThemeName, ViewName
from app.services.sound_service import SoundService
from app.database.db_manager import DatabaseManager
from app.database.schema import User, Meeting, Task
from sqlalchemy import select, func


class SettingsWindow(QWidget):
    """Professional settings widget embedded in the main content stack."""

    # Emitted when user saves – parent can react (e.g. apply theme)
    settingsSaved = Signal()
    # Emitted when user clicks renew so the main window can open websocket, etc.
    renewSubscriptionRequested = Signal()

    def __init__(self, settings: SettingsService, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._db = DatabaseManager()
        self._logger = get_logger(__name__)
        self.setObjectName("SettingsDialog")
        
        # Initialize sound service early so it's available when building tabs
        self._sound_service = SoundService()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar (cool gradient matching other views) ──
        header = QWidget(self)
        header.setObjectName("SettingsHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 12, 24, 12)
        h_lay.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("⚙  Settings", header)
        title.setObjectName("SettingsTitle")
        title_col.addWidget(title)
        subtitle = QLabel("Manage your preferences, account & data", header)
        subtitle.setObjectName("SettingsSubtitle")
        title_col.addWidget(subtitle)
        h_lay.addLayout(title_col)
        h_lay.addStretch()

        # Version badge
        ver = QLabel("v1.0", header)
        ver.setObjectName("SettingsVersionBadge")
        ver.setAlignment(Qt.AlignCenter)
        h_lay.addWidget(ver)

        root.addWidget(header)

        # ── Tab widget ──
        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("SettingsTabs")
        self._tabs.setDocumentMode(True)

        self._tabs.addTab(self._build_general_tab(), " ⚡ General")
        self._tabs.addTab(self._build_account_tab(), " 👤 Account")
        self._tabs.addTab(self._build_notifications_tab(), " 🔔 Alerts")
        self._tabs.addTab(self._build_backup_tab(), " 💾 Backup")
        self._tabs.addTab(self._build_about_tab(), " ℹ About")
        self._tabs.tabBar().setExpanding(True)

        root.addWidget(self._tabs, 1)
        
        # Populate sound combo after tabs are created (delayed to ensure _sound_combo exists)
        QTimer.singleShot(200, self._populate_sound_combo)

        # ── Bottom bar ──
        bottom = QWidget(self)
        bottom.setObjectName("SettingsBottomBar")
        b_lay = QHBoxLayout(bottom)
        b_lay.setContentsMargins(20, 12, 20, 12)
        b_lay.setSpacing(12)

        self._reset_btn = QPushButton("↺  Reset to Default", bottom)
        self._reset_btn.setObjectName("SettingsResetBtn")
        self._reset_btn.setCursor(Qt.PointingHandCursor)
        self._reset_btn.clicked.connect(self._on_reset)
        b_lay.addWidget(self._reset_btn)

        b_lay.addStretch()

        # Status label for feedback
        self._save_status = QLabel("", bottom)
        self._save_status.setObjectName("SettingsSaveStatus")
        b_lay.addWidget(self._save_status)

        self._save_btn = QPushButton("  ✓  Save Changes  ", bottom)
        self._save_btn.setObjectName("SettingsSaveBtn")
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        b_lay.addWidget(self._save_btn)

        root.addWidget(bottom)

        self._load_qss()
        self._load_from_settings()

    # =====================================================================
    #  TAB BUILDERS
    # =====================================================================

    def _build_general_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("SettingsPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(18)

        # ── Theme ──
        theme_card = self._card("🎨  Appearance", "Choose your preferred theme")
        card_lay = theme_card.layout()

        theme_row = QHBoxLayout()
        theme_row.setSpacing(0)

        self._theme_group = QButtonGroup(self)
        self._dark_btn = QPushButton("  🌙  Dark  ", page)
        self._dark_btn.setObjectName("ThemeToggleDark")
        self._dark_btn.setCheckable(True)
        self._dark_btn.setCursor(Qt.PointingHandCursor)
        self._dark_btn.setFixedHeight(36)

        self._light_btn = QPushButton("  ☀  Light  ", page)
        self._light_btn.setObjectName("ThemeToggleLight")
        self._light_btn.setCheckable(True)
        self._light_btn.setCursor(Qt.PointingHandCursor)
        self._light_btn.setFixedHeight(36)

        self._theme_group.addButton(self._dark_btn, 0)
        self._theme_group.addButton(self._light_btn, 1)

        theme_row.addWidget(self._dark_btn)
        theme_row.addWidget(self._light_btn)
        theme_row.addStretch()
        card_lay.addLayout(theme_row)
        lay.addWidget(theme_card)

        # ── Language ──
        lang_card = self._card("🌐  Language", "Select display language")
        card_lay = lang_card.layout()

        self._lang_combo = QComboBox(page)
        self._lang_combo.setObjectName("SettingsCombo")
        self._lang_combo.addItems(["English", "Spanish", "French", "German", "Chinese", "Arabic", "Swahili"])
        self._lang_combo.setFixedHeight(36)
        card_lay.addWidget(self._lang_combo)
        lay.addWidget(lang_card)

        # ── Default category ──
        cat_card = self._card("📂  Default Category", "Category used for new events/tasks")
        card_lay = cat_card.layout()

        self._cat_combo = QComboBox(page)
        self._cat_combo.setObjectName("SettingsCombo")
        self._cat_combo.addItems(["Work", "Personal", "Meetings", "Finance", "Study", "Health", "Travel"])
        self._cat_combo.setFixedHeight(36)
        card_lay.addWidget(self._cat_combo)
        lay.addWidget(cat_card)

        # ── Default reminder frequency ──
        freq_card = self._card("⏰  Default Reminder Frequency", "How often to remind by default")
        card_lay = freq_card.layout()

        freq_row = QHBoxLayout()
        freq_row.setSpacing(12)

        self._freq_group = QButtonGroup(self)
        for i, (text, btn_id) in enumerate([("Daily", 0), ("Weekly", 1), ("Monthly", 2)]):
            rb = QRadioButton(text, page)
            rb.setObjectName("SettingsRadio")
            rb.setCursor(Qt.PointingHandCursor)
            self._freq_group.addButton(rb, btn_id)
            freq_row.addWidget(rb)
            if i == 0:
                self._freq_daily = rb
            elif i == 1:
                self._freq_weekly = rb
            else:
                self._freq_monthly = rb
        freq_row.addStretch()
        card_lay.addLayout(freq_row)
        lay.addWidget(freq_card)

        # ── Default view ──
        view_card = self._card("📅  Default View", "Which view opens when you launch the app")
        card_lay = view_card.layout()

        self._view_combo = QComboBox(page)
        self._view_combo.setObjectName("SettingsCombo")
        self._view_combo.addItems(["Day", "Week", "Month", "Year"])
        self._view_combo.setFixedHeight(36)
        card_lay.addWidget(self._view_combo)
        lay.addWidget(view_card)

        # ── Weather city ──
        weather_card = self._card("🌤  Weather City", "Auto-detect from IP if left blank")
        card_lay = weather_card.layout()

        self._weather_edit = QLineEdit(page)
        self._weather_edit.setObjectName("SettingsInput")
        self._weather_edit.setPlaceholderText("e.g. Nairobi, London, New York…")
        self._weather_edit.setFixedHeight(36)
        card_lay.addWidget(self._weather_edit)
        lay.addWidget(weather_card)

        lay.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_account_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("SettingsPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(18)

        # ── Profile card ──
        profile_card = QFrame(page)
        profile_card.setObjectName("SettingsCard")
        pc_lay = QVBoxLayout(profile_card)
        pc_lay.setContentsMargins(20, 20, 20, 20)
        pc_lay.setSpacing(14)

        # Avatar + name row
        profile_row = QHBoxLayout()
        profile_row.setSpacing(16)

        try:
            sys_user = getpass.getuser()
        except Exception:
            sys_user = os.environ.get("USER", "User")
        display = sys_user.replace("_", " ").replace("-", " ").title()
        initial = display[0].upper() if display else "U"

        avatar = QLabel(initial, page)
        avatar.setObjectName("AccountAvatar")
        avatar.setFixedSize(56, 56)
        avatar.setAlignment(Qt.AlignCenter)
        profile_row.addWidget(avatar)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name_lbl = QLabel(display, page)
        name_lbl.setObjectName("AccountName")
        name_col.addWidget(name_lbl)
        status_lbl = QLabel("● Active", page)
        status_lbl.setObjectName("AccountStatus")
        name_col.addWidget(status_lbl)

        # Stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._stat_tasks = QLabel("0 tasks", page)
        self._stat_tasks.setObjectName("AccountStat")
        stats_row.addWidget(self._stat_tasks)
        sep = QLabel("•")
        sep.setObjectName("AccountStatSep")
        stats_row.addWidget(sep)
        self._stat_meetings = QLabel("0 meetings", page)
        self._stat_meetings.setObjectName("AccountStat")
        stats_row.addWidget(self._stat_meetings)
        stats_row.addStretch()
        name_col.addLayout(stats_row)

        profile_row.addLayout(name_col, 1)
        pc_lay.addLayout(profile_row)

        pc_lay.addWidget(self._separator())

        # Username
        form_row = QHBoxLayout()
        form_row.setSpacing(16)
        un_col = QVBoxLayout()
        un_col.setSpacing(4)
        un_col.addWidget(self._field_label("Username"))
        self._username_edit = QLineEdit(page)
        self._username_edit.setObjectName("SettingsInput")
        self._username_edit.setFixedHeight(36)
        un_col.addWidget(self._username_edit)
        form_row.addLayout(un_col, 1)

        em_col = QVBoxLayout()
        em_col.setSpacing(4)
        em_col.addWidget(self._field_label("Email"))
        self._email_edit = QLineEdit(page)
        self._email_edit.setObjectName("SettingsInput")
        self._email_edit.setPlaceholderText("your@email.com")
        self._email_edit.setFixedHeight(36)
        em_col.addWidget(self._email_edit)
        form_row.addLayout(em_col, 1)
        pc_lay.addLayout(form_row)

        # Subscription row
        sub_row = QHBoxLayout()
        sub_row.setSpacing(10)
        sub_row.addWidget(self._field_label("Subscription"))
        sub_row.addStretch()
        self._sub_badge = QLabel("Free", page)
        self._sub_badge.setObjectName("SubscriptionBadge")
        self._sub_badge.setAlignment(Qt.AlignCenter)
        sub_row.addWidget(self._sub_badge)

        # Renew subscription button -> opens browser with user_id + token
        self._renew_btn = QPushButton("↻  Renew Subscription", page)
        self._renew_btn.setObjectName("SubscriptionRenewButton")
        self._renew_btn.setCursor(Qt.PointingHandCursor)
        self._renew_btn.clicked.connect(self._on_renew_subscription)
        sub_row.addWidget(self._renew_btn)

        pc_lay.addLayout(sub_row)

        # Subscription details (expiry, status) under the row
        self._sub_detail_label = QLabel("", page)
        self._sub_detail_label.setObjectName("SubscriptionDetailLabel")
        pc_lay.addWidget(self._sub_detail_label)

        # Contact support
        self._support_label = QLabel(
            'Need help? Contact <a href="mailto:support@desktophab.com">support@desktophab.com</a>',
            page,
        )
        self._support_label.setObjectName("AccountSupportLabel")
        self._support_label.setOpenExternalLinks(True)
        pc_lay.addWidget(self._support_label)

        lay.addWidget(profile_card)

        # ── Danger zone ──
        danger_card = QFrame(page)
        danger_card.setObjectName("DangerCard")
        dc_lay = QVBoxLayout(danger_card)
        dc_lay.setContentsMargins(20, 16, 20, 16)
        dc_lay.setSpacing(12)

        danger_header = QHBoxLayout()
        danger_header.setSpacing(8)
        danger_icon = QLabel("⚠", page)
        danger_icon.setObjectName("DangerIcon")
        danger_header.addWidget(danger_icon)
        danger_lbl = QLabel("Danger Zone", page)
        danger_lbl.setObjectName("DangerLabel")
        danger_header.addWidget(danger_lbl)
        danger_header.addStretch()
        dc_lay.addLayout(danger_header)

        danger_desc = QLabel("These actions are irreversible. Proceed with caution.", page)
        danger_desc.setObjectName("DangerDesc")
        dc_lay.addWidget(danger_desc)

        danger_row = QHBoxLayout()
        danger_row.setSpacing(12)

        self._logout_btn = QPushButton("🚪  Log Out", page)
        self._logout_btn.setObjectName("DangerButton")
        self._logout_btn.setCursor(Qt.PointingHandCursor)
        self._logout_btn.clicked.connect(self._on_logout)
        danger_row.addWidget(self._logout_btn)

        self._delete_btn = QPushButton("🗑  Delete All Data", page)
        self._delete_btn.setObjectName("DangerButtonRed")
        self._delete_btn.setCursor(Qt.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete_all_data)
        danger_row.addWidget(self._delete_btn)
        danger_row.addStretch()

        dc_lay.addLayout(danger_row)
        lay.addWidget(danger_card)

        lay.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_notifications_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("SettingsPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(18)

        # ── Desktop notifications ──
        notif_card = self._card("🖥  Desktop Notifications", "Get alerts for upcoming events")
        card_lay = notif_card.layout()
        self._notif_check = QCheckBox("Enable desktop notifications", page)
        self._notif_check.setObjectName("SettingsCheckbox")
        self._notif_check.setCursor(Qt.PointingHandCursor)
        card_lay.addWidget(self._notif_check)
        lay.addWidget(notif_card)

        # ── Email alerts ──
        email_card = self._card("📧  Email Alerts", "Receive email reminders before events")
        card_lay = email_card.layout()
        self._email_alerts_check = QCheckBox("Send email reminders before events", page)
        self._email_alerts_check.setObjectName("SettingsCheckbox")
        self._email_alerts_check.setCursor(Qt.PointingHandCursor)
        card_lay.addWidget(self._email_alerts_check)
        lay.addWidget(email_card)

        # ── Sound alerts ──
        sound_card = self._card("🔊  Sound Alerts", "Play a sound when notifications fire")
        card_lay = sound_card.layout()
        self._sound_check = QCheckBox("Play sound for notifications", page)
        self._sound_check.setObjectName("SettingsCheckbox")
        self._sound_check.setCursor(Qt.PointingHandCursor)
        card_lay.addWidget(self._sound_check)
        
        # Sound selection dropdown
        sound_row = QHBoxLayout()
        sound_row.setSpacing(10)
        sound_label = QLabel("Reminder sound:", page)
        sound_label.setObjectName("SettingsLabel")
        sound_row.addWidget(sound_label)
        
        self._sound_combo = QComboBox(page)
        self._sound_combo.setObjectName("SettingsCombo")
        self._sound_combo.setFixedHeight(36)
        self._sound_combo.setMinimumWidth(200)
        self._sound_combo.setCursor(Qt.PointingHandCursor)
        
        sound_row.addWidget(self._sound_combo)
        
        # Test sound button
        test_sound_btn = QPushButton("▶ Test", page)
        test_sound_btn.setObjectName("SettingsTestSoundButton")
        test_sound_btn.setFixedHeight(36)
        test_sound_btn.setFixedWidth(100)
        test_sound_btn.setCursor(Qt.PointingHandCursor)
        test_sound_btn.clicked.connect(self._on_test_sound)
        sound_row.addWidget(test_sound_btn)
        
        sound_row.addStretch()
        card_lay.addLayout(sound_row)
        
        lay.addWidget(sound_card)

        # ── Quiet Hours ──
        quiet_card = self._card("🌙  Quiet Hours", "Suppress all notifications during these hours")
        card_lay = quiet_card.layout()

        quiet_row = QHBoxLayout()
        quiet_row.setSpacing(12)

        quiet_row.addWidget(self._field_label("From"))
        self._quiet_start = QTimeEdit(page)
        self._quiet_start.setObjectName("SettingsTimeEdit")
        self._quiet_start.setDisplayFormat("HH:mm")
        self._quiet_start.setFixedHeight(36)
        self._quiet_start.setFixedWidth(100)
        quiet_row.addWidget(self._quiet_start)

        quiet_row.addWidget(self._field_label("To"))
        self._quiet_end = QTimeEdit(page)
        self._quiet_end.setObjectName("SettingsTimeEdit")
        self._quiet_end.setDisplayFormat("HH:mm")
        self._quiet_end.setFixedHeight(36)
        self._quiet_end.setFixedWidth(100)
        quiet_row.addWidget(self._quiet_end)
        quiet_row.addStretch()

        card_lay.addLayout(quiet_row)
        lay.addWidget(quiet_card)

        # ── Reminder Lead Time ──
        reminder_card = self._card("⏱  Reminder Lead Time", "How many minutes before an event to remind")
        card_lay = reminder_card.layout()

        reminder_row = QHBoxLayout()
        reminder_row.setSpacing(10)
        self._reminder_spin = QSpinBox(page)
        self._reminder_spin.setObjectName("SettingsSpin")
        self._reminder_spin.setRange(0, 240)
        self._reminder_spin.setSuffix("  min")
        self._reminder_spin.setFixedHeight(36)
        self._reminder_spin.setFixedWidth(130)
        reminder_row.addWidget(self._reminder_spin)
        reminder_row.addWidget(self._field_label("before each event"))
        reminder_row.addStretch()
        card_lay.addLayout(reminder_row)
        lay.addWidget(reminder_card)

        # Info
        info = self._info_panel(
            "🔔",
            "Notifications are delivered via your OS notification system. "
            "Email alerts require a valid email in your Account settings."
        )
        lay.addWidget(info)

        lay.addStretch()
        scroll.setWidget(page)
        return scroll

    def _build_backup_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("SettingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("SettingsPage")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(28, 20, 28, 20)
        lay.setSpacing(18)

        # ── Stats overview ──
        stats_card = QFrame(page)
        stats_card.setObjectName("SettingsCard")
        sc_lay = QHBoxLayout(stats_card)
        sc_lay.setContentsMargins(20, 16, 20, 16)
        sc_lay.setSpacing(20)

        self._db_size_label = QLabel("📊  Database: calculating…", page)
        self._db_size_label.setObjectName("BackupStatLabel")
        sc_lay.addWidget(self._db_size_label)
        sc_lay.addStretch()
        self._last_backup_label = QLabel("Last backup: Never", page)
        self._last_backup_label.setObjectName("BackupStatLabel")
        sc_lay.addWidget(self._last_backup_label)
        lay.addWidget(stats_card)

        # ── Manual Backup ──
        backup_card = self._card("📦  Manual Backup", "Create a snapshot of your database right now")
        card_lay = backup_card.layout()
        backup_row = QHBoxLayout()
        backup_row.setSpacing(12)
        self._backup_now_btn = QPushButton("  📦  Backup Now  ", page)
        self._backup_now_btn.setObjectName("SettingsActionBtn")
        self._backup_now_btn.setCursor(Qt.PointingHandCursor)
        self._backup_now_btn.setFixedHeight(38)
        self._backup_now_btn.clicked.connect(self._on_backup_now)
        backup_row.addWidget(self._backup_now_btn)
        backup_row.addStretch()
        card_lay.addLayout(backup_row)
        lay.addWidget(backup_card)

        # ── Auto backup ──
        auto_card = self._card("🔄  Automatic Backup", "Schedule recurring backups")
        card_lay = auto_card.layout()
        self._auto_backup_check = QCheckBox("Enable automatic backups", page)
        self._auto_backup_check.setObjectName("SettingsCheckbox")
        self._auto_backup_check.setCursor(Qt.PointingHandCursor)
        card_lay.addWidget(self._auto_backup_check)

        sched_row = QHBoxLayout()
        sched_row.setSpacing(12)
        sched_row.addWidget(self._field_label("Schedule:"))
        self._backup_sched_combo = QComboBox(page)
        self._backup_sched_combo.setObjectName("SettingsCombo")
        self._backup_sched_combo.addItems(["Daily", "Weekly", "Monthly"])
        self._backup_sched_combo.setFixedHeight(36)
        self._backup_sched_combo.setFixedWidth(160)
        sched_row.addWidget(self._backup_sched_combo)
        sched_row.addStretch()
        card_lay.addLayout(sched_row)
        lay.addWidget(auto_card)

        # ── Restore ──
        restore_card = self._card("🔙  Restore Backup", "Load a previously saved backup file")
        card_lay = restore_card.layout()
        restore_row = QHBoxLayout()
        restore_row.setSpacing(12)
        self._restore_btn = QPushButton("  📂  Restore from File  ", page)
        self._restore_btn.setObjectName("SettingsActionBtn")
        self._restore_btn.setCursor(Qt.PointingHandCursor)
        self._restore_btn.setFixedHeight(38)
        self._restore_btn.clicked.connect(self._on_restore)
        restore_row.addWidget(self._restore_btn)
        restore_row.addStretch()
        card_lay.addLayout(restore_row)
        lay.addWidget(restore_card)

        # ── Export ──
        export_card = self._card("📤  Export Data", "Export all meetings, tasks & settings as JSON")
        card_lay = export_card.layout()
        export_row = QHBoxLayout()
        export_row.setSpacing(12)
        self._export_btn = QPushButton("  📤  Export JSON  ", page)
        self._export_btn.setObjectName("SettingsActionBtn")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.setFixedHeight(38)
        self._export_btn.clicked.connect(self._on_export)
        export_row.addWidget(self._export_btn)
        export_row.addStretch()
        card_lay.addLayout(export_row)
        lay.addWidget(export_card)

        # Info
        info = self._info_panel(
            "💾",
            "Backups are full copies of your database file. "
            "Export creates a human-readable JSON with all your data."
        )
        lay.addWidget(info)

        lay.addStretch()
        scroll.setWidget(page)
        return scroll

    # =====================================================================
    #  WIDGET HELPERS
    # =====================================================================

    def _card(self, title: str, description: str) -> QFrame:
        """Create a styled card with title and description."""
        card = QFrame()
        card.setObjectName("SettingsCard")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(20, 16, 20, 16)
        c_lay.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        t = QLabel(title)
        t.setObjectName("SettingsCardTitle")
        header.addWidget(t)
        header.addStretch()
        c_lay.addLayout(header)

        d = QLabel(description)
        d.setObjectName("SettingsCardDesc")
        d.setWordWrap(True)
        c_lay.addWidget(d)

        return card

    def _info_panel(self, icon: str, text: str) -> QFrame:
        """Create an info panel with icon and text."""
        info = QFrame()
        info.setObjectName("SettingsInfoPanel")
        i_lay = QHBoxLayout(info)
        i_lay.setContentsMargins(14, 12, 14, 12)
        i_lay.setSpacing(12)
        i_icon = QLabel(icon, info)
        i_icon.setFixedWidth(24)
        i_lay.addWidget(i_icon)
        label = QLabel(text, info)
        label.setObjectName("SettingsInfoText")
        label.setWordWrap(True)
        i_lay.addWidget(label, 1)
        return info

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SettingsSectionLabel")
        return lbl

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SettingsFieldLabel")
        return lbl

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("SettingsSep")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        return sep

    # Map QMessageBox icons to emoji prefixes
    _ICON_EMOJI = {
        QMessageBox.Information: "✅",
        QMessageBox.Warning: "⚠️",
        QMessageBox.Critical: "❌",
        QMessageBox.Question: "❓",
    }

    def _styled_msg(
        self,
        icon: QMessageBox.Icon,
        title: str,
        text: str,
        buttons=QMessageBox.Ok,
    ) -> int:
        """Show a styled QMessageBox with the app's dark sidebar theme."""
        box = QMessageBox(self)
        # Completely suppress native icon (macOS shows it even with NoIcon)
        box.setIcon(QMessageBox.NoIcon)
        box.setIconPixmap(QPixmap())
        emoji = self._ICON_EMOJI.get(icon, "")
        box.setWindowTitle(title)
        box.setText(f"{emoji}  {text}" if emoji else text)
        box.setStandardButtons(buttons)

        box.setStyleSheet("""
            QMessageBox {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0D2147, stop:0.5 #132D5B, stop:1 #1A3A6E);
                border: 1px solid rgba(100, 160, 255, 0.2);
            }
            QMessageBox QLabel {
                color: #E8EDF5;
                font-size: 14px;
                font-weight: 500;
                font-family: "Segoe UI", "Helvetica Neue", sans-serif;
                padding: 10px 6px;
                background: transparent;
            }
            QMessageBox QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #60A5FA);
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 700;
                min-width: 72px;
                min-height: 32px;
            }
            QMessageBox QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #3B82F6);
            }
            QMessageBox QPushButton:pressed {
                background: #1D4ED8;
            }
        """)

        # Style the "No" / secondary button differently
        if buttons & QMessageBox.No:
            no_btn = box.button(QMessageBox.No)
            if no_btn:
                no_btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(255, 255, 255, 0.08);
                        color: #CBD5E1;
                        border: 1px solid rgba(255, 255, 255, 0.15);
                        border-radius: 8px;
                        padding: 8px 24px;
                        font-size: 13px;
                        font-weight: 600;
                        min-width: 72px;
                        min-height: 32px;
                    }
                    QPushButton:hover {
                        background: rgba(255, 255, 255, 0.15);
                        color: #FFFFFF;
                        border: 1px solid rgba(255, 255, 255, 0.25);
                    }
                """)

        return box.exec()

    # =====================================================================
    #  LOAD / SAVE
    # =====================================================================

    def _load_from_settings(self) -> None:
        s = self._settings

        # General
        theme = s.get_theme()
        if theme == "dark":
            self._dark_btn.setChecked(True)
        else:
            self._light_btn.setChecked(True)

        lang = s.get_language()
        idx = self._lang_combo.findText(lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        cat = s.get_default_category()
        idx = self._cat_combo.findText(cat)
        if idx >= 0:
            self._cat_combo.setCurrentIndex(idx)

        freq = s.get_reminder_frequency()
        freq_map = {"Daily": self._freq_daily, "Weekly": self._freq_weekly, "Monthly": self._freq_monthly}
        btn = freq_map.get(freq, self._freq_daily)
        btn.setChecked(True)

        view = s.get_default_view()
        view_map = {"day": 0, "week": 1, "month": 2, "year": 3}
        self._view_combo.setCurrentIndex(view_map.get(view, 0))

        self._weather_edit.setText(s.get_weather_city())

        # Account
        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User)
                    .where(User.is_logged_in == True)
                    .order_by(User.last_login_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if user:
                    # Header name + avatar should reflect logged-in user
                    name_lbl = self.findChild(QLabel, "AccountName")
                    avatar_lbl = self.findChild(QLabel, "AccountAvatar")
                    display_name = user.name or "User"
                    if name_lbl:
                        name_lbl.setText(display_name)
                    if avatar_lbl and display_name:
                        avatar_lbl.setText(display_name[0].upper())

                    # Username / email fields
                    self._username_edit.setText(user.name or "")
                    self._email_edit.setText(user.email or "")

                    # Subscription tier badge
                    self._sub_badge.setText(
                        (user.subscription_tier or "free").capitalize()
                    )
                    # Subscription details: status + expiry date if present
                    details = []
                    if user.subscription_status:
                        details.append(user.subscription_status.capitalize())
                    if user.subscription_expires_at:
                        details.append(
                            "ends "
                            + user.subscription_expires_at.strftime("%b %d, %Y")
                        )
                    self._sub_detail_label.setText(" · ".join(details))
                # Stats
                task_count = session.execute(
                    select(func.count(Task.id))
                ).scalar() or 0
                meeting_count = session.execute(
                    select(func.count(Meeting.id))
                ).scalar() or 0
                self._stat_tasks.setText(f"{task_count} tasks")
                self._stat_meetings.setText(f"{meeting_count} meetings")
        except Exception:
            pass

        # Notifications
        self._notif_check.setChecked(s.get_notifications_enabled())
        self._email_alerts_check.setChecked(s.get_email_alerts())
        self._sound_check.setChecked(s.get_sound_alerts())
        # Reminder sound
        if hasattr(self, '_sound_combo'):
            selected_sound = s.get_reminder_sound()
            index = self._sound_combo.findText(selected_sound, Qt.MatchFixedString)
            if index >= 0:
                self._sound_combo.setCurrentIndex(index)
            else:
                # Try to find by removing emoji prefix
                for i in range(self._sound_combo.count()):
                    item_text = self._sound_combo.itemText(i)
                    if item_text.replace("🎵 ", "") == selected_sound or item_text == selected_sound:
                        self._sound_combo.setCurrentIndex(i)
                        break
                else:
                    self._sound_combo.setCurrentIndex(0)  # Default to first item
        self._reminder_spin.setValue(s.get_default_reminder_minutes())

        qs = s.get_quiet_hours_start().split(":")
        if len(qs) == 2:
            self._quiet_start.setTime(QTime(int(qs[0]), int(qs[1])))
        qe = s.get_quiet_hours_end().split(":")
        if len(qe) == 2:
            self._quiet_end.setTime(QTime(int(qe[0]), int(qe[1])))

        # Backup
        self._auto_backup_check.setChecked(s.get_auto_backup())
        sched = s.get_backup_schedule()
        idx = self._backup_sched_combo.findText(sched)
        if idx >= 0:
            self._backup_sched_combo.setCurrentIndex(idx)

        # Database size
        self._update_db_stats()

    def refresh_account(self) -> None:
        """Public hook for parent window to refresh account/subscription UI."""
        self._load_from_settings()

    def _update_db_stats(self) -> None:
        """Calculate and display database stats."""
        try:
            full_path = Path(self._db.db_path)
            if full_path.exists():
                size_bytes = full_path.stat().st_size
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                self._db_size_label.setText(f"📊  Database size: {size_str}")
            else:
                self._db_size_label.setText("📊  Database: not found")
        except Exception:
            self._db_size_label.setText("📊  Database: unknown")

    # =====================================================================
    #  SUBSCRIPTION ACTIONS
    # =====================================================================

    def _on_renew_subscription(self) -> None:
        """Open browser to renewal page, including user_id and token via backend."""
        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User)
                    .where(User.is_logged_in == True)
                    .order_by(User.last_login_at.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if not user:
                    QMessageBox.information(
                        self,
                        "Renew Subscription",
                        "No logged-in user found. Please log in again first.",
                    )
                    return

                user_id = user.api_user_id or str(user.id)
                token = user.access_token
                if not token:
                    QMessageBox.information(
                        self,
                        "Renew Subscription",
                        "No access token found for this user. Please log in again to refresh your session.",
                    )
                    return

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Renew Subscription",
                f"Unable to prepare renewal link: {exc}",
            )
            return

        # We cannot set HTTP headers directly in the user's browser, so instead
        # we pass the token via querystring for the web backend to validate.
        url = QUrl(f"https://www.deskhab.com/renew-smartcalender/{user_id}")
        url.setQuery(f"token={token}")
        QDesktopServices.openUrl(url)
        # Let parent window know renewal has started (so it can open websocket for realtime unlock).
        self.renewSubscriptionRequested.emit()

        # Last backup
        last = self._settings._get("last_backup_time", "")
        if last:
            self._last_backup_label.setText(f"Last backup: {last}")
        else:
            self._last_backup_label.setText("Last backup: Never")

    def apply_changes(self) -> None:
        """Save all settings to the database."""
        s = self._settings

        # General
        theme: ThemeName = "dark" if self._dark_btn.isChecked() else "light"
        s.set_theme(theme)
        s.set_language(self._lang_combo.currentText())
        s.set_default_category(self._cat_combo.currentText())

        freq_map = {0: "Daily", 1: "Weekly", 2: "Monthly"}
        checked = self._freq_group.checkedId()
        s.set_reminder_frequency(freq_map.get(checked, "Daily"))

        view_map = {0: "day", 1: "week", 2: "month", 3: "year"}
        view: ViewName = view_map.get(self._view_combo.currentIndex(), "day")  # type: ignore
        s.set_default_view(view)
        s.set_weather_city(self._weather_edit.text())

        # Account — update user in DB
        try:
            with self._db.session() as session:
                user = session.execute(
                    select(User).where(User.is_active == True).limit(1)
                ).scalar_one_or_none()
                if user:
                    new_name = self._username_edit.text().strip()
                    if new_name:
                        user.name = new_name
                    email = self._email_edit.text().strip()
                    if email:
                        user.email = email
                    session.commit()
        except Exception:
            pass

        # Notifications
        s.set_notifications_enabled(self._notif_check.isChecked())
        s.set_email_alerts(self._email_alerts_check.isChecked())
        s.set_sound_alerts(self._sound_check.isChecked())
        # Reminder sound - remove emoji prefix if present
        if hasattr(self, '_sound_combo'):
            selected_sound = self._sound_combo.currentText().replace("🎵 ", "")
            self._logger.info(f"Saving reminder sound setting: '{selected_sound}'")
            s.set_reminder_sound(selected_sound)
            # Verify it was saved
            saved_sound = s.get_reminder_sound()
            self._logger.info(f"Verified saved reminder sound: '{saved_sound}'")
        s.set_default_reminder_minutes(self._reminder_spin.value())
        s.set_quiet_hours_start(self._quiet_start.time().toString("HH:mm"))
        s.set_quiet_hours_end(self._quiet_end.time().toString("HH:mm"))

        # Backup
        s.set_auto_backup(self._auto_backup_check.isChecked())
        s.set_backup_schedule(self._backup_sched_combo.currentText())

    # =====================================================================
    #  ACTIONS
    # =====================================================================

    def _on_save(self) -> None:
        self.apply_changes()
        self._save_status.setText("✅ Saved!")
        self._save_status.setStyleSheet("color: #10B981; font-weight: 600; font-size: 12px;")
        self.settingsSaved.emit()
        # Clear status after 3 seconds
        QTimer.singleShot(3000, lambda: self._save_status.setText(""))

    def _on_reset(self) -> None:
        reply = self._styled_msg(
            QMessageBox.Question,
            "Reset Settings",
            "Are you sure you want to reset all settings to default?\n\n"
            "This will not delete your data, only reset preferences.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._light_btn.setChecked(True)
            self._lang_combo.setCurrentIndex(0)
            self._cat_combo.setCurrentIndex(0)
            self._freq_daily.setChecked(True)
            self._view_combo.setCurrentIndex(0)
            self._weather_edit.clear()
            self._notif_check.setChecked(True)
            self._email_alerts_check.setChecked(False)
            self._sound_check.setChecked(True)
            if hasattr(self, '_sound_combo'):
                self._sound_combo.setCurrentIndex(0)  # Default sound
            self._reminder_spin.setValue(10)
            self._quiet_start.setTime(QTime(22, 0))
            self._quiet_end.setTime(QTime(7, 0))
            self._auto_backup_check.setChecked(False)
            self._backup_sched_combo.setCurrentIndex(1)
            self._save_status.setText("↺ Reset to defaults (save to apply)")
            self._save_status.setStyleSheet("color: #F59E0B; font-weight: 600; font-size: 12px;")

    def _on_logout(self) -> None:
        reply = self._styled_msg(
            QMessageBox.Question,
            "Log Out",
            "Are you sure you want to log out?\n\nThis will close the application.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            # Close the entire application
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()

    def _on_delete_all_data(self) -> None:
        reply = self._styled_msg(
            QMessageBox.Warning,
            "Delete All Data",
            "⚠️ This will permanently delete ALL your meetings, tasks, and settings.\n\n"
            "This action CANNOT be undone.\n\nAre you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            # Double confirmation
            reply2 = self._styled_msg(
                QMessageBox.Critical,
                "Final Confirmation",
                "Type 'DELETE' in your mind and click Yes to confirm.\n\n"
                "ALL DATA WILL BE PERMANENTLY REMOVED.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply2 == QMessageBox.Yes:
                try:
                    with self._db.session() as session:
                        session.execute(Meeting.__table__.delete())
                        session.execute(Task.__table__.delete())
                        session.commit()
                    self._styled_msg(
                        QMessageBox.Information,
                        "Data Deleted",
                        "✅ All meetings and tasks have been deleted.\n"
                        "Settings have been preserved.",
                    )
                    # Refresh stats
                    self._stat_tasks.setText("0 tasks")
                    self._stat_meetings.setText("0 meetings")
                except Exception as e:
                    self._styled_msg(QMessageBox.Critical, "Error", f"Failed to delete data:\n{e}")

    def _on_backup_now(self) -> None:
        db_path = Path(self._db.db_path)

        if not db_path.exists():
            self._styled_msg(QMessageBox.Warning, "Backup", "Database file not found.")
            return

        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Save Backup",
            f"smart_calendar_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
            "Database Files (*.db)",
        )
        if dest:
            try:
                shutil.copy2(str(db_path), dest)
                # Record backup time
                self._settings._set(
                    "last_backup_time",
                    datetime.now().strftime("%Y-%m-%d %H:%M")
                )
                self._last_backup_label.setText(
                    f"Last backup: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
                self._styled_msg(
                    QMessageBox.Information, "Backup",
                    f"✅ Backup saved successfully!\n\n📁 {dest}"
                )
            except Exception as e:
                self._styled_msg(QMessageBox.Critical, "Backup Error", str(e))

    def _on_restore(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File", "", "Database Files (*.db)"
        )
        if path:
            reply = self._styled_msg(
                QMessageBox.Warning,
                "Restore Backup",
                "⚠️ This will overwrite your current data with the backup.\n\n"
                "Are you sure you want to continue?\n"
                "The app will need to restart after restore.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                try:
                    db_path = Path(self._db.db_path)

                    # Create a backup of current before restore
                    if db_path.exists():
                        backup_path = db_path.with_suffix(".db.bak")
                        shutil.copy2(str(db_path), str(backup_path))

                    # Copy the restore file
                    shutil.copy2(path, str(db_path))

                    self._styled_msg(
                        QMessageBox.Information,
                        "Restore Complete",
                        "✅ Database restored successfully!\n\n"
                        "Please restart the application for changes to take effect.\n\n"
                        "A backup of your previous database was saved as .db.bak"
                    )
                except Exception as e:
                    self._styled_msg(QMessageBox.Critical, "Restore Error", str(e))

    def _on_export(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            f"smart_calendar_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)",
        )
        if dest:
            try:
                data = {
                    "exported_at": datetime.now().isoformat(),
                    "app": "Smart Calendar",
                    "version": "1.0",
                    "settings": {},
                    "meetings": [],
                    "tasks": [],
                }

                # Collect all settings
                for key in [
                    "theme", "language", "default_category", "reminder_frequency",
                    "default_view", "weather_city", "notifications_enabled",
                    "email_alerts", "sound_alerts", "quiet_hours_start",
                    "quiet_hours_end", "auto_backup", "backup_schedule",
                    "default_reminder_minutes", "reminder_sound",
                ]:
                    data["settings"][key] = self._settings._get(key, "")

                # Export meetings
                with self._db.session() as session:
                    meetings = session.query(Meeting).all()
                    for m in meetings:
                        data["meetings"].append({
                            "id": m.id,
                            "title": m.title,
                            "description": m.description,
                            "start_time": m.start_time.isoformat() if m.start_time else None,
                            "end_time": m.end_time.isoformat() if m.end_time else None,
                            "location": m.location,
                            "color_gradient": m.color_gradient,
                        })

                    # Export tasks
                    tasks = session.query(Task).all()
                    for t in tasks:
                        data["tasks"].append({
                            "id": t.id,
                            "name": t.name,
                            "description": t.description,
                            "deadline": t.deadline.isoformat() if t.deadline else None,
                            "task_date": t.task_date.isoformat() if t.task_date else None,
                            "priority": t.priority,
                            "status": t.status,
                            "progress": t.progress,
                        })

                with open(dest, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                total = len(data["meetings"]) + len(data["tasks"])
                self._styled_msg(
                    QMessageBox.Information,
                    "Export Complete",
                    f"✅ Data exported successfully!\n\n"
                    f"📊 {len(data['meetings'])} meetings, {len(data['tasks'])} tasks\n"
                    f"📁 {dest}"
                )
            except Exception as e:
                self._styled_msg(QMessageBox.Critical, "Export Error", str(e))

    def _on_test_sound(self) -> None:
        """Test the selected sound."""
        if not hasattr(self, '_sound_combo'):
            return
        selected_sound = self._sound_combo.currentText().replace("🎵 ", "")
        self._logger.info(f"Testing sound: '{selected_sound}'")
        try:
            self._sound_service.play_sound(selected_sound, repeat=3)
        except Exception as e:
            self._logger.error(f"Error testing sound: {e}", exc_info=True)
    
    def _populate_sound_combo(self) -> None:
        """Populate the sound combo box with available sounds."""
        if not hasattr(self, '_sound_combo'):
            return
        self._sound_combo.clear()
        
        # Add system sounds
        system_sounds = self._sound_service.get_available_sounds()
        for sound in system_sounds:
            self._sound_combo.addItem(sound)
        
        # Add separator if we have custom sounds
        custom_sounds = self._sound_service.get_custom_sounds()
        if custom_sounds:
            self._sound_combo.insertSeparator(len(system_sounds))
            # Add custom sounds
            for sound_file in custom_sounds:
                # Remove extension for display
                sound_name = sound_file.replace(".wav", "").replace(".mp3", "").replace(".aiff", "").replace(".m4a", "")
                self._sound_combo.addItem(f"🎵 {sound_name}")

    # =====================================================================
    #  About Tab
    # =====================================================================

    def _build_about_tab(self) -> QWidget:
        """Build the About tab."""
        import sys
        import platform as _platform

        page = QWidget()
        page.setStyleSheet("background-color: #FFFFFF;")
        scroll = QScrollArea(page)
        scroll.setStyleSheet("background-color: #FFFFFF;")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setStyleSheet("background-color: #FFFFFF;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(20)

        # ── App badge ────────────────────────────────────────────────
        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignHCenter)

        icon_lbl = QLabel()
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(64, 64)
        icon_lbl.setStyleSheet("background: transparent;")

        # Use bundled logo image (works inside packaged app).
        logo_path = get_base_dir() / "assets" / "image.png"
        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            icon_lbl.setPixmap(
                pixmap.scaled(
                    64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        else:
            # Fallback for development or missing file
            icon_lbl.setText("📆")
            icon_lbl.setStyleSheet("font-size: 64px; background: transparent;")
        badge_row.addWidget(icon_lbl)
        lay.addLayout(badge_row)

        # App name
        # Brand accent color (green)
        accent = "#22C55E"

        name_lbl = QLabel("Smart Calender")
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {accent};"
            "background: transparent;"
        )
        lay.addWidget(name_lbl)

        version_lbl = QLabel("Version 1.0.0")
        version_lbl.setAlignment(Qt.AlignCenter)
        version_lbl.setStyleSheet("font-size: 13px; color: #7B8794; background: transparent;")
        lay.addWidget(version_lbl)

        # ── Divider ──────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFrameShadow(QFrame.Sunken)
        lay.addWidget(div)

        # ── Author card ───────────────────────────────────────────────
        card = QFrame()
        card.setObjectName("AboutCard")
        card.setStyleSheet(
            "#AboutCard {"
            f"  background: #F8FAFC;"
            f"  border: 1px solid rgba(34,197,94,0.22);"
            "  border-radius: 12px;"
            "  padding: 16px;"
            "}"
        )
        card_lay = QVBoxLayout(card)
        card_lay.setSpacing(8)

        def _row(label: str, value: str) -> QHBoxLayout:
            row = QHBoxLayout()
            lbl = QLabel(f"<b>{label}</b>")
            lbl.setFixedWidth(140)
            lbl.setStyleSheet(
                "background: transparent; color: #6B7280; font-weight: 700;"
            )
            val = QLabel(value)
            val.setWordWrap(True)
            val.setStyleSheet("background: transparent; color: #111827;")
            row.addWidget(lbl)
            row.addWidget(val, 1)
            return row

        card_lay.addLayout(_row("Designed by", "blackie-networks"))
        card_lay.addLayout(_row("Application",  "Smart Calender Desktop"))
        card_lay.addLayout(_row("Version",       "1.0.0"))
        card_lay.addLayout(_row("Platform",
            f"{_platform.system()} {_platform.release()} ({_platform.machine()})"))
        card_lay.addLayout(_row("Built by", "blackie-networks"))
        card_lay.addLayout(
            _row("License", "Copyright © 2024 blackie-networks. All rights reserved.")
        )

        # Link to the builder website
        builder_link = QLabel(
            "Visit: <a href='https://www.blackie-networks.com'>www.blackie-networks.com</a>"
        )
        builder_link.setAlignment(Qt.AlignCenter)
        builder_link.setTextFormat(Qt.RichText)
        builder_link.setOpenExternalLinks(True)
        builder_link.setStyleSheet(
            "background: transparent; color: #16A34A; font-weight: 700;"
        )
        card_lay.addWidget(builder_link)

        lay.addWidget(card)

        # ── Description ───────────────────────────────────────────────
        desc = QLabel(
            "Smart Calender is a productivity desktop application for managing "
            "events, meetings, tasks and reminders — all in one place.\n\n"
            "Designed and built by <b>blackie-networks</b> with ❤️."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(
            "color: #6B7280; font-size: 13px; background: transparent; padding: 0 24px;"
        )
        desc.setTextFormat(Qt.RichText)
        lay.addWidget(desc)

        lay.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return page

    # =====================================================================
    #  QSS
    # =====================================================================

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "settings.qss"
        if qss_path.exists():
            qss = qss_path.read_text(encoding="utf-8")
            # Resolve icon paths to absolute so QSS finds them
            icons_dir = root / "ui" / "resources" / "icons"
            qss = qss.replace(
                "url(app/ui/resources/icons/",
                f"url({icons_dir}/",
            )
            self.setStyleSheet(qss)

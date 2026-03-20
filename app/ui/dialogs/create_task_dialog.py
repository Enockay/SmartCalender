from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDate, QTime, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.task import TaskModel, SubtaskModel, AttachmentModel, TagModel


class CreateTaskDialog(QDialog):
    """Dialog for creating and editing tasks."""

    def __init__(self, parent=None, task: TaskModel | None = None, task_date: date | None = None) -> None:
        super().__init__(parent)
        self._task = task
        self._task_date = task_date or date.today()
        self.setWindowTitle("+ Create Task" if task is None else "Edit Task")
        self.setObjectName("CreateTaskDialog")
        self.setFixedSize(480, 580)
        self.setModal(True)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        if hasattr(Qt, "WindowFullscreenButtonHint"):
            self.setWindowFlag(Qt.WindowFullscreenButtonHint, False)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._subtasks: list[QCheckBox] = []
        self._attachments: list[dict] = []
        self._tags: list[str] = []

        self._build_ui()
        self._load_qss()
        self._center_dialog()

        if task:
            self._load_task_data()

    def _center_dialog(self) -> None:
        """Center the dialog on the parent window or screen."""
        if self.parent():
            parent_geometry = self.parent().frameGeometry()
            dialog_geometry = self.frameGeometry()
            x = parent_geometry.center().x() - dialog_geometry.width() // 2
            y = parent_geometry.center().y() - dialog_geometry.height() // 2
            self.move(x, y)
        else:
            # Center on screen
            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                dialog_geometry = self.frameGeometry()
                x = screen_geometry.center().x() - dialog_geometry.width() // 2
                y = screen_geometry.center().y() - dialog_geometry.height() // 2
                self.move(x, y)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

       

        # Content area
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(12, 10, 12, 12)
        content_layout.setSpacing(8)

        # Scroll area for form
        scroll = QScrollArea(self)
        scroll.setObjectName("DialogScrollArea")
        scroll.setAttribute(Qt.WA_StyledBackground, True)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        form_widget = QWidget()
        form_widget.setObjectName("DialogFormWidget")
        form_widget.setAttribute(Qt.WA_StyledBackground, True)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(8)

        # Task Name
        name_row = QHBoxLayout()
        name_label = QLabel("Task Name:", self)
        name_label.setObjectName("FieldLabel")
        name_label.setFixedWidth(80)
        self._name_edit = QLineEdit(self)
        self._name_edit.setPlaceholderText("Enter task name")
        name_row.addWidget(name_label)
        name_row.addWidget(self._name_edit, 1)
        form_layout.addLayout(name_row)

        # Description
        desc_row = QHBoxLayout()
        desc_label = QLabel("Description:", self)
        desc_label.setObjectName("FieldLabel")
        desc_label.setFixedWidth(80)
        self._description_edit = QTextEdit(self)
        self._description_edit.setPlaceholderText("Enter task description")
        self._description_edit.setMaximumHeight(70)
        desc_row.addWidget(desc_label)
        desc_row.addWidget(self._description_edit, 1)
        form_layout.addLayout(desc_row)

        # Deadline
        deadline_row = QHBoxLayout()
        deadline_label = QLabel("Deadline:", self)
        deadline_label.setObjectName("FieldLabel")
        deadline_label.setFixedWidth(80)
        
        deadline_inputs = QHBoxLayout()
        deadline_inputs.setSpacing(8)
        
        self._deadline_edit = QDateEdit(self)
        self._deadline_edit.setCalendarPopup(True)
        self._deadline_edit.setDate(QDate.currentDate().addDays(7))
        self._deadline_edit.setDisplayFormat("dd/MM/yyyy")
        
        # Install event filter to catch clicks and open calendar
        self._deadline_edit.installEventFilter(self)
        
        self._deadline_time_edit = QTimeEdit(self)
        self._deadline_time_edit.setTime(QTime.currentTime())
        self._deadline_time_edit.setDisplayFormat("HH:mm")
        self._deadline_time_edit.setButtonSymbols(QTimeEdit.ButtonSymbols.UpDownArrows)
        
        deadline_inputs.addWidget(self._deadline_edit, 2)
        deadline_inputs.addWidget(self._deadline_time_edit, 1)
        
        deadline_row.addWidget(deadline_label)
        deadline_row.addLayout(deadline_inputs, 1)
        form_layout.addLayout(deadline_row)

        # Task Date (the date this task belongs to)
        task_date_row = QHBoxLayout()
        task_date_label = QLabel("Task Date:", self)
        task_date_label.setObjectName("FieldLabel")
        task_date_label.setFixedWidth(80)
        
        self._task_date_edit = QDateEdit(self)
        self._task_date_edit.setCalendarPopup(True)
        self._task_date_edit.setDate(QDate.fromString(self._task_date.strftime("%Y-%m-%d"), "yyyy-MM-dd"))
        self._task_date_edit.setDisplayFormat("dd/MM/yyyy")
        # Only prevent past dates for new tasks, will be set in _load_task_data if editing
        if not self._task:
            self._task_date_edit.setMinimumDate(QDate.currentDate())  # Prevent past dates for new tasks
        
        task_date_row.addWidget(task_date_label)
        task_date_row.addWidget(self._task_date_edit, 1)
        form_layout.addLayout(task_date_row)

        # Priority
        priority_row = QHBoxLayout()
        priority_label = QLabel("Priority:", self)
        priority_label.setObjectName("FieldLabel")
        priority_label.setFixedWidth(80)
        self._priority_combo = QComboBox(self)
        self._priority_combo.addItems(["Low", "Medium", "High"])
        self._priority_combo.setCurrentText("Medium")
        priority_row.addWidget(priority_label)
        priority_row.addWidget(self._priority_combo, 1)
        form_layout.addLayout(priority_row)

        # Divider
        divider = QFrame(self)
        divider.setObjectName("DialogDivider")
        divider.setFixedHeight(1)
        form_layout.addWidget(divider)

        # Attachments section
        attachments_label = QLabel("Attachments:", self)
        attachments_label.setObjectName("SectionLabel")
        form_layout.addWidget(attachments_label)

        self._attachments_container = QWidget()
        self._attachments_container.setObjectName("AttachmentsContainer")
        self._attachments_container.setAttribute(Qt.WA_StyledBackground, True)
        attachments_layout = QVBoxLayout(self._attachments_container)
        attachments_layout.setContentsMargins(0, 0, 0, 0)
        attachments_layout.setSpacing(4)

        add_attachment_btn = QPushButton("+ Add Attachment", self)
        add_attachment_btn.setObjectName("AddButton")
        add_attachment_btn.clicked.connect(self._add_attachment)
        attachments_layout.addWidget(add_attachment_btn)

        form_layout.addWidget(self._attachments_container)

        # Divider
        divider2 = QFrame(self)
        divider2.setObjectName("DialogDivider")
        divider2.setFixedHeight(1)
        form_layout.addWidget(divider2)

        # Subtasks section
        subtasks_label = QLabel("Subtasks:", self)
        subtasks_label.setObjectName("SectionLabel")
        form_layout.addWidget(subtasks_label)

        self._subtasks_container = QWidget()
        subtasks_layout = QVBoxLayout(self._subtasks_container)
        subtasks_layout.setContentsMargins(0, 0, 0, 0)
        subtasks_layout.setSpacing(4)

        add_subtask_btn = QPushButton("+ Add Subtask", self)
        add_subtask_btn.setObjectName("AddButton")
        add_subtask_btn.clicked.connect(self._add_subtask)
        subtasks_layout.addWidget(add_subtask_btn)

        form_layout.addWidget(self._subtasks_container)

        # Tags section
        tags_row = QHBoxLayout()
        tags_label = QLabel("Tags:", self)
        tags_label.setObjectName("SectionLabel")
        tags_label.setFixedWidth(80)
        self._tags_edit = QLineEdit(self)
        self._tags_edit.setPlaceholderText("Enter tags separated by commas")
        tags_row.addWidget(tags_label)
        tags_row.addWidget(self._tags_edit, 1)
        form_layout.addLayout(tags_row)

        form_layout.addStretch()

        scroll.setWidget(form_widget)
        content_layout.addWidget(scroll)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        button_box.setObjectName("DialogButtonBox")
        button_box.accepted.connect(self._on_save_clicked)
        button_box.rejected.connect(self.reject)
        
        # Set object names for styling
        save_button = button_box.button(QDialogButtonBox.Save)
        if save_button:
            save_button.setObjectName("SaveButton")
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        if cancel_button:
            cancel_button.setObjectName("CancelButton")
        
        content_layout.addWidget(button_box)

        layout.addLayout(content_layout)

    def _add_subtask(self) -> None:
        """Add a new subtask input."""
        layout = self._subtasks_container.layout()
        subtask_layout = QHBoxLayout()
        subtask_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox("", self)
        subtask_input = QLineEdit(self)
        subtask_input.setPlaceholderText("Enter subtask name")
        delete_btn = QPushButton("×", self)
        delete_btn.setFixedSize(20, 20)
        delete_btn.setObjectName("DeleteButton")

        def remove_subtask():
            layout.removeItem(subtask_layout)
            checkbox.setParent(None)
            subtask_input.setParent(None)
            delete_btn.setParent(None)
            if checkbox in self._subtasks:
                self._subtasks.remove(checkbox)

        delete_btn.clicked.connect(remove_subtask)

        subtask_layout.addWidget(checkbox)
        subtask_layout.addWidget(subtask_input)
        subtask_layout.addWidget(delete_btn)

        layout.insertWidget(layout.count() - 1, QWidget())  # Spacer
        layout.insertLayout(layout.count() - 1, subtask_layout)

        self._subtasks.append(checkbox)

    def _add_attachment(self) -> None:
        """Add a new attachment."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File", "", "All Files (*)"
        )
        if file_path:
            path_obj = Path(file_path)
            file_size = path_obj.stat().st_size if path_obj.exists() else 0
            file_type = "document"
            if path_obj.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif"]:
                file_type = "image"
            elif path_obj.suffix.lower() in [".pdf", ".doc", ".docx"]:
                file_type = "document"

            attachment = {
                "file_path": file_path,
                "file_name": path_obj.name,
                "file_type": file_type,
                "file_size": file_size,
            }
            self._attachments.append(attachment)
            self._update_attachments_display()

    def _update_attachments_display(self) -> None:
        """Update the attachments display."""
        layout = self._attachments_container.layout()
        # Clear existing attachment widgets (except add button)
        while layout.count() > 1:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        for att in self._attachments:
            att_frame = QFrame(self)
            att_frame.setObjectName("AttachmentItem")
            att_frame.setAttribute(Qt.WA_StyledBackground, True)
            att_frame.setCursor(Qt.PointingHandCursor)
            att_layout = QHBoxLayout(att_frame)
            att_layout.setContentsMargins(8, 6, 6, 6)
            att_layout.setSpacing(8)

            file_label = QLabel(f"📎 {att['file_name']} ({self._format_file_size(att['file_size'])})", att_frame)
            file_label.setObjectName("AttachmentLabel")
            file_label.setWordWrap(True)
            file_label.setCursor(Qt.PointingHandCursor)
            
            # Make label clickable to open file
            def make_open_handler(attachment):
                def open_attachment(event):
                    file_path = Path(attachment['file_path'])
                    if file_path.exists():
                        QDesktopServices.openUrl(QUrl.fromLocalFile(str(file_path.absolute())))
                return open_attachment
            
            file_label.mousePressEvent = make_open_handler(att)
            
            delete_btn = QPushButton("×", att_frame)
            delete_btn.setFixedSize(20, 20)
            delete_btn.setObjectName("DeleteButton")
            delete_btn.clicked.connect(lambda checked, a=att: self._remove_attachment(a))

            att_layout.addWidget(file_label, 1)
            att_layout.addWidget(delete_btn)

            layout.insertWidget(layout.count() - 1, att_frame)

    def _remove_attachment(self, attachment: dict) -> None:
        """Remove an attachment."""
        if attachment in self._attachments:
            self._attachments.remove(attachment)
            self._update_attachments_display()

    def _format_file_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} GB"

    def _load_task_data(self) -> None:
        """Load task data into the form."""
        if not self._task:
            return

        self._name_edit.setText(self._task.name)
        if self._task.description:
            self._description_edit.setPlainText(self._task.description)
        if self._task.deadline:
            qdate = QDate(
                self._task.deadline.year,
                self._task.deadline.month,
                self._task.deadline.day,
            )
            self._deadline_edit.setDate(qdate)
            qtime = QTime(
                self._task.deadline.hour,
                self._task.deadline.minute,
            )
            self._deadline_time_edit.setTime(qtime)
        if self._task.priority:
            self._priority_combo.setCurrentText(self._task.priority)

        # Load subtasks
        for subtask in self._task.subtasks:
            self._add_subtask()
            if self._subtasks:
                # Get the last added subtask input
                last_layout = self._subtasks_container.layout().itemAt(
                    self._subtasks_container.layout().count() - 2
                )
                if last_layout and last_layout.layout():
                    for i in range(last_layout.layout().count()):
                        widget = last_layout.layout().itemAt(i).widget()
                        if isinstance(widget, QLineEdit):
                            widget.setText(subtask.name)
                        elif isinstance(widget, QCheckBox):
                            widget.setChecked(subtask.completed)

        # Load attachments
        self._attachments = [
            {
                "file_path": att.file_path,
                "file_name": att.file_name,
                "file_type": att.file_type or "document",
                "file_size": att.file_size or 0,
            }
            for att in self._task.attachments
        ]
        self._update_attachments_display()

        # Load tags
        if self._task.tags:
            tag_names = [tag.tag_name for tag in self._task.tags]
            self._tags_edit.setText(", ".join(tag_names))
        
        # Load task_date
        if self._task.task_date:
            task_date_obj = self._task.task_date.date() if isinstance(self._task.task_date, datetime) else self._task.task_date
            if isinstance(task_date_obj, date):
                self._task_date_edit.setDate(QDate(task_date_obj.year, task_date_obj.month, task_date_obj.day))
                # When editing, don't allow changing to past dates
                # Set minimum date to today to prevent selecting past dates
                self._task_date_edit.setMinimumDate(QDate.currentDate())

    def _load_qss(self) -> None:
        """Load QSS styling."""
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "create_task_dialog.qss"
        if qss_path.exists():
            style = qss_path.read_text(encoding="utf-8")
            self.setStyleSheet(style)
        else:
            # Debug: print if file not found
            print(f"QSS file not found at: {qss_path}")

    def get_task_data(self) -> dict | None:
        """Get task data from the form."""
        name = self._name_edit.text().strip()
        if not name:
            return None

        description = self._description_edit.toPlainText().strip() or None

        qdate = self._deadline_edit.date()
        qtime = self._deadline_time_edit.time()
        if qdate.isValid() and qtime.isValid():
            deadline = datetime(
                qdate.year(), qdate.month(), qdate.day(),
                qtime.hour(), qtime.minute()
            )
        else:
            deadline = None

        # Get task date and validate it's not in the past
        task_qdate = self._task_date_edit.date()
        if not task_qdate.isValid():
            QMessageBox.warning(self, "Invalid Date", "Please select a valid task date.")
            return None
        
        task_date_obj = date(task_qdate.year(), task_qdate.month(), task_qdate.day())
        today = date.today()
        
        if task_date_obj < today:
            message = "You cannot add tasks to past dates.\nPlease select today or a future date." if not self._task else "You cannot change a task date to a past date.\nPlease select today or a future date."
            QMessageBox.warning(
                self,
                "Past Date",
                message,
                QMessageBox.Ok
            )
            return None
        
        # Convert task_date to datetime (start of day)
        task_date = datetime.combine(task_date_obj, datetime.min.time())
        
        priority = self._priority_combo.currentText() or None

        # Collect subtasks
        subtasks = []
        layout = self._subtasks_container.layout()
        for i in range(layout.count() - 1):  # Exclude add button
            item = layout.itemAt(i)
            if item and item.layout():
                checkbox = None
                line_edit = None
                for j in range(item.layout().count()):
                    widget = item.layout().itemAt(j).widget()
                    if isinstance(widget, QCheckBox):
                        checkbox = widget
                    elif isinstance(widget, QLineEdit):
                        line_edit = widget
                if checkbox and line_edit and line_edit.text().strip():
                    subtasks.append({
                        "name": line_edit.text().strip(),
                        "completed": checkbox.isChecked(),
                    })

        # Tags
        tags_text = self._tags_edit.text().strip()
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()] if tags_text else []

        # Calculate progress based on subtasks if available
        progress = 0.0
        if subtasks:
            total = len(subtasks)
            completed = sum(1 for st in subtasks if st.get("completed", False))
            if total > 0:
                progress = (completed / total * 100.0)
        
        # If no subtasks, use status-based progress (will be set when status changes)
        # For now, default to 0% for backlog, 50% for in_progress if task exists
        if not subtasks and self._task:
            status = getattr(self._task, "status", "backlog")
            if status == "completed":
                progress = 100.0
            elif status == "in_progress":
                progress = 50.0
            else:
                progress = 0.0

        return {
            "name": name,
            "description": description,
            "deadline": deadline,
            "task_date": task_date,
            "priority": priority,
            "progress": progress,
            "subtasks": subtasks,
            "attachments": self._attachments,
            "tags": tags,
        }

    def eventFilter(self, obj, event) -> bool:
        """Event filter to handle date edit clicks."""
        if obj == self._deadline_edit:
            from PySide6.QtGui import QMouseEvent
            if isinstance(event, QMouseEvent) and event.type() == QMouseEvent.Type.MouseButtonPress:
                # Get click position
                click_x = event.position().x() if hasattr(event, 'position') else event.x()
                button_width = 28  # Width of calendar button
                
                # If click is on the input field (not the button), simulate clicking the button
                if click_x < (obj.width() - button_width):
                    # Simulate a click on the calendar button to open the popup
                    QTimer.singleShot(50, self._trigger_calendar_button_click)
        return super().eventFilter(obj, event)
    
    def _trigger_calendar_button_click(self) -> None:
        """Trigger the calendar popup by simulating a click on the dropdown button."""
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication
        
        # Calculate button center position (right side of widget)
        button_width = 28
        button_x = self._deadline_edit.width() - (button_width // 2)
        button_y = self._deadline_edit.height() // 2
        button_pos = QPoint(button_x, button_y)
        
        # Create and send mouse press event to trigger calendar popup
        mouse_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            button_pos,
            self._deadline_edit.mapToGlobal(button_pos),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        QApplication.sendEvent(self._deadline_edit, mouse_event)

    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        if self.get_task_data() is None:
            return
        self.accept()

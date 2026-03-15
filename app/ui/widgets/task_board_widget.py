from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.task import TaskModel
from app.ui.widgets.task_card_widget import TaskCardWidget


class TasksContainerWidget(QWidget):
    """Container widget that accepts drops for task cards."""
    
    def __init__(self, column_status: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._column_status = column_status
        self.setAcceptDrops(True)
        self.setObjectName("TasksContainer")
        self.setAttribute(Qt.WA_StyledBackground, True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Accept drag events if they contain task ID data."""
        if event.mimeData().hasText():
            try:
                int(event.mimeData().text())  # Validate it's a number
                event.acceptProposedAction()
            except ValueError:
                event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        """Handle drop events to move tasks between columns."""
        if event.mimeData().hasText():
            try:
                task_id = int(event.mimeData().text())
                # Find the parent TaskBoardWidget and call its drop handler
                parent = self.parent()
                while parent and not isinstance(parent, TaskBoardWidget):
                    parent = parent.parent()
                if parent:
                    parent._on_task_dropped(task_id, self._column_status)
                event.acceptProposedAction()
            except (ValueError, AttributeError):
                event.ignore()


class TaskColumnWidget(QWidget):
    """A single Kanban column in the task board."""

    def __init__(self, title: str, status: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._status = status

        self.setObjectName("TaskColumn")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumWidth(240)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Column header ──
        col_header = QWidget(self)
        col_header.setObjectName("ColumnHeader")
        col_header.setAttribute(Qt.WA_StyledBackground, True)
        ch_lay = QHBoxLayout(col_header)
        ch_lay.setContentsMargins(12, 10, 12, 10)
        ch_lay.setSpacing(8)

        accent = QFrame(self)
        accent.setFixedWidth(4)
        accent.setFixedHeight(22)
        accent.setObjectName(self._accent_object_name())
        ch_lay.addWidget(accent, alignment=Qt.AlignVCenter)

        icon = self._get_column_icon()
        title_label = QLabel(f"{icon} {self._title}", self)
        title_label.setObjectName(self._get_title_object_name())
        ch_lay.addWidget(title_label)

        self._count_label = QLabel("0", self)
        self._count_label.setObjectName("ColumnCount")
        self._count_label.setAlignment(Qt.AlignCenter)
        self._count_label.setFixedSize(24, 24)
        ch_lay.addWidget(self._count_label)

        ch_lay.addStretch()
        main_layout.addWidget(col_header)

        # ── Tasks scroll area ──
        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("TaskColumnScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QFrame.NoFrame)

        self._tasks_container = TasksContainerWidget(self._status, self)
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setContentsMargins(6, 4, 6, 4)
        self._tasks_layout.setSpacing(4)
        self._tasks_layout.addStretch()

        self._scroll.setWidget(self._tasks_container)
        main_layout.addWidget(self._scroll)

    def _accent_object_name(self) -> str:
        mapping = {
            "backlog": "ColumnAccentBacklog",
            "in_progress": "ColumnAccentInProgress",
            "completed": "ColumnAccentCompleted",
        }
        return mapping.get(self._status, "ColumnAccentBacklog")
    
    def _get_column_icon(self) -> str:
        """Get icon emoji for the column based on status."""
        mapping = {
            "backlog": "📋",
            "in_progress": "⚡",
            "completed": "✅",
        }
        return mapping.get(self._status, "📋")
    
    def _get_title_object_name(self) -> str:
        """Get object name for the title label based on status."""
        mapping = {
            "backlog": "ColumnTitleBacklog",
            "in_progress": "ColumnTitleInProgress",
            "completed": "ColumnTitleCompleted",
        }
        return mapping.get(self._status, "ColumnTitleBacklog")

    def add_task_card(self, card: TaskCardWidget) -> None:
        """Insert a task card before the trailing stretch."""
        self._tasks_layout.insertWidget(self._tasks_layout.count() - 1, card)
        self._update_count()

    def remove_task_card(self, card: TaskCardWidget) -> None:
        """Remove a task card from this column."""
        self._tasks_layout.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        self._update_count()

    def clear_tasks(self) -> None:
        """Remove all task cards from this column."""
        while self._tasks_layout.count() > 1:  # keep stretch
            item = self._tasks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        self._update_count()

    def _update_count(self) -> None:
        """Refresh the visible task count."""
        count = self._tasks_layout.count() - 1  # exclude stretch
        self._count_label.setText(str(max(0, count)))

    def get_status(self) -> str:
        """Return the logical status represented by this column."""
        return self._status


class TaskBoardWidget(QWidget):
    """Kanban-style board widget for structured task management."""

    taskClicked = Signal(int)           # task_id
    taskDeleted = Signal(int)           # task_id
    taskStatusChanged = Signal(int, str)  # task_id, new_status

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("TaskBoard")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._task_cards: dict[int, TaskCardWidget] = {}
        self._current_date: date | None = None

        self._build_ui()
        self._load_qss()
    
    def set_date(self, task_date: date) -> None:
        """Set the date for filtering tasks."""
        self._current_date = task_date
        self._update_date_display()
    
    def get_date(self) -> date | None:
        """Get the current date being displayed."""
        return self._current_date

    def _build_ui(self) -> None:
        # Main vertical layout for the board
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Professional header bar ──
        header_bar = QWidget(self)
        header_bar.setObjectName("TaskBoardHeader")
        header_bar.setAttribute(Qt.WA_StyledBackground, True)
        h_lay = QHBoxLayout(header_bar)
        h_lay.setContentsMargins(20, 10, 20, 10)
        h_lay.setSpacing(10)

        self._date_label = QLabel(header_bar)
        self._date_label.setObjectName("TaskBoardDate")
        self._update_date_display()
        h_lay.addWidget(self._date_label)

        h_lay.addStretch()

        self._summary_label = QLabel("", header_bar)
        self._summary_label.setObjectName("TaskBoardSummary")
        h_lay.addWidget(self._summary_label)

        main_layout.addWidget(header_bar)

        # ── Instruction ribbon ──
        ribbon = QWidget(self)
        ribbon.setObjectName("TaskBoardRibbon")
        ribbon.setAttribute(Qt.WA_StyledBackground, True)
        r_lay = QHBoxLayout(ribbon)
        r_lay.setContentsMargins(20, 6, 20, 6)
        instruction = QLabel("💡 Drag and drop tasks between columns to update their progress", ribbon)
        instruction.setObjectName("TaskBoardInstruction")
        r_lay.addWidget(instruction)
        main_layout.addWidget(ribbon)

        # ── Columns area ──
        self._horizontal_scroll = QScrollArea(self)
        self._horizontal_scroll.setObjectName("TaskBoardScroll")
        self._horizontal_scroll.setWidgetResizable(True)
        self._horizontal_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._horizontal_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._horizontal_scroll.setFrameShape(QFrame.NoFrame)

        columns_container = QWidget()
        columns_container.setObjectName("ColumnsContainer")
        columns_container.setAttribute(Qt.WA_StyledBackground, True)

        columns_layout = QHBoxLayout(columns_container)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(6)

        self._backlog_column = TaskColumnWidget("Backlog", "backlog", columns_container)
        self._in_progress_column = TaskColumnWidget("In Progress", "in_progress", columns_container)
        self._completed_column = TaskColumnWidget("Completed", "completed", columns_container)

        columns_layout.addWidget(self._backlog_column, stretch=1)
        columns_layout.addWidget(self._in_progress_column, stretch=1)
        columns_layout.addWidget(self._completed_column, stretch=1)

        self._horizontal_scroll.setWidget(columns_container)
        main_layout.addWidget(self._horizontal_scroll)

    def _load_qss(self) -> None:
        """Load the task board stylesheet."""
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "task_board.qss"

        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def _update_date_display(self) -> None:
        """Update the date display in the header."""
        display_date = self._current_date if self._current_date else date.today()
        date_str = display_date.strftime("Task Board – %A, %d %B %Y")
        self._date_label.setText(date_str)
        # Update summary count
        total = len(self._task_cards)
        if hasattr(self, "_summary_label"):
            self._summary_label.setText(
                f"{total} task{'s' if total != 1 else ''}" if total else "No tasks"
            )

    def set_tasks(self, tasks: List[TaskModel]) -> None:
        """Populate the board with a new list of tasks."""
        self.clear_tasks()
        for task in tasks:
            self.add_task(task)
        self._update_date_display()

    def add_task(self, task: TaskModel) -> None:
        """Create and place a task card into the appropriate column."""
        if task.id in self._task_cards:
            self.remove_task(task.id)

        card = TaskCardWidget(task, self)
        card.clicked.connect(self.taskClicked.emit)
        card.deleteRequested.connect(self._on_delete_requested)

        column = self._get_column_for_status(getattr(task, "status", "backlog"))
        column.add_task_card(card)

        self._task_cards[task.id] = card

    def remove_task(self, task_id: int) -> None:
        """Remove a task card from the board by task ID."""
        card = self._task_cards.get(task_id)
        if card is None:
            return

        for column in self._all_columns():
            if card.parent() == column._tasks_container:
                column.remove_task_card(card)
                break

        del self._task_cards[task_id]

    def update_task(self, task: TaskModel) -> None:
        """Replace an existing card with updated task data."""
        self.remove_task(task.id)
        self.add_task(task)

    def clear_tasks(self) -> None:
        """Clear all task cards from every column."""
        for column in self._all_columns():
            column.clear_tasks()
        self._task_cards.clear()

    def _get_column_for_status(self, status: str) -> TaskColumnWidget:
        mapping = {
            "backlog": self._backlog_column,
            "in_progress": self._in_progress_column,
            "completed": self._completed_column,
        }
        # Map old "review" status to "in_progress" for backward compatibility
        if status == "review":
            status = "in_progress"
        return mapping.get(status, self._backlog_column)

    def _all_columns(self) -> list[TaskColumnWidget]:
        return [
            self._backlog_column,
            self._in_progress_column,
            self._completed_column,
        ]

    def _on_delete_requested(self, task_id: int) -> None:
        """Emit the delete signal upward."""
        self.taskDeleted.emit(task_id)

    def _on_task_dropped(self, task_id: int, new_status: str) -> None:
        """Handle task drop - move task to new column and update status."""
        card = self._task_cards.get(task_id)
        if card is None:
            return
        
        # Get current task
        task = card.get_task()
        old_status = getattr(task, "status", "backlog")
        
        # If status hasn't changed, do nothing
        if old_status == new_status:
            return
        
        # Update task status
        task.status = new_status
        
        # Update progress based on status
        status_progress_map = {
            "backlog": 0.0,
            "in_progress": 50.0,
            "completed": 100.0,
        }
        # Map old "review" status to "in_progress" for backward compatibility
        if new_status == "review":
            new_status = "in_progress"
        task.progress = status_progress_map.get(new_status, task.progress)
        
        # Update the card's task model without full rebuild to avoid layout issues
        card._task = task
        # Just update the progress bar and color without rebuilding entire UI
        if hasattr(card, "_progress_bar"):
            progress = card._calculate_progress()
            card._progress_bar.setValue(int(progress))
            progress_color = card._get_progress_bar_color()
            card._progress_bar.setStyleSheet(f"""
                QProgressBar#TaskProgressBar {{
                    border: none;
                    border-radius: 3px;
                    background: #F1F5F9;
                    height: 6px;
                }}
                QProgressBar#TaskProgressBar::chunk {{
                    background-color: {progress_color};
                    border-radius: 3px;
                }}
            """)
        
        # Update progress value label if it exists
        if hasattr(card, "_progress_value"):
            progress = card._calculate_progress()
            card._progress_value.setText(f"{int(progress)}%")
        
        # Move card to new column
        old_column = self._get_column_for_status(old_status)
        new_column = self._get_column_for_status(new_status)
        
        if old_column != new_column:
            old_column.remove_task_card(card)
            new_column.add_task_card(card)
        
        # Emit status change signal
        self.taskStatusChanged.emit(task_id, new_status)

    def highlight_task(self, task_id: int) -> None:
        """Scroll to and visually highlight a specific task card."""
        card = self._task_cards.get(task_id)
        if card is None:
            return

        # Ensure the card is visible by scrolling to it
        card.ensureVisible = True
        
        # Add a temporary highlight border
        original_style = card.styleSheet()
        card.setStyleSheet("""
            QFrame#TaskCard {
                background-color: #EEF2FF;
                border: 2px solid #4A6CF7;
                border-radius: 6px;
            }
        """)
        
        # Remove highlight after 2 seconds
        QTimer.singleShot(2000, lambda: card.setStyleSheet(original_style))
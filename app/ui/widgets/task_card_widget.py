from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize, Signal, QMimeData
from PySide6.QtGui import QPixmap, QDrag, QPainter, QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.task import TaskModel


class TaskCardWidget(QFrame):
    """A styled card widget representing a single task in the Kanban board."""

    clicked = Signal(int)           # task_id
    deleteRequested = Signal(int)   # task_id

    def __init__(self, task: TaskModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task = task

        self.setObjectName("TaskCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._build_ui()
        self._apply_inline_defaults()

    def _apply_inline_defaults(self) -> None:
        """Optional widget-level tuning not handled by QSS."""
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(6)

        # ---------------- Header ----------------
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._name_label = QLabel(self._task.name or "Untitled Task", self)
        self._name_label.setObjectName("TaskName")
        self._name_label.setWordWrap(True)
        self._name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header_layout.addWidget(self._name_label)

        self._delete_btn = QPushButton("×", self)
        self._delete_btn.setObjectName("TaskDeleteButton")
        self._delete_btn.setFixedSize(24, 24)
        self._delete_btn.setCursor(Qt.PointingHandCursor)
        self._delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self._task.id))
        header_layout.addWidget(self._delete_btn, alignment=Qt.AlignTop)

        main_layout.addLayout(header_layout)

        # ---------------- Meta row ----------------
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(8)

        if self._task.deadline:
            deadline_str = self._task.deadline.strftime("%b %d")
            deadline_label = QLabel(f"📅 {deadline_str}", self)
            deadline_label.setObjectName("TaskDeadline")
            meta_row.addWidget(deadline_label)

        meta_row.addStretch()

        if self._task.priority:
            priority_text = str(self._task.priority).strip().lower()
            priority_label = QLabel(priority_text.capitalize(), self)
            priority_label.setObjectName(f"TaskPriority{priority_text.capitalize()}")
            priority_label.setAlignment(Qt.AlignCenter)
            priority_label.setMinimumWidth(70)
            meta_row.addWidget(priority_label)

        main_layout.addLayout(meta_row)

        # ---------------- Description (optional) ----------------
        description = getattr(self._task, "description", None)
        if description:
            desc_label = QLabel(description, self)
            desc_label.setObjectName("TaskDescription")
            desc_label.setWordWrap(True)
            main_layout.addWidget(desc_label)

        # ---------------- Progress ----------------
        progress = self._calculate_progress()

        progress_title_row = QHBoxLayout()
        progress_title_row.setContentsMargins(0, 0, 0, 0)
        progress_title_row.setSpacing(6)

        progress_text = QLabel("Progress", self)
        progress_text.setObjectName("TaskProgressLabel")

        self._progress_value = QLabel(f"{int(progress)}%", self)
        self._progress_value.setObjectName("TaskProgressValue")

        progress_title_row.addWidget(progress_text)
        progress_title_row.addStretch()
        progress_title_row.addWidget(self._progress_value)

        main_layout.addLayout(progress_title_row)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setObjectName("TaskProgressBar")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(int(progress))
        self._progress_bar.setFormat("")
        
        # Set progress bar color based on status
        progress_color = self._get_progress_bar_color()
        self._progress_bar.setStyleSheet(f"""
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
        
        main_layout.addWidget(self._progress_bar)

        # ---------------- Stats row ----------------
        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(12)

        if self._task.subtasks:
            subtasks_label = QLabel(f"☑ {len(self._task.subtasks)} subtasks", self)
            subtasks_label.setObjectName("TaskSubtasks")
            stats_row.addWidget(subtasks_label)

        if self._task.attachments:
            # Show image thumbnails for image attachments
            image_attachments = [
                att for att in self._task.attachments 
                if att.file_type == "image" or self._is_image_file(att.file_path)
            ]
            non_image_attachments = [
                att for att in self._task.attachments 
                if att.file_type != "image" and not self._is_image_file(att.file_path)
            ]
            
            if image_attachments:
                # Create a horizontal layout for image thumbnails
                images_layout = QHBoxLayout()
                images_layout.setContentsMargins(0, 0, 0, 0)
                images_layout.setSpacing(4)
                
                # Show up to 3 image thumbnails
                for att in image_attachments[:3]:
                    thumbnail = self._create_image_thumbnail(att)
                    if thumbnail:
                        images_layout.addWidget(thumbnail)
                
                # If there are more than 3 images, show a count indicator
                if len(image_attachments) > 3:
                    more_label = QLabel(f"+{len(image_attachments) - 3}", self)
                    more_label.setObjectName("TaskAttachmentMore")
                    more_label.setAlignment(Qt.AlignCenter)
                    images_layout.addWidget(more_label)
                
                images_layout.addStretch()
                stats_row.addLayout(images_layout)
            
            # Show text count for non-image attachments
            if non_image_attachments:
                attachments_label = QLabel(f"📎 {len(non_image_attachments)} files", self)
                attachments_label.setObjectName("TaskAttachments")
                stats_row.addWidget(attachments_label)
            elif not image_attachments:
                # Fallback: show count if no images detected
                attachments_label = QLabel(f"📎 {len(self._task.attachments)} attachments", self)
                attachments_label.setObjectName("TaskAttachments")
                stats_row.addWidget(attachments_label)

        stats_row.addStretch()
        main_layout.addLayout(stats_row)

        # ---------------- Tags row ----------------
        if self._task.tags:
            tags_layout = QHBoxLayout()
            tags_layout.setContentsMargins(0, 0, 0, 0)
            tags_layout.setSpacing(6)

            for tag in self._task.tags:
                tag_label = QLabel(str(tag.tag_name), self)
                tag_label.setObjectName("TaskTag")
                tag_label.setAlignment(Qt.AlignCenter)
                tags_layout.addWidget(tag_label)

            tags_layout.addStretch()
            main_layout.addLayout(tags_layout)

    def _calculate_progress(self) -> float:
        """Calculate progress based on status, or from subtasks if available."""
        # First, check if progress should be based on status
        status = getattr(self._task, "status", "backlog")
        # Map old "review" status to "in_progress" for backward compatibility
        if status == "review":
            status = "in_progress"
        
        status_progress_map = {
            "backlog": 0.0,
            "in_progress": 50.0,
            "completed": 100.0,
        }
        
        # If task is completed, always show 100%
        if status == "completed":
            return 100.0
        
        # Get the maximum progress allowed for this status
        max_progress_for_status = status_progress_map.get(status, 0.0)
        
        # If there are subtasks, calculate from them but cap at status progress
        if self._task.subtasks:
            total = len(self._task.subtasks)
            completed = sum(1 for st in self._task.subtasks if getattr(st, "completed", False))
            subtask_progress = (completed / total * 100.0) if total > 0 else 0.0
            # Cap subtask progress at the maximum allowed for this status
            # This ensures in_progress tasks never show more than 50% even if all subtasks are done
            return min(subtask_progress, max_progress_for_status)
        
        # Otherwise, use saved task.progress from database if it exists, otherwise use status-based progress
        task_progress = float(getattr(self._task, "progress", 0.0) or 0.0)
        
        # If we have saved progress, use it (capped by status)
        # This ensures progress persists even if subtasks change
        if task_progress > 0:
            return min(task_progress, max_progress_for_status)
        
        # If no saved progress, use status-based default
        return max_progress_for_status
    
    def _get_progress_bar_color(self) -> str:
        """Get the progress bar color based on task status."""
        status = getattr(self._task, "status", "backlog")
        # Map old "review" status to "in_progress" for backward compatibility
        if status == "review":
            status = "in_progress"
        
        color_map = {
            "backlog": "#94A3B8",      # Gray for backlog
            "in_progress": "#3B82F6",    # Blue for in progress
            "completed": "#10B981",     # Green for completed
        }
        return color_map.get(status, "#94A3B8")

    def _is_image_file(self, file_path: str) -> bool:
        """Check if a file is an image based on its extension."""
        image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}
        path_obj = Path(file_path)
        return path_obj.suffix.lower() in image_extensions

    def _create_image_thumbnail(self, attachment) -> QLabel | None:
        """Create a thumbnail label for an image attachment."""
        file_path = Path(attachment.file_path)
        
        # Check if file exists
        if not file_path.exists():
            return None
        
        try:
            # Load and scale the image
            pixmap = QPixmap(str(file_path))
            if pixmap.isNull():
                return None
            
            # Scale to thumbnail size (40x40 pixels)
            thumbnail_size = QSize(40, 40)
            scaled_pixmap = pixmap.scaled(
                thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Create label with the thumbnail
            thumbnail_label = QLabel(self)
            thumbnail_label.setPixmap(scaled_pixmap)
            thumbnail_label.setFixedSize(40, 40)
            thumbnail_label.setObjectName("TaskAttachmentThumbnail")
            thumbnail_label.setAlignment(Qt.AlignCenter)
            thumbnail_label.setStyleSheet("""
                QLabel#TaskAttachmentThumbnail {
                    border: 1px solid #E5E7EB;
                    border-radius: 4px;
                    background-color: #F9FAFB;
                }
            """)
            thumbnail_label.setCursor(Qt.PointingHandCursor)
            thumbnail_label.setToolTip(attachment.file_name)
            
            return thumbnail_label
        except Exception:
            # If image loading fails, return None
            return None

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for clicking and starting drag."""
        if event.button() == Qt.LeftButton:
            # Store the position for drag detection
            self._drag_start_position = event.position().toPoint()
            # Store press time for double-click detection
            self._press_time = event.timestamp()
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click to edit task."""
        if event.button() == Qt.LeftButton:
            # Emit clicked signal for double-click (will open edit dialog)
            self.clicked.emit(self._task.id)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move to initiate drag-and-drop."""
        if not (event.buttons() & Qt.LeftButton):
            return
        
        if not hasattr(self, "_drag_start_position"):
            return
        
        # Check if mouse has moved enough to start a drag
        if (event.position().toPoint() - self._drag_start_position).manhattanLength() < 10:
            return
        
        # Create drag object
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self._task.id))
        drag.setMimeData(mime_data)
        
        # Create a pixmap of the card for drag preview
        pixmap = self.grab()
        # Make it semi-transparent to show it's being dragged
        transparent_pixmap = QPixmap(pixmap.size())
        transparent_pixmap.fill(Qt.transparent)
        painter = QPainter(transparent_pixmap)
        painter.setOpacity(0.8)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        
        drag.setPixmap(transparent_pixmap)
        drag.setHotSpot(event.position().toPoint())
        
        # Start drag
        result = drag.exec(Qt.MoveAction)
        
        # Clean up drag start position
        if hasattr(self, "_drag_start_position"):
            delattr(self, "_drag_start_position")

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release - emit clicked if it was a click, not a drag."""
        if event.button() == Qt.LeftButton:
            if hasattr(self, "_drag_start_position"):
                # If mouse didn't move much, it was a click
                if (event.position().toPoint() - self._drag_start_position).manhattanLength() < 10:
                    self.clicked.emit(self._task.id)
                delattr(self, "_drag_start_position")
        super().mouseReleaseEvent(event)

    def get_task(self) -> TaskModel:
        """Return the underlying task model."""
        return self._task

    def update_task(self, task: TaskModel) -> None:
        """Update the task model and refresh the UI."""
        self._task = task
        
        # Clear existing layout and widgets properly
        existing_layout = self.layout()
        if existing_layout:
            # Remove all widgets and nested layouts
            while existing_layout.count():
                item = existing_layout.takeAt(0)
                if item.widget():
                    widget = item.widget()
                    widget.setParent(None)
                    widget.deleteLater()
                elif item.layout():
                    nested_layout = item.layout()
                    while nested_layout.count():
                        nested_item = nested_layout.takeAt(0)
                        if nested_item.widget():
                            nested_item.widget().setParent(None)
                            nested_item.widget().deleteLater()
            
            # Remove the layout from the widget
            existing_layout.setParent(None)
            existing_layout.deleteLater()
        
        # Rebuild UI with new task data
        self._build_ui()
        self._apply_inline_defaults()
        
        # Update progress bar color after rebuild
        if hasattr(self, "_progress_bar"):
            progress_color = self._get_progress_bar_color()
            self._progress_bar.setStyleSheet(f"""
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
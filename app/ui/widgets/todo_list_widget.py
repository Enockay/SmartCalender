from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Dict

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass
class TodoEvent:
    text: str
    color: str = "#3B82F6"          # solid hex or "linear:#RRGGBB:#RRGGBB"
    text_color: str = "#FFFFFF"


class PreserveColorDelegate(QStyledItemDelegate):
    """Custom delegate that preserves item background colors even when selected."""
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        # Get the item's background color from the model
        bg_data = index.data(Qt.BackgroundRole)
        
        # In PySide6, index.data() can return QBrush directly or None
        if bg_data is not None:
            # Check if it's already a QBrush
            if isinstance(bg_data, QBrush):
                bg_brush = bg_data
            else:
                # Try to convert if it's something else
                bg_brush = QBrush(bg_data) if bg_data else None
            
            # If we have a valid brush with a color, use it instead of selection
            if bg_brush and isinstance(bg_brush, QBrush) and bg_brush.style() != Qt.NoBrush:
                # Paint the custom background
                painter.fillRect(option.rect, bg_brush)
                # Remove selected state so selection highlight doesn't override
                option.state &= ~QStyle.State_Selected
        
        # Call parent paint to draw text and other elements
        super().paint(painter, option, index)


class TodoListWidget(QWidget):
    """Modern day schedule / todo list with strong hour visibility and colored meeting rows."""

    eventClicked = Signal(object, str)  # time, text

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TodoListRoot")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._sheet = QFrame(self)
        self._sheet.setObjectName("TodoSheet")

        sheet_layout = QVBoxLayout(self._sheet)
        sheet_layout.setContentsMargins(0, 0, 0, 0)
        sheet_layout.setSpacing(0)

        self._table = QTableWidget(self._sheet)
        self._table.setObjectName("TodoListTable")
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Time", "Plan"])
        self._table.setRowCount(24)

        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setVisible(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 80)

        self._table.setShowGrid(True)
        self._table.setGridStyle(Qt.SolidLine)
        self._table.setAlternatingRowColors(False)
        self._table.setWordWrap(True)
        self._table.setMouseTracking(True)

        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setCornerButtonEnabled(False)
        
        # Use custom delegate to preserve background colors when selected
        self._table.setItemDelegate(PreserveColorDelegate(self._table))

        self._table.cellDoubleClicked.connect(self._on_cell_clicked)
        self._table.cellClicked.connect(self._on_cell_clicked)
        # Reapply event colors when selection changes to preserve background colors
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        sheet_layout.addWidget(self._table)
        outer_layout.addWidget(self._sheet)

        self._row_times: list[time] = []
        self._events: Dict[time, TodoEvent] = {}
        self._last_selected_rows: set[int] = set()  # Track previously selected rows

        self._build_rows()
        self._load_qss()
        self._refresh_rows()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._highlight_current_time)
        self._timer.start(60_000)

    def _build_rows(self) -> None:
        time_font = QFont("Segoe UI", 10)
        time_font.setBold(True)

        event_font = QFont("Segoe UI", 11)
        event_font.setBold(False)

        for row in range(24):
            t = time(hour=row, minute=0)
            self._row_times.append(t)

            time_item = QTableWidgetItem(t.strftime("%H:%M"))
            time_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            time_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            time_item.setFont(time_font)

            event_item = QTableWidgetItem("")
            event_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            event_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            event_item.setFont(event_font)

            self._table.setItem(row, 0, time_item)
            self._table.setItem(row, 1, event_item)
            self._table.setRowHeight(row, 40)

    def _load_qss(self) -> None:
        root = Path(__file__).resolve().parents[2]
        qss_path = root / "ui" / "resources" / "qss" / "todo_list.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    def set_events(self, events: Dict[time, TodoEvent | str]) -> None:
        """Set events for given hours. Supports TodoEvent or plain string."""
        normalized: Dict[time, TodoEvent] = {}

        for t, value in events.items():
            if isinstance(value, TodoEvent):
                normalized[t] = TodoEvent(
                    text=value.text,
                    color=value.color or "#3B82F6",
                    text_color=value.text_color or "#FFFFFF",
                )
            else:
                normalized[t] = TodoEvent(text=str(value))

        self._events = normalized
        self._refresh_rows()
        # Auto-scroll to the first meeting after a short delay (allow table to lay out)
        QTimer.singleShot(50, self._scroll_to_first_event)

    def _scroll_to_first_event(self) -> None:
        """Scroll the table so the first meeting/event row is visible near the top."""
        if not self._events:
            # No events — scroll to the current hour instead
            current_hour = datetime.now().hour
            target_row = max(0, current_hour - 1)
        else:
            # Find the earliest event hour
            earliest = min(self._events.keys(), key=lambda t: t.hour)
            target_row = max(0, earliest.hour - 1)  # show one row above for context

        item = self._table.item(target_row, 0)
        if item:
            self._table.scrollToItem(item, QAbstractItemView.PositionAtTop)

    def _clear_row_style(self, row: int) -> None:
        time_item = self._table.item(row, 0)
        event_item = self._table.item(row, 1)

        if not time_item or not event_item:
            return

        time_item.setData(Qt.BackgroundRole, None)
        event_item.setData(Qt.BackgroundRole, None)
        time_item.setData(Qt.ForegroundRole, None)
        event_item.setData(Qt.ForegroundRole, None)

    def _base_empty_row_style(self, row: int, is_past: bool) -> None:
        time_item = self._table.item(row, 0)
        event_item = self._table.item(row, 1)

        if not time_item or not event_item:
            return

        # Soft gradient for the time column background to give it a lifted,
        # "pill-like" feel, with slightly lighter tone for future hours.
        if is_past:
            time_fg = QColor("#94A3B8")
            event_fg = QColor("#94A3B8")
            grad = QLinearGradient(0, 0, 1, 0)
            grad.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
            grad.setColorAt(0.0, QColor("#CBD5E1"))   # darker on the left
            grad.setColorAt(1.0, QColor("#E5E7EB"))   # lighter on the right
            time_bg = QBrush(grad)
            event_bg = QColor("#F8FAFC")
        else:
            time_fg = QColor("#475569")
            event_fg = QColor("#334155")
            grad = QLinearGradient(0, 0, 1, 0)
            grad.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
            grad.setColorAt(0.0, QColor("#E2E8F0"))
            grad.setColorAt(1.0, QColor("#F8FAFC"))
            time_bg = QBrush(grad)
            event_bg = QColor("#FFFFFF")

        time_item.setForeground(QBrush(time_fg))
        event_item.setForeground(QBrush(event_fg))
        time_item.setBackground(time_bg)
        event_item.setBackground(QBrush(event_bg))

    def _event_brush(self, raw: str) -> QBrush:
        if isinstance(raw, str) and raw.startswith("linear:"):
            try:
                _, c1, c2 = raw.split(":")
                grad = QLinearGradient(0, 0, 1, 0)
                grad.setCoordinateMode(QLinearGradient.ObjectBoundingMode)
                grad.setColorAt(0.0, QColor(c1))
                grad.setColorAt(1.0, QColor(c2))
                return QBrush(grad)
            except Exception:
                return QBrush(QColor("#3B82F6"))
        return QBrush(QColor(raw))

    def _apply_event_row_style(self, row: int, event: TodoEvent) -> None:
        time_item = self._table.item(row, 0)
        event_item = self._table.item(row, 1)
        if not time_item or not event_item:
            return
        # Use the event's configured colors; support solid or linear gradients.
        row_fg = QColor(event.text_color or "#FFFFFF")
        row_bg = self._event_brush(event.color or "#3B82F6")

        time_item.setForeground(QBrush(row_fg))
        event_item.setForeground(QBrush(row_fg))
        time_item.setBackground(row_bg)
        event_item.setBackground(row_bg)
        
        # Force update to ensure colors are applied
        time_item.setData(Qt.BackgroundRole, row_bg)
        event_item.setData(Qt.BackgroundRole, row_bg)
        self._table.update()

    def _refresh_rows(self) -> None:
        current_hour = datetime.now().hour

        # Reset any previous spans so we can recompute them from scratch.
        # This ensures that when meetings change, old spans don't linger.
        if self._table is not None:
            self._table.clearSpans()

        for row, row_time in enumerate(self._row_times):
            time_item = self._table.item(row, 0)
            event_item = self._table.item(row, 1)

            if not time_item or not event_item:
                continue

            event = self._events.get(row_time)

            time_item.setText(row_time.strftime("%H:%M"))
            if event:
                # Prefix with a subtle reminder bell to indicate this slot
                # has an associated meeting/reminder.
                event_item.setText(f"  🔔 {event.text}")
            else:
                event_item.setText("")

            self._clear_row_style(row)

            if event:
                self._apply_event_row_style(row, event)
            else:
                self._base_empty_row_style(row, is_past=row_time.hour < current_hour)

        # After basic row styling, create vertical spans in the "Plan" column
        # for multi-hour meetings so they appear as a single block, similar
        # to the week view. We span only column 1 so the time column remains
        # visible and unmerged.
        current_group_start: int | None = None
        current_group_event: TodoEvent | None = None

        def _finalize_group(end_row_exclusive: int) -> None:
            nonlocal current_group_start, current_group_event
            if current_group_start is None:
                return
            span_rows = end_row_exclusive - current_group_start
            if span_rows > 1:
                # Span just the "Plan" column so consecutive hours for the
                # same meeting appear as a single block. We no longer repaint
                # backgrounds here; per-row styling from _apply_event_row_style
                # should remain in effect.
                self._table.setSpan(current_group_start, 1, span_rows, 1)
                # Only show the title on the first row of the span so the text
                # doesn't repeat inside the merged block.
                for r in range(current_group_start + 1, end_row_exclusive):
                    event_item = self._table.item(r, 1)
                    if event_item:
                        event_item.setText("")
            current_group_start = None
            current_group_event = None

        for row, row_time in enumerate(self._row_times):
            event = self._events.get(row_time)

            if not event:
                # End any ongoing span when there's no event in this row.
                _finalize_group(row)
                continue

            if (
                current_group_event is not None
                and event.text == current_group_event.text
                and event.color == current_group_event.color
                and event.text_color == current_group_event.text_color
            ):
                # Continue existing group
                continue

            # Start a new group after finishing the previous one.
            _finalize_group(row)
            current_group_start = row
            current_group_event = event

        # Final group that may run to the last row.
        _finalize_group(len(self._row_times))

        self._highlight_current_time()

    def _highlight_current_time(self) -> None:
        current_hour = datetime.now().hour

        for row, row_time in enumerate(self._row_times):
            time_item = self._table.item(row, 0)
            event_item = self._table.item(row, 1)

            if not time_item or not event_item:
                continue

            event = self._events.get(row_time)

            if row_time.hour == current_hour:
                if event:
                    # Keep event color, just strengthen the time cell slightly.
                    time_font = time_item.font()
                    time_font.setBold(True)
                    time_font.setItalic(False)
                    time_item.setFont(time_font)
                else:
                    time_item.setForeground(QBrush(QColor("#1D4ED8")))
                    time_item.setBackground(QBrush(QColor("#DBEAFE")))
                    event_item.setForeground(QBrush(QColor("#0F172A")))
                    event_item.setBackground(QBrush(QColor("#EFF6FF")))
            else:
                if not event:
                    is_past = row_time.hour < current_hour
                    self._base_empty_row_style(row, is_past=is_past)

    def clear_events(self) -> None:
        self._events.clear()
        self._refresh_rows()

    def _on_selection_changed(self) -> None:
        """Reapply event colors when selection changes to preserve background colors."""
        # Use a timer to ensure selection styling is applied first, then we override it
        QTimer.singleShot(10, self._reapply_selected_event_colors)
    
    def _reapply_selected_event_colors(self) -> None:
        """Reapply event colors for currently selected rows and previously selected rows."""
        current_selected_rows = set()
        for item in self._table.selectedItems():
            current_selected_rows.add(item.row())
        
        # Reapply colors for both current selection and previous selection
        rows_to_update = current_selected_rows | self._last_selected_rows
        
        # Reapply event styling for rows that have events
        for row in rows_to_update:
            if row < len(self._row_times):
                row_time = self._row_times[row]
                event = self._events.get(row_time)
                if event:
                    # Reapply the event colors to override selection styling
                    self._apply_event_row_style(row, event)
                    # Force update of the specific cells
                    self._table.update(self._table.visualItemRect(self._table.item(row, 0)))
                    self._table.update(self._table.visualItemRect(self._table.item(row, 1)))
                else:
                    # If no event, reapply base styling
                    current_hour = datetime.now().hour
                    is_past = row_time.hour < current_hour
                    self._base_empty_row_style(row, is_past)
        
        # Update the last selected rows for next time
        self._last_selected_rows = current_selected_rows.copy()
        
        # Force a full repaint
        self._table.viewport().update()

    def _on_cell_clicked(self, row: int, column: int) -> None:
        row_time = self._row_times[row]
        event = self._events.get(row_time)
        text = event.text if event else ""
        # Immediately reapply event colors after click to preserve background
        QTimer.singleShot(10, self._reapply_selected_event_colors)
        self.eventClicked.emit(row_time, text)
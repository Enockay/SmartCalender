"""Three-screen welcome tour shown on first launch (UX review §4.6)."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_MOD = "⌘" if sys.platform == "darwin" else "Ctrl"

_PAGES = [
    (
        "Your day, your calendar",
        "Today shows what is on your plate right now. Calendar holds your schedule: "
        "switch between Day, Week, Month and Year at the top.",
        [
            ("Today", "events, tasks due and your next reminder"),
            ("Calendar", "Day · Week · Month · Year  (keys D, W, M, Y)"),
            ("Tasks", "a board from Backlog to Done"),
            ("Reminders", "everything SmartCalender will nudge you about"),
        ],
    ),
    (
        "Add anything in one line",
        f"Type into the quick add bar at the top (or press {_MOD}+K / N) and SmartCalender "
        "works out whether it is an event, a task or a reminder.",
        [
            ("Lunch with Ana Friday 1pm", "creates an event"),
            ("Call the bank tomorrow", "creates a task"),
            ("Remind me to pay rent on the 1st every month", "creates a repeating reminder"),
        ],
    ),
    (
        "Reminders that reach you",
        "SmartCalender shows a notification on your computer before each event or reminder. "
        "Keep the app open (minimised is fine) to receive them. You can change the default "
        "lead time and sounds in Settings.",
        [
            ("Snooze", "push a reminder back by a few minutes"),
            ("Overdue", "anything you missed is collected in one place"),
        ],
    ),
]

_STYLE = """
QDialog#WelcomeDialog { background: #FFFFFF; }
QLabel#WelcomeStep { color: #047857; font-size: 12px; font-weight: 600; letter-spacing: 1px; }
QLabel#WelcomeTitle { color: #111827; font-size: 22px; font-weight: 700; }
QLabel#WelcomeBody { color: #374151; font-size: 14px; }
QFrame#WelcomeRow { background: #F3F4F6; border-radius: 10px; }
QLabel#WelcomeRowTitle { color: #111827; font-size: 14px; font-weight: 600; }
QLabel#WelcomeRowBody { color: #4B5563; font-size: 13px; }
QPushButton#WelcomePrimary {
    background: #10B981; color: white; border: none; border-radius: 10px;
    padding: 10px 22px; font-size: 14px; font-weight: 600;
}
QPushButton#WelcomePrimary:hover { background: #059669; }
QPushButton#WelcomeSecondary {
    background: transparent; color: #374151; border: 1px solid #E5E7EB; border-radius: 10px;
    padding: 10px 18px; font-size: 14px;
}
QPushButton#WelcomeSecondary:hover { background: #F3F4F6; }
QPushButton#WelcomeSkip { background: transparent; border: none; color: #6B7280; font-size: 13px; }
QPushButton#WelcomeSkip:hover { color: #111827; }
QCheckBox { color: #111827; font-size: 14px; }
QLabel#WelcomeDot { background: #E5E7EB; border-radius: 4px; }
QLabel#WelcomeDot[active="true"] { background: #10B981; }
"""


class WelcomeDialog(QDialog):
    """Returns Accepted when finished; `load_sample_data` says whether to add sample data."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WelcomeDialog")
        self.setWindowTitle("Welcome to SmartCalender")
        self.setModal(True)
        self.setFixedSize(560, 500)
        self.setStyleSheet(_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)

        top = QHBoxLayout()
        self._step = QLabel("", self)
        self._step.setObjectName("WelcomeStep")
        top.addWidget(self._step)
        top.addStretch()
        skip = QPushButton("Skip tour", self)
        skip.setObjectName("WelcomeSkip")
        skip.setCursor(Qt.PointingHandCursor)
        skip.clicked.connect(self.accept)
        top.addWidget(skip)
        root.addLayout(top)

        self._pages = QStackedWidget(self)
        for i, (title, body, rows) in enumerate(_PAGES):
            self._pages.addWidget(self._page(title, body, rows, last=i == len(_PAGES) - 1))
        root.addWidget(self._pages, 1)

        bottom = QHBoxLayout()
        self._dots: list[QLabel] = []
        for _ in _PAGES:
            d = QLabel(self)
            d.setObjectName("WelcomeDot")
            d.setFixedSize(8, 8)
            self._dots.append(d)
            bottom.addWidget(d)
        bottom.addStretch()
        self._back = QPushButton("Back", self)
        self._back.setObjectName("WelcomeSecondary")
        self._back.setCursor(Qt.PointingHandCursor)
        self._back.clicked.connect(lambda: self._go(self._pages.currentIndex() - 1))
        bottom.addWidget(self._back)
        self._next = QPushButton("Next", self)
        self._next.setObjectName("WelcomePrimary")
        self._next.setCursor(Qt.PointingHandCursor)
        self._next.setDefault(True)
        self._next.clicked.connect(self._on_next)
        bottom.addWidget(self._next)
        root.addLayout(bottom)

        self._go(0)

    @property
    def load_sample_data(self) -> bool:
        return self._sample_check.isChecked()

    def _page(self, title: str, body: str, rows: list[tuple[str, str]], last: bool) -> QWidget:
        page = QWidget(self)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        t = QLabel(title, page)
        t.setObjectName("WelcomeTitle")
        t.setWordWrap(True)
        lay.addWidget(t)
        b = QLabel(body, page)
        b.setObjectName("WelcomeBody")
        b.setWordWrap(True)
        lay.addWidget(b)
        for head, text in rows:
            row = QFrame(page)
            row.setObjectName("WelcomeRow")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(14, 10, 14, 10)
            rl.setSpacing(2)
            h = QLabel(head, row)
            h.setObjectName("WelcomeRowTitle")
            h.setWordWrap(True)
            rl.addWidget(h)
            tx = QLabel(text, row)
            tx.setObjectName("WelcomeRowBody")
            tx.setWordWrap(True)
            rl.addWidget(tx)
            lay.addWidget(row)
        lay.addStretch()
        if last:
            self._sample_check = QCheckBox("Fill my calendar with a sample week so I can explore", page)
            self._sample_check.setCursor(Qt.PointingHandCursor)
            lay.addWidget(self._sample_check)
            hint = QLabel("You can remove the sample data any time from Settings.", page)
            hint.setObjectName("WelcomeRowBody")
            lay.addWidget(hint)
        return page

    def _go(self, index: int) -> None:
        index = max(0, min(index, self._pages.count() - 1))
        self._pages.setCurrentIndex(index)
        last = index == self._pages.count() - 1
        self._step.setText(f"STEP {index + 1} OF {self._pages.count()}")
        self._back.setVisible(index > 0)
        self._next.setText("Get started" if last else "Next")
        for i, d in enumerate(self._dots):
            d.setProperty("active", "true" if i == index else "false")
            d.style().unpolish(d)
            d.style().polish(d)

    def _on_next(self) -> None:
        if self._pages.currentIndex() == self._pages.count() - 1:
            self.accept()
        else:
            self._go(self._pages.currentIndex() + 1)

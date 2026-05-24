from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from apiclient.models.request import HttpResponse


class ResponseViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.summary_label = QLabel("No response yet")
        self.summary_label.setTextInteractionFlags(
            self.summary_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])
        self.headers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.body_view = QPlainTextEdit()
        self.body_view.setReadOnly(True)
        self.body_view.setPlaceholderText("Response body")

        self.tabs = QTabWidget()
        self.tabs.addTab(self.headers_table, "Headers")
        self.tabs.addTab(self.body_view, "Body")

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.tabs)

    def show_response(self, response: HttpResponse) -> None:
        if response.error:
            self.summary_label.setText(f"Error · {response.elapsed_ms:.0f} ms")
            self._set_headers({})
            self.body_view.setPlainText(response.error)
            return

        self.summary_label.setText(
            f"{response.status_code} {response.reason} · {response.elapsed_ms:.0f} ms"
        )
        self._set_headers(response.headers)
        self.body_view.setPlainText(response.body)

    def clear(self) -> None:
        self.summary_label.setText("No response yet")
        self._set_headers({})
        self.body_view.clear()

    def _set_headers(self, headers: dict[str, str]) -> None:
        self.headers_table.setRowCount(0)
        for key, value in headers.items():
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))

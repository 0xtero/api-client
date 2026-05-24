from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from apiclient.models.request import BodyMode, HttpRequest

HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class RequestEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False

        self.method_combo = QComboBox()
        self.method_combo.addItems(HTTP_METHODS)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://api.example.com/path")

        url_row = QHBoxLayout()
        url_row.addWidget(self.method_combo)
        url_row.addWidget(self.url_input, stretch=1)

        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        headers_buttons = QHBoxLayout()
        add_header_btn = QPushButton("Add header")
        remove_header_btn = QPushButton("Remove header")
        add_header_btn.clicked.connect(self._add_header_row)
        remove_header_btn.clicked.connect(self._remove_header_row)
        headers_buttons.addWidget(add_header_btn)
        headers_buttons.addWidget(remove_header_btn)
        headers_buttons.addStretch()

        headers_widget = QWidget()
        headers_layout = QVBoxLayout(headers_widget)
        headers_layout.setContentsMargins(0, 0, 0, 0)
        headers_layout.addWidget(self.headers_table)
        headers_layout.addLayout(headers_buttons)

        self.body_mode_combo = QComboBox()
        self.body_mode_combo.addItems(["none", "json", "text"])

        self.body_editor = QPlainTextEdit()
        self.body_editor.setPlaceholderText("Request body")

        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.body_mode_combo)
        body_layout.addWidget(self.body_editor)

        self.tabs = QTabWidget()
        self.tabs.addTab(headers_widget, "Headers")
        self.tabs.addTab(body_widget, "Body")

        layout = QVBoxLayout(self)
        layout.addLayout(url_row)
        layout.addWidget(self.tabs)

        self.method_combo.currentTextChanged.connect(self._emit_changed)
        self.url_input.textChanged.connect(self._emit_changed)
        self.body_mode_combo.currentTextChanged.connect(self._on_body_mode_changed)
        self.body_editor.textChanged.connect(self._emit_changed)
        self.headers_table.itemChanged.connect(self._emit_changed)

        self._on_body_mode_changed(self.body_mode_combo.currentText())

    def load_request(self, request: HttpRequest) -> None:
        self._loading = True
        try:
            self.method_combo.setCurrentText(request.method)
            self.url_input.setText(request.url)
            self.body_mode_combo.setCurrentText(request.body.mode.value)
            self.body_editor.setPlainText(request.body.content)
            self._set_headers(request.headers)
            self._on_body_mode_changed(request.body.mode.value)
        finally:
            self._loading = False

    def to_request(self, name: str) -> HttpRequest:
        headers = self._collect_headers()
        mode = BodyMode(self.body_mode_combo.currentText())
        return HttpRequest(
            name=name,
            method=self.method_combo.currentText(),
            url=self.url_input.text().strip(),
            headers=headers,
            body={"mode": mode, "content": self.body_editor.toPlainText()},
        )

    def _emit_changed(self, *_args: object) -> None:
        if not self._loading:
            self.changed.emit()

    def _on_body_mode_changed(self, mode: str) -> None:
        enabled = mode != BodyMode.NONE.value
        self.body_editor.setEnabled(enabled)
        self._emit_changed()

    def _set_headers(self, headers: dict[str, str]) -> None:
        self.headers_table.blockSignals(True)
        self.headers_table.setRowCount(0)
        for key, value in headers.items():
            self._append_header_row(key, value)
        if self.headers_table.rowCount() == 0:
            self._append_header_row("", "")
        self.headers_table.blockSignals(False)

    def _collect_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        for row in range(self.headers_table.rowCount()):
            key_item = self.headers_table.item(row, 0)
            value_item = self.headers_table.item(row, 1)
            key = (key_item.text() if key_item else "").strip()
            value = value_item.text() if value_item else ""
            if key:
                headers[key] = value
        return headers

    def _append_header_row(self, key: str, value: str) -> None:
        row = self.headers_table.rowCount()
        self.headers_table.insertRow(row)
        self.headers_table.setItem(row, 0, QTableWidgetItem(key))
        self.headers_table.setItem(row, 1, QTableWidgetItem(value))

    def _add_header_row(self) -> None:
        self._append_header_row("", "")
        self._emit_changed()

    def _remove_header_row(self) -> None:
        row = self.headers_table.currentRow()
        if row >= 0:
            self.headers_table.removeRow(row)
        if self.headers_table.rowCount() == 0:
            self._append_header_row("", "")
        self._emit_changed()

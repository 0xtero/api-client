from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from apiclient.models.request import ApiKeyIn, AuthType, BodyMode, HttpAuth, HttpRequest

HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
AUTH_TYPES = [
    ("None", AuthType.NONE),
    ("Bearer token", AuthType.BEARER),
    ("Basic auth", AuthType.BASIC),
    ("API key", AuthType.API_KEY),
]
API_KEY_LOCATIONS = [
    ("Header", ApiKeyIn.HEADER),
    ("Query param", ApiKeyIn.QUERY),
]


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

        self.auth_type_combo = QComboBox()
        for label, _auth_type in AUTH_TYPES:
            self.auth_type_combo.addItem(label)

        self.auth_none_label = QLabel("No authentication configured for this request.")
        self.auth_none_label.setWordWrap(True)

        self.bearer_token_input = QLineEdit()
        self.bearer_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.bearer_token_input.setPlaceholderText("Token")

        bearer_form = QFormLayout()
        bearer_form.addRow("Token", self.bearer_token_input)
        bearer_widget = QWidget()
        bearer_widget.setLayout(bearer_form)

        self.basic_username_input = QLineEdit()
        self.basic_username_input.setPlaceholderText("Username")
        self.basic_password_input = QLineEdit()
        self.basic_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.basic_password_input.setPlaceholderText("Password")

        basic_form = QFormLayout()
        basic_form.addRow("Username", self.basic_username_input)
        basic_form.addRow("Password", self.basic_password_input)
        basic_widget = QWidget()
        basic_widget.setLayout(basic_form)

        self.api_key_name_input = QLineEdit()
        self.api_key_name_input.setPlaceholderText("X-API-Key")
        self.api_key_value_input = QLineEdit()
        self.api_key_value_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_value_input.setPlaceholderText("Value")
        self.api_key_in_combo = QComboBox()
        for label, _location in API_KEY_LOCATIONS:
            self.api_key_in_combo.addItem(label)

        api_key_form = QFormLayout()
        api_key_form.addRow("Key name", self.api_key_name_input)
        api_key_form.addRow("Key value", self.api_key_value_input)
        api_key_form.addRow("Add to", self.api_key_in_combo)
        api_key_widget = QWidget()
        api_key_widget.setLayout(api_key_form)

        self.auth_stack = QStackedWidget()
        self.auth_stack.addWidget(self.auth_none_label)
        self.auth_stack.addWidget(bearer_widget)
        self.auth_stack.addWidget(basic_widget)
        self.auth_stack.addWidget(api_key_widget)

        auth_layout = QVBoxLayout()
        auth_layout.addWidget(self.auth_type_combo)
        auth_layout.addWidget(self.auth_stack)
        auth_widget = QWidget()
        auth_widget.setLayout(auth_layout)

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
        self.tabs.addTab(auth_widget, "Auth")
        self.tabs.addTab(headers_widget, "Headers")
        self.tabs.addTab(body_widget, "Body")

        layout = QVBoxLayout(self)
        layout.addLayout(url_row)
        layout.addWidget(self.tabs)

        self.method_combo.currentTextChanged.connect(self._emit_changed)
        self.url_input.textChanged.connect(self._emit_changed)
        self.auth_type_combo.currentIndexChanged.connect(self._on_auth_type_changed)
        self.bearer_token_input.textChanged.connect(self._emit_changed)
        self.basic_username_input.textChanged.connect(self._emit_changed)
        self.basic_password_input.textChanged.connect(self._emit_changed)
        self.api_key_name_input.textChanged.connect(self._emit_changed)
        self.api_key_value_input.textChanged.connect(self._emit_changed)
        self.api_key_in_combo.currentIndexChanged.connect(self._emit_changed)
        self.body_mode_combo.currentTextChanged.connect(self._on_body_mode_changed)
        self.body_editor.textChanged.connect(self._emit_changed)
        self.headers_table.itemChanged.connect(self._emit_changed)

        self._on_body_mode_changed(self.body_mode_combo.currentText())
        self._on_auth_type_changed(self.auth_type_combo.currentIndex())

    def load_request(self, request: HttpRequest) -> None:
        self._loading = True
        try:
            self.method_combo.setCurrentText(request.method)
            self.url_input.setText(request.url)
            self.body_mode_combo.setCurrentText(request.body.mode.value)
            self.body_editor.setPlainText(request.body.content)
            self._set_headers(request.headers)
            self._set_auth(request.auth)
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
            auth=self._collect_auth(),
        )

    def _emit_changed(self, *_args: object) -> None:
        if not self._loading:
            self.changed.emit()

    def _on_body_mode_changed(self, mode: str) -> None:
        enabled = mode != BodyMode.NONE.value
        self.body_editor.setEnabled(enabled)
        self._emit_changed()

    def _on_auth_type_changed(self, index: int) -> None:
        self.auth_stack.setCurrentIndex(index)
        self._emit_changed()

    def _set_auth(self, auth: HttpAuth) -> None:
        type_index = next(
            (i for i, (_, auth_type) in enumerate(AUTH_TYPES) if auth_type == auth.type),
            0,
        )
        self.auth_type_combo.setCurrentIndex(type_index)
        self.bearer_token_input.setText(auth.token)
        self.basic_username_input.setText(auth.username)
        self.basic_password_input.setText(auth.password)
        self.api_key_name_input.setText(auth.key_name)
        self.api_key_value_input.setText(auth.key_value)
        key_in_index = next(
            (i for i, (_, location) in enumerate(API_KEY_LOCATIONS) if location == auth.key_in),
            0,
        )
        self.api_key_in_combo.setCurrentIndex(key_in_index)
        self.auth_stack.setCurrentIndex(type_index)

    def _collect_auth(self) -> HttpAuth:
        auth_type = AUTH_TYPES[self.auth_type_combo.currentIndex()][1]
        key_in = API_KEY_LOCATIONS[self.api_key_in_combo.currentIndex()][1]
        return HttpAuth(
            type=auth_type,
            token=self.bearer_token_input.text(),
            username=self.basic_username_input.text(),
            password=self.basic_password_input.text(),
            key_name=self.api_key_name_input.text(),
            key_value=self.api_key_value_input.text(),
            key_in=key_in,
        )

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

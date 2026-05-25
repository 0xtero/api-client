from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from apiclient.http.oauth import fetch_oauth_token
from apiclient.http.url_builder import extract_path_param_names
from apiclient.models.request import (
    ApiKeyIn,
    AuthType,
    DEFAULT_OAUTH_TOKEN_CONTENT_TYPE,
    HttpAuth,
    HttpRequest,
    HttpRequestSettings,
    KeyValueEntry,
    OAuthGrantType,
)
from apiclient.ui.body_editor import BodyEditor
from apiclient.ui.key_value_table import KeyValueTableWidget

HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
AUTH_TYPES = [
    ("None", AuthType.NONE),
    ("Bearer token", AuthType.BEARER),
    ("Basic auth", AuthType.BASIC),
    ("API key", AuthType.API_KEY),
    ("OAuth 2.0", AuthType.OAUTH),
]
API_KEY_LOCATIONS = [
    ("Header", ApiKeyIn.HEADER),
    ("Query param", ApiKeyIn.QUERY),
]
OAUTH_GRANT_TYPES = [
    ("Client credentials", OAuthGrantType.CLIENT_CREDENTIALS),
    ("Password", OAuthGrantType.PASSWORD),
    ("Authorization code", OAuthGrantType.AUTHORIZATION_CODE),
]
OAUTH_TOKEN_CONTENT_TYPES = [
    "application/x-www-form-urlencoded",
    "application/json",
]


def upsert_header(
    entries: list[KeyValueEntry],
    name: str,
    value: str,
) -> list[KeyValueEntry]:
    updated = False
    result: list[KeyValueEntry] = []
    for entry in entries:
        if entry.name.lower() == name.lower():
            result.append(KeyValueEntry(name=name, value=value, enabled=True))
            updated = True
        else:
            result.append(entry)
    if not updated:
        result.append(KeyValueEntry(name=name, value=value, enabled=True))
    return result


class RequestEditor(QWidget):
    changed = Signal()
    oauth_test_finished = Signal(object)

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

        self.oauth_idp_input = QLineEdit()
        self.oauth_idp_input.setPlaceholderText("https://idp.example.com/oauth/token")
        self.oauth_client_id_input = QLineEdit()
        self.oauth_client_id_input.setPlaceholderText("Client ID")
        self.oauth_client_secret_input = QLineEdit()
        self.oauth_client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.oauth_client_secret_input.setPlaceholderText("Client secret")
        self.oauth_grant_type_combo = QComboBox()
        for label, _grant_type in OAUTH_GRANT_TYPES:
            self.oauth_grant_type_combo.addItem(label)
        self.oauth_scope_input = QLineEdit()
        self.oauth_scope_input.setPlaceholderText("Optional scope")
        self.oauth_content_type_combo = QComboBox()
        self.oauth_content_type_combo.addItems(OAUTH_TOKEN_CONTENT_TYPES)
        self.oauth_username_input = QLineEdit()
        self.oauth_username_input.setPlaceholderText("Username")
        self.oauth_password_input = QLineEdit()
        self.oauth_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.oauth_password_input.setPlaceholderText("Password")
        self.oauth_username_label = QLabel("Username")
        self.oauth_password_label = QLabel("Password")
        self.oauth_access_token_input = QLineEdit()
        self.oauth_access_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.oauth_access_token_input.setPlaceholderText("Bearer access token")
        self.oauth_test_auth_button = QPushButton("Test Auth")

        oauth_form = QFormLayout()
        oauth_form.addRow("IDP endpoint", self.oauth_idp_input)
        oauth_form.addRow("Client ID", self.oauth_client_id_input)
        oauth_form.addRow("Client secret", self.oauth_client_secret_input)
        oauth_form.addRow("Grant type", self.oauth_grant_type_combo)
        oauth_form.addRow("Scope", self.oauth_scope_input)
        oauth_form.addRow("Content-Type", self.oauth_content_type_combo)
        oauth_form.addRow(self.oauth_username_label, self.oauth_username_input)
        oauth_form.addRow(self.oauth_password_label, self.oauth_password_input)
        oauth_form.addRow("Access token", self.oauth_access_token_input)
        oauth_form.addRow("", self.oauth_test_auth_button)
        oauth_widget = QWidget()
        oauth_widget.setLayout(oauth_form)

        self.auth_stack = QStackedWidget()
        self.auth_stack.addWidget(self.auth_none_label)
        self.auth_stack.addWidget(bearer_widget)
        self.auth_stack.addWidget(basic_widget)
        self.auth_stack.addWidget(api_key_widget)
        self.auth_stack.addWidget(oauth_widget)

        auth_layout = QVBoxLayout()
        auth_layout.addWidget(self.auth_type_combo)
        auth_layout.addWidget(self.auth_stack)
        auth_widget = QWidget()
        auth_widget.setLayout(auth_layout)

        self.query_params_table = KeyValueTableWidget(
            name_header="Name",
            value_header="Value",
        )

        self.path_params_table = KeyValueTableWidget(
            name_header="Name",
            value_header="Value",
        )

        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)
        query_layout.setContentsMargins(0, 0, 0, 0)
        path_label = QLabel("Path parameters")
        query_layout.addWidget(path_label)
        query_layout.addWidget(self.path_params_table)
        query_label = QLabel("Query parameters")
        query_layout.addWidget(query_label)
        query_layout.addWidget(self.query_params_table)

        self.headers_table = KeyValueTableWidget(name_header="Header", value_header="Value")

        headers_widget = QWidget()
        headers_layout = QVBoxLayout(headers_widget)
        headers_layout.setContentsMargins(0, 0, 0, 0)
        headers_layout.addWidget(self.headers_table)

        self.body_editor = BodyEditor()

        body_widget = QWidget()
        body_layout = QVBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.body_editor)

        self.follow_redirects_check = QCheckBox("Automatically follow redirects")
        self.follow_redirects_check.setChecked(True)
        self.max_redirects_spin = QSpinBox()
        self.max_redirects_spin.setRange(1, 50)
        self.max_redirects_spin.setValue(5)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1000, 300000)
        self.timeout_spin.setSingleStep(1000)
        self.timeout_spin.setSuffix(" ms")
        self.timeout_spin.setValue(30000)
        self.encode_url_check = QCheckBox("Encode URL parameters")
        self.encode_url_check.setChecked(True)

        settings_form = QFormLayout()
        settings_form.addRow(self.follow_redirects_check)
        settings_form.addRow("Max redirects", self.max_redirects_spin)
        settings_form.addRow("Request timeout", self.timeout_spin)
        settings_form.addRow(self.encode_url_check)
        settings_widget = QWidget()
        settings_widget.setLayout(settings_form)

        self.tabs = QTabWidget()
        self.tabs.addTab(auth_widget, "Auth")
        self.tabs.addTab(query_widget, "Params")
        self.tabs.addTab(headers_widget, "Headers")
        self.tabs.addTab(body_widget, "Body")
        self.tabs.addTab(settings_widget, "Settings")

        layout = QVBoxLayout(self)
        layout.addLayout(url_row)
        layout.addWidget(self.tabs)

        self.method_combo.currentTextChanged.connect(self._emit_changed)
        self.url_input.textChanged.connect(self._on_url_changed)
        self.auth_type_combo.currentIndexChanged.connect(self._on_auth_type_changed)
        self.bearer_token_input.textChanged.connect(self._emit_changed)
        self.basic_username_input.textChanged.connect(self._emit_changed)
        self.basic_password_input.textChanged.connect(self._emit_changed)
        self.api_key_name_input.textChanged.connect(self._emit_changed)
        self.api_key_value_input.textChanged.connect(self._emit_changed)
        self.api_key_in_combo.currentIndexChanged.connect(self._emit_changed)
        self.oauth_idp_input.textChanged.connect(self._emit_changed)
        self.oauth_client_id_input.textChanged.connect(self._emit_changed)
        self.oauth_client_secret_input.textChanged.connect(self._emit_changed)
        self.oauth_grant_type_combo.currentIndexChanged.connect(self._on_oauth_grant_type_changed)
        self.oauth_scope_input.textChanged.connect(self._emit_changed)
        self.oauth_content_type_combo.currentTextChanged.connect(self._emit_changed)
        self.oauth_username_input.textChanged.connect(self._emit_changed)
        self.oauth_password_input.textChanged.connect(self._emit_changed)
        self.oauth_access_token_input.textChanged.connect(self._emit_changed)
        self.oauth_test_auth_button.clicked.connect(self._test_oauth_auth)
        self.body_editor.changed.connect(self._emit_changed)
        self.headers_table.changed.connect(self._emit_changed)
        self.query_params_table.changed.connect(self._emit_changed)
        self.path_params_table.changed.connect(self._emit_changed)
        self.follow_redirects_check.toggled.connect(self._emit_changed)
        self.max_redirects_spin.valueChanged.connect(self._emit_changed)
        self.timeout_spin.valueChanged.connect(self._emit_changed)
        self.encode_url_check.toggled.connect(self._emit_changed)

        self._on_auth_type_changed(self.auth_type_combo.currentIndex())
        self._on_oauth_grant_type_changed(self.oauth_grant_type_combo.currentIndex())

    def load_request(self, request: HttpRequest) -> None:
        self._loading = True
        try:
            self.method_combo.setCurrentText(request.method)
            self.url_input.setText(request.url)
            self.body_editor.load_body(request.body)
            self._set_headers(request.headers)
            self.query_params_table.load_entries(request.query_params)
            self.path_params_table.load_entries(request.path_params)
            self._set_settings(request.settings)
            self._set_auth(request.auth)
        finally:
            self._loading = False

    def to_request(self, name: str) -> HttpRequest:
        return HttpRequest(
            name=name,
            method=self.method_combo.currentText(),
            url=self.url_input.text().strip(),
            headers=self.headers_table.collect_entries(),
            query_params=self.query_params_table.collect_entries(),
            path_params=self.path_params_table.collect_entries(),
            body=self.body_editor.collect_body(),
            auth=self._collect_auth(),
            settings=self._collect_settings(),
        )

    def _on_url_changed(self, _text: str) -> None:
        if not self._loading:
            self._sync_path_params_from_url()
            self._emit_changed()

    def _sync_path_params_from_url(self) -> None:
        names = extract_path_param_names(self.url_input.text())
        existing = {entry.name: entry for entry in self.path_params_table.collect_entries()}
        entries = [
            KeyValueEntry(
                name=name,
                value=existing[name].value if name in existing else "",
                enabled=existing[name].enabled if name in existing else True,
            )
            for name in names
        ]
        self.path_params_table.load_entries(entries)

    def _emit_changed(self, *_args: object) -> None:
        if not self._loading:
            self.changed.emit()

    def _on_auth_type_changed(self, index: int) -> None:
        self.auth_stack.setCurrentIndex(index)
        self._emit_changed()

    def _on_oauth_grant_type_changed(self, index: int) -> None:
        grant_type = OAUTH_GRANT_TYPES[index][1]
        show_password_fields = grant_type == OAuthGrantType.PASSWORD
        self.oauth_username_label.setVisible(show_password_fields)
        self.oauth_username_input.setVisible(show_password_fields)
        self.oauth_password_label.setVisible(show_password_fields)
        self.oauth_password_input.setVisible(show_password_fields)
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
        self.oauth_idp_input.setText(auth.idp_endpoint)
        self.oauth_client_id_input.setText(auth.client_id)
        self.oauth_client_secret_input.setText(auth.client_secret)
        grant_type_index = next(
            (
                i
                for i, (_, grant_type) in enumerate(OAUTH_GRANT_TYPES)
                if grant_type == auth.grant_type
            ),
            0,
        )
        self.oauth_grant_type_combo.setCurrentIndex(grant_type_index)
        self.oauth_scope_input.setText(auth.scope)
        content_type_index = self.oauth_content_type_combo.findText(auth.token_content_type)
        self.oauth_content_type_combo.setCurrentIndex(
            content_type_index if content_type_index >= 0 else 0
        )
        self.oauth_username_input.setText(auth.username)
        self.oauth_password_input.setText(auth.password)
        self.oauth_access_token_input.setText(auth.access_token)
        self._on_oauth_grant_type_changed(grant_type_index)
        self.auth_stack.setCurrentIndex(type_index)

    def _test_oauth_auth(self) -> None:
        auth = self._collect_auth()
        timeout = self.timeout_spin.value() / 1000
        result = fetch_oauth_token(auth, timeout=timeout)
        self.oauth_test_finished.emit(result.response)

        if result.error:
            self.oauth_access_token_input.clear()
            self._emit_changed()
            QMessageBox.critical(self, "Test Auth", result.error)
            return

        assert result.access_token is not None
        self.oauth_access_token_input.setText(result.access_token)
        self._set_authorization_bearer_header(result.access_token)
        self._emit_changed()
        QMessageBox.information(self, "Test Auth", "Access token obtained successfully.")

    def _set_authorization_bearer_header(self, token: str) -> None:
        entries = upsert_header(
            self.headers_table.collect_entries(),
            "Authorization",
            f"Bearer {token}",
        )
        self.headers_table.load_entries(entries)

    def _collect_auth(self) -> HttpAuth:
        auth_type = AUTH_TYPES[self.auth_type_combo.currentIndex()][1]
        key_in = API_KEY_LOCATIONS[self.api_key_in_combo.currentIndex()][1]
        grant_type = OAUTH_GRANT_TYPES[self.oauth_grant_type_combo.currentIndex()][1]
        return HttpAuth(
            type=auth_type,
            token=self.bearer_token_input.text(),
            username=self.oauth_username_input.text()
            if auth_type == AuthType.OAUTH
            else self.basic_username_input.text(),
            password=self.oauth_password_input.text()
            if auth_type == AuthType.OAUTH
            else self.basic_password_input.text(),
            key_name=self.api_key_name_input.text(),
            key_value=self.api_key_value_input.text(),
            key_in=key_in,
            idp_endpoint=self.oauth_idp_input.text(),
            client_id=self.oauth_client_id_input.text(),
            client_secret=self.oauth_client_secret_input.text(),
            grant_type=grant_type,
            scope=self.oauth_scope_input.text(),
            token_content_type=self.oauth_content_type_combo.currentText().strip()
            or DEFAULT_OAUTH_TOKEN_CONTENT_TYPE,
            access_token=self.oauth_access_token_input.text(),
        )

    def _set_headers(self, headers: list[KeyValueEntry]) -> None:
        self.headers_table.load_entries(headers)

    def _set_settings(self, settings: HttpRequestSettings) -> None:
        self.follow_redirects_check.setChecked(settings.follow_redirects)
        self.max_redirects_spin.setValue(settings.max_redirects)
        self.timeout_spin.setValue(settings.timeout_ms)
        self.encode_url_check.setChecked(settings.encode_url)

    def _collect_settings(self) -> HttpRequestSettings:
        return HttpRequestSettings(
            follow_redirects=self.follow_redirects_check.isChecked(),
            max_redirects=self.max_redirects_spin.value(),
            timeout_ms=self.timeout_spin.value(),
            encode_url=self.encode_url_check.isChecked(),
        )

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from apiclient.http.response_format import (
    format_headers_raw,
    is_html_content_type,
    is_json_content,
    render_body_text,
)
from apiclient.http.status import status_class
from apiclient.models.request import HttpResponse
from apiclient.ui.json_syntax_highlighter import JsonSyntaxHighlighter


class _RawRenderedTab(QWidget):
    def __init__(
        self,
        rendered_widget: QWidget,
        raw_widget: QWidget,
        *,
        default_mode: str = "Rendered",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Rendered", "Raw"])
        self.mode_combo.setCurrentText(default_mode)

        self.stack = QStackedWidget()
        self.stack.addWidget(rendered_widget)
        self.stack.addWidget(raw_widget)
        self.stack.setCurrentIndex(self.mode_combo.currentIndex())

        controls = QHBoxLayout()
        controls.addStretch()
        controls.addWidget(QLabel("View"))
        controls.addWidget(self.mode_combo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self.stack)

        self.mode_combo.currentIndexChanged.connect(self.stack.setCurrentIndex)


class ResponseViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._response: HttpResponse | None = None

        self.summary_label = QLabel("No response yet")
        self.summary_label.setTextInteractionFlags(
            self.summary_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.headers_table = QTableWidget(0, 2)
        self.headers_table.setHorizontalHeaderLabels(["Header", "Value"])
        self.headers_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.headers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.headers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self.headers_raw_view = QPlainTextEdit()
        self.headers_raw_view.setReadOnly(True)
        self.headers_raw_view.setPlaceholderText("Raw response headers")

        self.headers_tab = _RawRenderedTab(self.headers_table, self.headers_raw_view)

        self.body_html_view = QTextBrowser()
        self.body_html_view.setOpenExternalLinks(False)

        self.body_text_view = QPlainTextEdit()
        self.body_text_view.setReadOnly(True)
        self.body_json_highlighter = JsonSyntaxHighlighter(self.body_text_view.document())

        self.body_rendered_stack = QStackedWidget()
        self.body_rendered_stack.addWidget(self.body_text_view)
        self.body_rendered_stack.addWidget(self.body_html_view)

        self.body_raw_view = QPlainTextEdit()
        self.body_raw_view.setReadOnly(True)
        self.body_raw_view.setPlaceholderText("Raw response body")

        self.body_tab = _RawRenderedTab(self.body_rendered_stack, self.body_raw_view)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.headers_tab, "Headers")
        self.tabs.addTab(self.body_tab, "Body")

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.tabs)

    def show_response(self, response: HttpResponse) -> None:
        self._response = response
        if response.error:
            self.summary_label.setText(f"Error · {response.elapsed_ms:.0f} ms")
            self._set_headers({})
            self.body_raw_view.setPlainText(response.error)
            self.body_text_view.setPlainText(response.error)
            self.body_json_highlighter.set_enabled(False)
            self.body_html_view.clear()
            self.body_rendered_stack.setCurrentWidget(self.body_text_view)
            return

        self.summary_label.setText(
            f"{response.status_code} {response.reason} ({status_class(response.status_code)})"
            f" · {response.elapsed_ms:.0f} ms"
        )
        self._refresh_headers(response.headers)
        self._refresh_body(response.body, response.content_type)

    def clear(self) -> None:
        self._response = None
        self.summary_label.setText("No response yet")
        self._set_headers({})
        self.headers_raw_view.clear()
        self.body_raw_view.clear()
        self.body_text_view.clear()
        self.body_json_highlighter.set_enabled(False)
        self.body_html_view.clear()
        self.body_rendered_stack.setCurrentWidget(self.body_text_view)

    def _refresh_headers(self, headers: dict[str, str]) -> None:
        self._set_headers(headers)
        self.headers_raw_view.setPlainText(format_headers_raw(headers))

    def _refresh_body(self, body: str, content_type: str | None) -> None:
        self.body_raw_view.setPlainText(body)
        if is_html_content_type(content_type):
            self.body_html_view.setHtml(body)
            self.body_rendered_stack.setCurrentWidget(self.body_html_view)
        else:
            rendered = render_body_text(body, content_type)
            self.body_text_view.setPlainText(rendered)
            self.body_json_highlighter.set_enabled(is_json_content(body, content_type))
            self.body_rendered_stack.setCurrentWidget(self.body_text_view)

    def _set_headers(self, headers: dict[str, str]) -> None:
        self.headers_table.setRowCount(0)
        for key, value in headers.items():
            row = self.headers_table.rowCount()
            self.headers_table.insertRow(row)
            self.headers_table.setItem(row, 0, QTableWidgetItem(key))
            self.headers_table.setItem(row, 1, QTableWidgetItem(value))

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apiclient.models.request import BodyMode, FormFieldEntry, FormFieldKind, HttpBody
from apiclient.ui.key_value_table import KeyValueTableWidget

BODY_MODES = [
    BodyMode.NONE,
    BodyMode.JSON,
    BodyMode.TEXT,
    BodyMode.FORM_URLENCODED,
    BodyMode.MULTIPART,
    BodyMode.FILE,
]


class MultipartFieldsWidget(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Name", "Type", "Value / file"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        add_btn = QPushButton("Add field")
        remove_btn = QPushButton("Remove field")
        browse_btn = QPushButton("Browse file…")
        add_btn.clicked.connect(self._add_row)
        remove_btn.clicked.connect(self._remove_row)
        browse_btn.clicked.connect(self._browse_file)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        buttons.addWidget(browse_btn)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.table.itemChanged.connect(self._on_item_changed)

    def load_fields(self, fields: list[FormFieldEntry]) -> None:
        self._loading = True
        try:
            self.table.blockSignals(True)
            self.table.setRowCount(0)
            for entry in fields:
                self._append_row(entry)
            if self.table.rowCount() == 0:
                self._append_row(FormFieldEntry())
            self.table.blockSignals(False)
        finally:
            self._loading = False

    def collect_fields(self) -> list[FormFieldEntry]:
        fields: list[FormFieldEntry] = []
        for row in range(self.table.rowCount()):
            enabled_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            type_widget = self.table.cellWidget(row, 2)
            value_item = self.table.item(row, 3)
            name = (name_item.text() if name_item else "").strip()
            value = value_item.text() if value_item else ""
            enabled = (
                enabled_item.checkState() == Qt.CheckState.Checked if enabled_item else True
            )
            kind = FormFieldKind.TEXT
            if isinstance(type_widget, QComboBox):
                kind = FormFieldKind(type_widget.currentText())
            if not name and not value:
                continue
            fields.append(
                FormFieldEntry(
                    name=name,
                    value=value if kind == FormFieldKind.TEXT else "",
                    enabled=enabled,
                    kind=kind,
                    file_path=value if kind == FormFieldKind.FILE else "",
                )
            )
        return fields

    def _on_item_changed(self, _item: QTableWidgetItem) -> None:
        self._emit_changed()

    def _emit_changed(self) -> None:
        if not self._loading:
            self.changed.emit()

    def _append_row(self, entry: FormFieldEntry) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled_item = QTableWidgetItem()
        enabled_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        enabled_item.setCheckState(
            Qt.CheckState.Checked if entry.enabled else Qt.CheckState.Unchecked
        )
        self.table.setItem(row, 0, enabled_item)
        self.table.setItem(row, 1, QTableWidgetItem(entry.name))

        kind_combo = QComboBox()
        kind_combo.addItems([FormFieldKind.TEXT.value, FormFieldKind.FILE.value])
        kind_combo.setCurrentText(entry.kind.value)
        kind_combo.currentTextChanged.connect(lambda _t: self._emit_changed())
        self.table.setCellWidget(row, 2, kind_combo)

        value = entry.value if entry.kind == FormFieldKind.TEXT else entry.file_path
        self.table.setItem(row, 3, QTableWidgetItem(value))

    def _add_row(self) -> None:
        self._append_row(FormFieldEntry())
        self._emit_changed()

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self._append_row(FormFieldEntry())
        self._emit_changed()

    def _browse_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        row = self.table.currentRow()
        if row < 0:
            return
        type_widget = self.table.cellWidget(row, 2)
        if not isinstance(type_widget, QComboBox):
            return
        if type_widget.currentText() != FormFieldKind.FILE.value:
            return
        path, _selected = QFileDialog.getOpenFileName(self, "Select file")
        if path:
            self.table.setItem(row, 3, QTableWidgetItem(path))
            self._emit_changed()


class BodyEditor(QWidget):
    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._loading = False

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([mode.value for mode in BODY_MODES])

        self.none_label = QLabel("No request body.")
        self.none_label.setWordWrap(True)

        self.raw_editor = QPlainTextEdit()
        self.raw_editor.setPlaceholderText("Request body")

        self.content_type_input = QLineEdit()
        self.content_type_input.setPlaceholderText("Content-Type (optional)")

        self.form_fields_table = KeyValueTableWidget(name_header="Field", value_header="Value")
        self.multipart_fields = MultipartFieldsWidget()

        self.file_path_input = QLineEdit()
        self.file_path_input.setPlaceholderText("Path to file")
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_file)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_path_input, stretch=1)
        file_row.addWidget(browse_btn)

        self.file_content_type_input = QLineEdit()
        self.file_content_type_input.setPlaceholderText("Content-Type (optional)")

        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.addLayout(file_row)
        file_layout.addWidget(self.file_content_type_input)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.none_label)
        self.stack.addWidget(self.raw_editor)
        self.stack.addWidget(self.form_fields_table)
        self.stack.addWidget(self.multipart_fields)
        self.stack.addWidget(file_widget)

        layout = QVBoxLayout(self)
        layout.addWidget(self.mode_combo)
        layout.addWidget(self.content_type_input)
        layout.addWidget(self.stack)

        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.raw_editor.textChanged.connect(self._emit_changed)
        self.content_type_input.textChanged.connect(self._emit_changed)
        self.form_fields_table.changed.connect(self._emit_changed)
        self.multipart_fields.changed.connect(self._emit_changed)
        self.file_path_input.textChanged.connect(self._emit_changed)
        self.file_content_type_input.textChanged.connect(self._emit_changed)

        self._on_mode_changed(self.mode_combo.currentText())

    def load_body(self, body: HttpBody) -> None:
        self._loading = True
        try:
            self.mode_combo.setCurrentText(body.mode.value)
            self.raw_editor.setPlainText(body.content)
            if body.mode == BodyMode.FILE:
                self.file_content_type_input.setText(body.content_type)
                self.content_type_input.clear()
            else:
                self.content_type_input.setText(body.content_type)
                self.file_content_type_input.clear()
            self.form_fields_table.load_entries(body.form_fields)
            self.multipart_fields.load_fields(body.multipart_fields)
            self.file_path_input.setText(body.file_path)
            self._on_mode_changed(body.mode.value)
        finally:
            self._loading = False

    def collect_body(self) -> HttpBody:
        mode = BodyMode(self.mode_combo.currentText())
        content_type = ""
        if mode == BodyMode.TEXT:
            content_type = self.content_type_input.text()
        elif mode == BodyMode.FILE:
            content_type = self.file_content_type_input.text()
        return HttpBody(
            mode=mode,
            content=self.raw_editor.toPlainText(),
            form_fields=self.form_fields_table.collect_entries(),
            multipart_fields=self.multipart_fields.collect_fields(),
            file_path=self.file_path_input.text(),
            content_type=content_type,
        )

    def _on_mode_changed(self, mode: str) -> None:
        index_map = {
            BodyMode.NONE.value: 0,
            BodyMode.JSON.value: 1,
            BodyMode.TEXT.value: 1,
            BodyMode.FORM_URLENCODED.value: 2,
            BodyMode.MULTIPART.value: 3,
            BodyMode.FILE.value: 4,
        }
        self.stack.setCurrentIndex(index_map.get(mode, 0))
        self.content_type_input.setVisible(mode == BodyMode.TEXT.value)
        self.file_content_type_input.setVisible(mode == BodyMode.FILE.value)
        self._emit_changed()

    def _browse_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _selected = QFileDialog.getOpenFileName(self, "Select body file")
        if path:
            self.file_path_input.setText(path)
            self._emit_changed()

    def _emit_changed(self) -> None:
        if not self._loading:
            self.changed.emit()

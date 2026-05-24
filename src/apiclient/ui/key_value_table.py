from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from apiclient.models.request import KeyValueEntry


class KeyValueTableWidget(QWidget):
    changed = Signal()

    def __init__(
        self,
        *,
        name_header: str = "Name",
        value_header: str = "Value",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._loading = False

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", name_header, value_header])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        add_btn = QPushButton("Add row")
        remove_btn = QPushButton("Remove row")
        add_btn.clicked.connect(self._add_row)
        remove_btn.clicked.connect(self._remove_row)

        buttons = QHBoxLayout()
        buttons.addWidget(add_btn)
        buttons.addWidget(remove_btn)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.table.itemChanged.connect(self._on_item_changed)

    def load_entries(self, entries: list[KeyValueEntry]) -> None:
        self._loading = True
        try:
            self.table.blockSignals(True)
            self.table.setRowCount(0)
            for entry in entries:
                self._append_row(entry.name, entry.value, entry.enabled)
            if self.table.rowCount() == 0:
                self._append_row("", "", True)
            self.table.blockSignals(False)
        finally:
            self._loading = False

    def collect_entries(self) -> list[KeyValueEntry]:
        entries: list[KeyValueEntry] = []
        for row in range(self.table.rowCount()):
            enabled_item = self.table.item(row, 0)
            name_item = self.table.item(row, 1)
            value_item = self.table.item(row, 2)
            name = (name_item.text() if name_item else "").strip()
            value = value_item.text() if value_item else ""
            enabled = (
                enabled_item.checkState() == Qt.CheckState.Checked if enabled_item else True
            )
            if name or value:
                entries.append(KeyValueEntry(name=name, value=value, enabled=enabled))
        return entries

    def _on_item_changed(self, _item: QTableWidgetItem) -> None:
        if not self._loading:
            self.changed.emit()

    def _append_row(self, name: str, value: str, enabled: bool) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)

        enabled_item = QTableWidgetItem()
        enabled_item.setFlags(
            Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
        )
        enabled_item.setCheckState(
            Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        )
        self.table.setItem(row, 0, enabled_item)
        self.table.setItem(row, 1, QTableWidgetItem(name))
        self.table.setItem(row, 2, QTableWidgetItem(value))

    def _add_row(self) -> None:
        self._append_row("", "", True)
        self.changed.emit()

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
        if self.table.rowCount() == 0:
            self._append_row("", "", True)
        self.changed.emit()

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

from apiclient.models.project import FolderItem
from apiclient.storage.project_storage import ProjectSession


def list_folder_targets(session: ProjectSession) -> list[tuple[str, list, tuple[str, ...]]]:
    targets: list[tuple[str, list, tuple[str, ...]]] = [
        ("Collection root", session.collection.items, ()),
    ]

    def walk(folder: FolderItem, path: tuple[str, ...]) -> None:
        targets.append((" / ".join(path), folder.items, path))
        for item in folder.items:
            if isinstance(item, FolderItem):
                walk(item, path + (item.name,))

    for item in session.collection.items:
        if isinstance(item, FolderItem):
            walk(item, (item.name,))

    return targets


class SaveRequestDialog(QDialog):
    def __init__(
        self,
        session: ProjectSession,
        *,
        suggested_name: str = "Untitled request",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Save Request")

        self.name_input = QLineEdit(suggested_name)
        self.folder_combo = QComboBox()
        for label, parent_items, folder_parts in list_folder_targets(session):
            self.folder_combo.addItem(label, (parent_items, folder_parts))

        form = QFormLayout()
        form.addRow("Request name", self.name_input)
        form.addRow("Save in", self.folder_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def selected_name(self) -> str:
        return self.name_input.text().strip()

    def selected_target(self) -> tuple[list, tuple[str, ...]]:
        data = self.folder_combo.currentData()
        assert data is not None
        parent_items, folder_parts = data
        return parent_items, folder_parts

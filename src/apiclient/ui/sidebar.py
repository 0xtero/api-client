from dataclasses import dataclass
from typing import Literal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem

from apiclient.models.project import CollectionItem, FolderItem, RequestRef
from apiclient.storage.project_storage import ProjectSession


@dataclass(frozen=True)
class TreeSelection:
    kind: Literal["none", "folder", "request"]
    item: CollectionItem | None = None
    parent_items: list[CollectionItem] | None = None
    index: int | None = None
    file_path: str | None = None


class CollectionSidebar(QTreeWidget):
    selection_changed = Signal(object)
    duplicate_requested = Signal(object)
    rename_requested = Signal(object)
    delete_requested = Signal(object)

    ROLE_KIND = Qt.ItemDataRole.UserRole
    ROLE_ITEM = Qt.ItemDataRole.UserRole + 1
    ROLE_PARENT = Qt.ItemDataRole.UserRole + 2
    ROLE_INDEX = Qt.ItemDataRole.UserRole + 3
    ROLE_FILE = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.currentItemChanged.connect(self._on_current_changed)

    def load_session(self, session: ProjectSession | None) -> None:
        self.blockSignals(True)
        self.clear()
        if session is not None:
            for index, item in enumerate(session.collection.items):
                self._append_item(None, session.collection.items, index, item)
            self.expandAll()
        self.blockSignals(False)

    def clear_selection(self) -> None:
        self.blockSignals(True)
        self.clearSelection()
        self.setCurrentItem(None)
        self.blockSignals(False)

    def current_selection(self) -> TreeSelection:
        item = self.currentItem()
        if item is None:
            return TreeSelection(kind="none")

        kind = item.data(0, self.ROLE_KIND)
        collection_item = item.data(0, self.ROLE_ITEM)
        parent_items = item.data(0, self.ROLE_PARENT)
        index = item.data(0, self.ROLE_INDEX)
        file_path = item.data(0, self.ROLE_FILE)

        if kind == "request":
            return TreeSelection(
                kind="request",
                item=collection_item,
                parent_items=parent_items,
                index=index,
                file_path=file_path,
            )
        if kind == "folder":
            return TreeSelection(
                kind="folder",
                item=collection_item,
                parent_items=parent_items,
                index=index,
            )
        return TreeSelection(kind="none")

    def selection_for_item(self, tree_item: QTreeWidgetItem) -> TreeSelection:
        kind = tree_item.data(0, self.ROLE_KIND)
        collection_item = tree_item.data(0, self.ROLE_ITEM)
        parent_items = tree_item.data(0, self.ROLE_PARENT)
        index = tree_item.data(0, self.ROLE_INDEX)
        file_path = tree_item.data(0, self.ROLE_FILE)

        if kind == "request":
            return TreeSelection(
                kind="request",
                item=collection_item,
                parent_items=parent_items,
                index=index,
                file_path=file_path,
            )
        if kind == "folder":
            return TreeSelection(
                kind="folder",
                item=collection_item,
                parent_items=parent_items,
                index=index,
            )
        return TreeSelection(kind="none")

    def select_request_by_file(self, file_path: str) -> None:
        iterator = self._walk_items(self.invisibleRootItem())
        for tree_item in iterator:
            if tree_item.data(0, self.ROLE_KIND) == "request" and tree_item.data(0, self.ROLE_FILE) == file_path:
                self.setCurrentItem(tree_item)
                return

    def _show_context_menu(self, position) -> None:
        tree_item = self.itemAt(position)
        if tree_item is None:
            return

        self.setCurrentItem(tree_item)
        selection = self.selection_for_item(tree_item)
        if selection.kind == "none":
            return

        menu = QMenu(self)
        if selection.kind == "request":
            duplicate_action = QAction("Duplicate", self)
            duplicate_action.triggered.connect(self._emit_duplicate_requested)
            menu.addAction(duplicate_action)

        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(self._emit_rename_requested)
        menu.addAction(rename_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._emit_delete_requested)
        menu.addAction(delete_action)

        menu.exec(self.viewport().mapToGlobal(position))

    def _emit_duplicate_requested(self) -> None:
        selection = self.current_selection()
        if selection.kind == "request":
            self.duplicate_requested.emit(selection)

    def _emit_rename_requested(self) -> None:
        selection = self.current_selection()
        if selection.kind in {"folder", "request"}:
            self.rename_requested.emit(selection)

    def _emit_delete_requested(self) -> None:
        selection = self.current_selection()
        if selection.kind in {"folder", "request"}:
            self.delete_requested.emit(selection)

    def _append_item(
        self,
        parent_tree_item: QTreeWidgetItem | None,
        parent_items: list[CollectionItem],
        index: int,
        collection_item: CollectionItem,
    ) -> QTreeWidgetItem:
        if isinstance(collection_item, FolderItem):
            tree_item = QTreeWidgetItem([collection_item.name])
            tree_item.setData(0, self.ROLE_KIND, "folder")
            tree_item.setData(0, self.ROLE_ITEM, collection_item)
            tree_item.setData(0, self.ROLE_PARENT, parent_items)
            tree_item.setData(0, self.ROLE_INDEX, index)
            if parent_tree_item is None:
                self.addTopLevelItem(tree_item)
            else:
                parent_tree_item.addChild(tree_item)

            for child_index, child in enumerate(collection_item.items):
                self._append_item(tree_item, collection_item.items, child_index, child)
            return tree_item

        assert isinstance(collection_item, RequestRef)
        tree_item = QTreeWidgetItem([collection_item.name])
        tree_item.setData(0, self.ROLE_KIND, "request")
        tree_item.setData(0, self.ROLE_ITEM, collection_item)
        tree_item.setData(0, self.ROLE_PARENT, parent_items)
        tree_item.setData(0, self.ROLE_INDEX, index)
        tree_item.setData(0, self.ROLE_FILE, collection_item.file)
        if parent_tree_item is None:
            self.addTopLevelItem(tree_item)
        else:
            parent_tree_item.addChild(tree_item)
        return tree_item

    def _walk_items(self, root: QTreeWidgetItem):
        for i in range(root.childCount()):
            child = root.child(i)
            yield child
            yield from self._walk_items(child)

    def _on_current_changed(self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        if current is None:
            self.selection_changed.emit(TreeSelection(kind="none"))
            return
        self.selection_changed.emit(self.current_selection())

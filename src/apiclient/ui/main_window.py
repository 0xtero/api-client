from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from apiclient.models.project import FolderItem, RequestRef
from apiclient.models.request import HttpRequest, HttpResponse
from apiclient.storage.project_storage import ProjectSession, ProjectStorage, ProjectStorageError
from apiclient.ui.request_editor import RequestEditor
from apiclient.ui.response_viewer import ResponseViewer
from apiclient.ui.sidebar import CollectionSidebar, TreeSelection
from apiclient.ui.workers import HttpRequestRunner


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("api-client")
        self.resize(1200, 800)

        self._storage = ProjectStorage()
        self._session: ProjectSession | None = None
        self._current_file: str | None = None
        self._dirty = False
        self._loading_editor = False
        self._runner = HttpRequestRunner()

        self.sidebar = CollectionSidebar()
        self.request_editor = RequestEditor()
        self.response_viewer = ResponseViewer()

        self.send_button = QPushButton("Send")
        self.save_button = QPushButton("Save")
        self.project_label = QLabel("No project open")
        self.project_label.setTextInteractionFlags(
            self.project_label.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse
        )

        top_bar = QHBoxLayout()
        top_bar.addWidget(self.project_label, stretch=1)
        top_bar.addWidget(self.save_button)
        top_bar.addWidget(self.send_button)

        request_panel = QWidget()
        request_layout = QVBoxLayout(request_panel)
        request_layout.setContentsMargins(0, 0, 0, 0)
        request_layout.addLayout(top_bar)
        request_layout.addWidget(self.request_editor)

        center_splitter = QSplitter(Qt.Orientation.Vertical)
        center_splitter.addWidget(request_panel)
        center_splitter.addWidget(self.response_viewer)
        center_splitter.setStretchFactor(0, 3)
        center_splitter.setStretchFactor(1, 2)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.sidebar)
        main_splitter.addWidget(center_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)
        main_splitter.setSizes([260, 940])

        self.setCentralWidget(main_splitter)
        self.setStatusBar(QStatusBar())

        self._build_menus()
        self._connect_signals()
        self._update_actions()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.new_project_action = QAction("&New Project…", self)
        self.open_project_action = QAction("&Open Project…", self)
        self.save_project_action = QAction("&Save Project", self)
        self.save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self.exit_action = QAction("E&xit", self)
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        collection_menu = self.menuBar().addMenu("&Collection")
        self.add_folder_action = QAction("Add &Folder", self)
        self.add_request_action = QAction("Add &Request", self)
        self.rename_item_action = QAction("&Rename", self)
        self.delete_item_action = QAction("&Delete", self)
        collection_menu.addAction(self.add_folder_action)
        collection_menu.addAction(self.add_request_action)
        collection_menu.addSeparator()
        collection_menu.addAction(self.rename_item_action)
        collection_menu.addAction(self.delete_item_action)

        toolbar = QToolBar("Main")
        toolbar.addAction(self.save_project_action)
        toolbar.addAction(self.add_folder_action)
        toolbar.addAction(self.add_request_action)
        toolbar.addWidget(self.send_button)
        self.addToolBar(toolbar)

    def _connect_signals(self) -> None:
        self.new_project_action.triggered.connect(self.new_project)
        self.open_project_action.triggered.connect(self.open_project)
        self.save_project_action.triggered.connect(self.save_project)
        self.exit_action.triggered.connect(self.close)
        self.add_folder_action.triggered.connect(self.add_folder)
        self.add_request_action.triggered.connect(self.add_request)
        self.rename_item_action.triggered.connect(self.rename_item)
        self.delete_item_action.triggered.connect(self.delete_item)
        self.send_button.clicked.connect(self.send_request)
        self.save_button.clicked.connect(self.save_current_request)
        self.sidebar.selection_changed.connect(self.on_selection_changed)
        self.request_editor.changed.connect(self._mark_dirty)

    def new_project(self) -> None:
        if not self._confirm_discard():
            return

        directory = QFileDialog.getExistingDirectory(self, "Choose project folder")
        if not directory:
            return

        name, ok = QInputDialog.getText(self, "New Project", "Project name:", text=Path(directory).name)
        if not ok or not name.strip():
            return

        try:
            session = self._storage.create(Path(directory), name.strip())
        except ProjectStorageError as exc:
            QMessageBox.critical(self, "New Project", str(exc))
            return

        self._set_session(session)
        self.statusBar().showMessage(f"Created project in {session.root}", 5000)

    def open_project(self) -> None:
        if not self._confirm_discard():
            return

        directory = QFileDialog.getExistingDirectory(self, "Open project folder")
        if not directory:
            return

        try:
            session = self._storage.open(Path(directory))
        except ProjectStorageError as exc:
            QMessageBox.critical(self, "Open Project", str(exc))
            return

        self._set_session(session)
        self.statusBar().showMessage(f"Opened {session.name}", 5000)

    def save_project(self) -> None:
        if not self._session:
            return
        if self._current_file:
            self.save_current_request()
        self._storage.save(self._session)
        self.statusBar().showMessage("Project saved", 3000)

    def save_current_request(self) -> None:
        if not self._session or not self._current_file:
            return

        selection = self.sidebar.current_selection()
        name = selection.item.name if selection.item else "Untitled request"
        request = self.request_editor.to_request(name)
        self._storage.save_request(self._session, self._current_file, request)
        if isinstance(selection.item, RequestRef) and selection.item.name != request.name:
            selection.item.name = request.name
            self.sidebar.load_session(self._session)
            self.sidebar.select_request_by_file(self._current_file)
        self._dirty = False
        self._update_actions()
        self.statusBar().showMessage("Request saved", 2000)

    def add_folder(self) -> None:
        if not self._session:
            return
        if not self._confirm_discard():
            return

        name, ok = QInputDialog.getText(self, "Add Folder", "Folder name:")
        if not ok or not name.strip():
            return

        parent_items = self._target_parent_items()
        self._storage.add_folder(self._session, parent_items, name.strip())
        self.sidebar.load_session(self._session)
        self._storage.save(self._session)
        self.statusBar().showMessage("Folder added", 2000)

    def add_request(self) -> None:
        if not self._session:
            return
        if not self._confirm_discard():
            return

        name, ok = QInputDialog.getText(self, "Add Request", "Request name:", text="New request")
        if not ok or not name.strip():
            return

        parent_items, folder_parts = self._target_parent_with_path()
        ref = self._storage.add_request(
            self._session,
            parent_items,
            name.strip(),
            folder_parts=folder_parts,
        )
        self._storage.save(self._session)
        self.sidebar.load_session(self._session)
        self.sidebar.select_request_by_file(ref.file)
        self.statusBar().showMessage("Request added", 2000)

    def rename_item(self) -> None:
        if not self._session:
            return

        selection = self.sidebar.current_selection()
        if selection.kind == "none" or selection.item is None:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=selection.item.name
        )
        if not ok or not new_name.strip() or new_name.strip() == selection.item.name:
            return

        current_file = self._current_file
        self._storage.rename_item(self._session, selection.item, new_name.strip())
        self._storage.save(self._session)
        self.sidebar.load_session(self._session)
        if current_file:
            self.sidebar.select_request_by_file(current_file)
        self.statusBar().showMessage("Item renamed", 2000)

    def delete_item(self) -> None:
        if not self._session:
            return

        selection = self.sidebar.current_selection()
        if selection.kind == "none" or selection.item is None or selection.parent_items is None:
            return
        if selection.index is None:
            return

        confirm = QMessageBox.question(
            self,
            "Delete Item",
            f"Delete '{selection.item.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._storage.remove_item(self._session, selection.parent_items, selection.index)
        self._storage.save(self._session)
        self._current_file = None
        self._dirty = False
        self.sidebar.load_session(self._session)
        self.response_viewer.clear()
        self.statusBar().showMessage("Item deleted", 2000)

    def send_request(self) -> None:
        if self._runner.is_running:
            return

        request = self.request_editor.to_request(self._current_request_name())
        if not request.url.strip():
            QMessageBox.warning(self, "Send Request", "URL is required.")
            return

        if self._session and self._current_file and self._dirty:
            self.save_current_request()

        self.send_button.setEnabled(False)
        self.statusBar().showMessage("Sending request…")
        self._runner.start(request, self._on_response, self._on_request_failed)

    def on_selection_changed(self, selection: TreeSelection) -> None:
        if self._loading_editor:
            return
        if not self._confirm_discard():
            if self._current_file:
                self.sidebar.select_request_by_file(self._current_file)
            return

        if selection.kind != "request" or not selection.file_path or not self._session:
            self._current_file = None
            self._dirty = False
            self._update_actions()
            return

        try:
            request = self._storage.load_request(self._session, selection.file_path)
        except ProjectStorageError as exc:
            QMessageBox.critical(self, "Load Request", str(exc))
            return

        self._loading_editor = True
        try:
            self.request_editor.load_request(request)
            self._current_file = selection.file_path
            self._dirty = False
        finally:
            self._loading_editor = False
        self._update_actions()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard():
            self._runner.cancel()
            event.accept()
        else:
            event.ignore()

    def _set_session(self, session: ProjectSession) -> None:
        self._session = session
        self._current_file = None
        self._dirty = False
        self.project_label.setText(f"{session.name} — {session.root}")
        self.sidebar.load_session(session)
        self.response_viewer.clear()
        self._update_actions()

    def _target_parent_items(self) -> list:
        assert self._session is not None
        selection = self.sidebar.current_selection()
        if selection.kind == "folder" and isinstance(selection.item, FolderItem):
            return selection.item.items
        if selection.kind == "request" and selection.parent_items is not None:
            return selection.parent_items
        return self._session.collection.items

    def _target_parent_with_path(self) -> tuple[list, tuple[str, ...]]:
        assert self._session is not None
        selection = self.sidebar.current_selection()
        if selection.kind == "folder" and isinstance(selection.item, FolderItem):
            return selection.item.items, self._folder_path_for_item(selection.item)
        if selection.kind == "request" and selection.parent_items is not None:
            folder = self._folder_containing(selection.parent_items)
            if folder is not None:
                return selection.parent_items, self._folder_path_for_item(folder)
            return selection.parent_items, ()
        return self._session.collection.items, ()

    def _folder_containing(self, parent_items: list) -> FolderItem | None:
        assert self._session is not None

        def walk(folder: FolderItem) -> FolderItem | None:
            if folder.items is parent_items:
                return folder
            for item in folder.items:
                if isinstance(item, FolderItem):
                    found = walk(item)
                    if found is not None:
                        return found
            return None

        for item in self._session.collection.items:
            if isinstance(item, FolderItem):
                found = walk(item)
                if found is not None:
                    return found
        return None

    def _folder_path_for_item(self, folder: FolderItem) -> tuple[str, ...]:
        assert self._session is not None
        path: list[str] = []

        def walk(items: list, target: FolderItem, current: list[str]) -> bool:
            for item in items:
                if item is target:
                    path.extend(current)
                    path.append(item.name)
                    return True
                if isinstance(item, FolderItem):
                    if walk(item.items, target, current + [item.name]):
                        return True
            return False

        walk(self._session.collection.items, folder, [])
        return tuple(path)

    def _current_request_name(self) -> str:
        selection = self.sidebar.current_selection()
        if selection.item:
            return selection.item.name
        return "Untitled request"

    def _mark_dirty(self) -> None:
        if self._current_file:
            self._dirty = True
            self._update_actions()

    def _update_actions(self) -> None:
        has_project = self._session is not None
        has_request = self._current_file is not None
        selection = self.sidebar.current_selection()
        has_item = selection.kind in {"folder", "request"}

        for action in (
            self.save_project_action,
            self.add_folder_action,
            self.add_request_action,
            self.rename_item_action,
            self.delete_item_action,
        ):
            action.setEnabled(has_project)

        self.save_button.setEnabled(has_project and has_request and self._dirty)
        self.send_button.setEnabled(has_request and not self._runner.is_running)
        self.rename_item_action.setEnabled(has_project and has_item)
        self.delete_item_action.setEnabled(has_project and has_item)

        title = "api-client"
        if self._session:
            title = f"{self._session.name} — api-client"
        if self._dirty:
            title = f"* {title}"
        self.setWindowTitle(title)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes to the current request before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if result == QMessageBox.StandardButton.Save:
            self.save_current_request()
            return True
        if result == QMessageBox.StandardButton.Discard:
            self._dirty = False
            self._update_actions()
            return True
        return False

    def _on_response(self, response: HttpResponse) -> None:
        self.response_viewer.show_response(response)
        self.send_button.setEnabled(True)
        self.statusBar().showMessage("Request completed", 3000)
        self._update_actions()

    def _on_request_failed(self, message: str) -> None:
        self.response_viewer.show_response(
            HttpResponse(status_code=0, reason="Worker failed", error=message)
        )
        self.send_button.setEnabled(True)
        self.statusBar().showMessage("Request failed", 3000)
        self._update_actions()


def create_main_window() -> MainWindow:
    return MainWindow()

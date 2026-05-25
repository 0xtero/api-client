from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from apiclient.http.auth import validate_auth
from apiclient.http.curl import curl_to_request, request_to_curl
from apiclient.http.url_builder import validate_path_params
from apiclient.models.project import FolderItem, RequestRef
from apiclient.models.request import HttpRequest, HttpResponse
from apiclient.storage.project_storage import ProjectSession, ProjectStorage, ProjectStorageError
from apiclient.ui.app_session import (
    apply_default_center_splitter_sizes,
    load_last_project_path,
    restore_center_splitter,
    restore_window_state,
    save_center_splitter,
    save_last_project_path,
    save_window_state,
)
from apiclient.ui.request_editor import RequestEditor
from apiclient.ui.response_viewer import ResponseViewer
from apiclient.ui.save_request_dialog import SaveRequestDialog
from apiclient.ui.sidebar import CollectionSidebar, TreeSelection
from apiclient.ui.workers import HttpRequestRunner


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("api-client")

        self._storage = ProjectStorage()
        self._session: ProjectSession | None = None
        self._current_file: str | None = None
        self._dirty = False
        self._loading_editor = False
        self._center_splitter_initialized = False
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

        self.center_splitter = QSplitter(Qt.Orientation.Vertical)
        self.center_splitter.addWidget(request_panel)
        self.center_splitter.addWidget(self.response_viewer)
        self.center_splitter.setStretchFactor(0, 3)
        self.center_splitter.setStretchFactor(1, 7)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.sidebar)
        main_splitter.addWidget(self.center_splitter)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)
        main_splitter.setSizes([260, 940])

        self.setCentralWidget(main_splitter)
        self.setStatusBar(QStatusBar())

        self._build_menus()
        self._connect_signals()
        restore_window_state(self)
        if not self._try_open_last_project():
            self._start_blank_request()
        self._update_actions()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.new_project_action = QAction("&New Project…", self)
        self.open_project_action = QAction("&Open Project…", self)
        self.new_request_action = QAction("&New Request", self)
        self.new_request_action.setShortcut(QKeySequence.StandardKey.New)
        self.save_request_action = QAction("&Save Request", self)
        self.save_request_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_project_action = QAction("Save &Project", self)
        self.exit_action = QAction("E&xit", self)
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.new_request_action)
        file_menu.addAction(self.save_request_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addSeparator()
        self.copy_curl_action = QAction("Copy as c&URL", self)
        self.import_curl_action = QAction("Import from c&URL…", self)
        file_menu.addAction(self.copy_curl_action)
        file_menu.addAction(self.import_curl_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        collection_menu = self.menuBar().addMenu("&Collection")
        self.add_folder_action = QAction("Add &Folder", self)
        self.add_request_action = QAction("New &Request", self)
        self.rename_item_action = QAction("&Rename", self)
        self.delete_item_action = QAction("&Delete", self)
        collection_menu.addAction(self.add_folder_action)
        collection_menu.addAction(self.add_request_action)
        collection_menu.addSeparator()
        collection_menu.addAction(self.rename_item_action)
        collection_menu.addAction(self.delete_item_action)

        toolbar = QToolBar("Main")
        toolbar.setObjectName("MainToolBar")
        toolbar.addAction(self.open_project_action)
        toolbar.addAction(self.save_request_action)
        toolbar.addAction(self.new_request_action)
        toolbar.addAction(self.add_folder_action)
        toolbar.addWidget(self.send_button)
        self.addToolBar(toolbar)

    def _connect_signals(self) -> None:
        self.new_project_action.triggered.connect(self.new_project)
        self.open_project_action.triggered.connect(self.open_project)
        self.new_request_action.triggered.connect(self.new_request)
        self.save_request_action.triggered.connect(self.save_current_request)
        self.save_project_action.triggered.connect(self.save_project)
        self.copy_curl_action.triggered.connect(self.copy_as_curl)
        self.import_curl_action.triggered.connect(self.import_from_curl)
        self.exit_action.triggered.connect(self.close)
        self.add_folder_action.triggered.connect(self.add_folder)
        self.add_request_action.triggered.connect(self.new_request)
        self.rename_item_action.triggered.connect(self.rename_item)
        self.delete_item_action.triggered.connect(self.delete_item)
        self.send_button.clicked.connect(self.send_request)
        self.save_button.clicked.connect(self.save_current_request)
        self.sidebar.selection_changed.connect(self.on_selection_changed)
        self.sidebar.duplicate_requested.connect(self.duplicate_request)
        self.sidebar.rename_requested.connect(self.rename_item)
        self.sidebar.delete_requested.connect(self.delete_item)
        self.request_editor.changed.connect(self._mark_dirty)
        self.request_editor.oauth_test_finished.connect(self._on_oauth_test_finished)

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

    def new_request(self) -> None:
        if not self._confirm_discard():
            return

        self._start_blank_request()
        self.statusBar().showMessage("New request", 2000)

    def _start_blank_request(self) -> None:
        self._loading_editor = True
        try:
            self.request_editor.load_request(HttpRequest())
            self._current_file = None
            self._dirty = False
            self.sidebar.clear_selection()
        finally:
            self._loading_editor = False
        self._update_actions()

    def open_project(self) -> None:
        if not self._confirm_discard():
            return

        directory = QFileDialog.getExistingDirectory(self, "Open project folder")
        if not directory:
            return

        self._open_project_at(Path(directory))

    def _try_open_last_project(self) -> bool:
        path = load_last_project_path()
        if path is None:
            return False
        if not self._open_project_at(path, notify=False):
            return False
        self.statusBar().showMessage(f"Reopened {self._session.name}", 5000)
        return True

    def _open_project_at(self, directory: Path, *, notify: bool = True) -> bool:
        try:
            session = self._storage.open(directory)
        except ProjectStorageError as exc:
            if notify:
                QMessageBox.critical(self, "Open Project", str(exc))
            return False

        self._set_session(session)
        if notify:
            self.statusBar().showMessage(f"Opened {session.name}", 5000)
        return True

    def save_project(self) -> None:
        if not self._session:
            return
        if self._current_file and self._dirty:
            if not self.save_current_request():
                return
        try:
            self._storage.save(self._session)
        except ProjectStorageError as exc:
            QMessageBox.critical(self, "Save Project", str(exc))
            return
        self.sidebar.load_session(self._session)
        if self._current_file:
            self.sidebar.select_request_by_file(self._current_file)
        self._update_actions()
        self.statusBar().showMessage("Project saved", 3000)

    def save_current_request(self) -> bool:
        if not self._dirty:
            return True

        if not self._ensure_project_for_save():
            return False

        assert self._session is not None
        request = self.request_editor.to_request(self._current_request_name())

        if not self._current_file:
            dialog = SaveRequestDialog(
                self._session,
                suggested_name=request.name or "Untitled request",
                parent=self,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return False
            name = dialog.selected_name()
            if not name:
                QMessageBox.warning(self, "Save Request", "Request name is required.")
                return False
            parent_items, folder_parts = dialog.selected_target()
            request.name = name
            ref = self._storage.add_request(
                self._session,
                parent_items,
                name,
                request,
                folder_parts=folder_parts,
            )
            self._current_file = ref.file
            self.sidebar.load_session(self._session)
            self.sidebar.select_request_by_file(ref.file)
        else:
            selection = self.sidebar.current_selection()
            name = selection.item.name if selection.item else request.name
            request.name = name
            self._storage.save_request(self._session, self._current_file, request)
            if isinstance(selection.item, RequestRef) and selection.item.name != request.name:
                selection.item.name = request.name
                self.sidebar.load_session(self._session)
                self.sidebar.select_request_by_file(self._current_file)

        self._dirty = False
        self._update_actions()
        self.statusBar().showMessage("Request saved", 2000)
        return True

    def _ensure_project_for_save(self) -> bool:
        if self._session:
            return True

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Question)
        message.setWindowTitle("Save Request")
        message.setText("No project is open. Create or open a project to save this request.")
        new_button = message.addButton("New Project…", QMessageBox.ButtonRole.AcceptRole)
        open_button = message.addButton("Open Project…", QMessageBox.ButtonRole.ActionRole)
        cancel_button = message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()

        clicked = message.clickedButton()
        if clicked == cancel_button:
            return False
        if clicked == new_button:
            return self._create_project_for_save()
        if clicked == open_button:
            return self._open_project_for_save()
        return False

    def _create_project_for_save(self) -> bool:
        directory = QFileDialog.getExistingDirectory(self, "Choose project folder")
        if not directory:
            return False

        name, ok = QInputDialog.getText(
            self,
            "New Project",
            "Project name:",
            text=Path(directory).name,
        )
        if not ok or not name.strip():
            return False

        try:
            session = self._storage.create(Path(directory), name.strip())
        except ProjectStorageError as exc:
            QMessageBox.critical(self, "New Project", str(exc))
            return False

        self._attach_session(session)
        return True

    def _open_project_for_save(self) -> bool:
        directory = QFileDialog.getExistingDirectory(self, "Open project folder")
        if not directory:
            return False

        try:
            session = self._storage.open(Path(directory))
        except ProjectStorageError as exc:
            QMessageBox.critical(self, "Open Project", str(exc))
            return False

        self._attach_session(session)
        return True

    def _attach_session(self, session: ProjectSession) -> None:
        self._session = session
        self.project_label.setText(f"{session.name} — {session.root}")
        self.sidebar.load_session(session)
        save_last_project_path(session.root)
        self._update_actions()

    def add_folder(self) -> None:
        if not self._session:
            return
        if not self._confirm_discard():
            return

        name, ok = QInputDialog.getText(self, "Add Folder", "Folder name:")
        if not ok or not name.strip():
            return

        self._storage.add_folder(self._session, self._session.collection.items, name.strip())
        self.sidebar.load_session(self._session)
        self.statusBar().showMessage("Folder added", 2000)

    def add_request(self) -> None:
        self.new_request()

    def duplicate_request(self, selection: TreeSelection | None = None) -> None:
        if not self._session:
            return

        selection = selection or self.sidebar.current_selection()
        if selection.kind != "request" or selection.item is None:
            return
        if not isinstance(selection.item, RequestRef):
            return

        location = self._storage.find_item_location(self._session, selection.item)
        if location is None:
            return
        parent_items, _index = location

        if not self._confirm_discard():
            return

        folder_parts = self._storage.find_folder_parts(self._session, parent_items)
        ref = self._storage.duplicate_request(
            self._session,
            parent_items,
            selection.item,
            folder_parts=folder_parts,
        )
        self.sidebar.load_session(self._session)
        self._load_request_file(ref.file)
        self.statusBar().showMessage("Request duplicated", 2000)

    def rename_item(self, selection: TreeSelection | None = None) -> None:
        if not self._session:
            return

        selection = selection or self.sidebar.current_selection()
        if selection.kind == "none" or selection.item is None:
            return

        location = self._storage.find_item_location(self._session, selection.item)
        if location is None:
            return
        parent_items, _index = location

        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=selection.item.name
        )
        if not ok or not new_name.strip() or new_name.strip() == selection.item.name:
            return

        old_file = selection.file_path if isinstance(selection.item, RequestRef) else None
        folder_parts = self._storage.find_folder_parts(self._session, parent_items)
        if selection.kind == "folder" and isinstance(selection.item, FolderItem):
            folder_parts = (*folder_parts, selection.item.name)

        try:
            self._storage.rename_item(
                self._session,
                selection.item,
                new_name.strip(),
                folder_parts=folder_parts,
            )
        except ProjectStorageError as exc:
            QMessageBox.critical(self, "Rename", str(exc))
            return

        self.sidebar.load_session(self._session)
        if isinstance(selection.item, RequestRef):
            if self._current_file == old_file:
                self._current_file = selection.item.file
            self.sidebar.select_request_by_file(selection.item.file)
        elif self._current_file:
            self.sidebar.select_request_by_file(self._current_file)
        self._update_actions()
        self.statusBar().showMessage("Item renamed", 2000)

    def delete_item(self, selection: TreeSelection | None = None) -> None:
        if not self._session:
            return

        selection = selection or self.sidebar.current_selection()
        if selection.kind == "none" or selection.item is None:
            return

        location = self._storage.find_item_location(self._session, selection.item)
        if location is None:
            return
        parent_items, index = location

        if selection.kind == "request":
            message = f"Delete request '{selection.item.name}'?"
        elif isinstance(selection.item, FolderItem):
            request_count = self._count_requests_in_folder(selection.item)
            if request_count:
                noun = "request" if request_count == 1 else "requests"
                message = (
                    f"Delete folder '{selection.item.name}' and all {request_count} "
                    f"contained {noun}?"
                )
            else:
                message = f"Delete empty folder '{selection.item.name}'?"
        else:
            message = f"Delete '{selection.item.name}'?"

        confirm = QMessageBox.question(
            self,
            "Delete Item",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        deleted_current = (
            selection.kind == "request"
            and self._current_file is not None
            and selection.file_path == self._current_file
        )
        deleted_folder_contains_current = (
            selection.kind == "folder"
            and isinstance(selection.item, FolderItem)
            and self._current_file is not None
            and self._folder_contains_request_file(selection.item, self._current_file)
        )

        self._storage.remove_item(self._session, parent_items, index)
        self.sidebar.load_session(self._session)

        if deleted_current or deleted_folder_contains_current:
            self._start_blank_request()
            self.response_viewer.clear()
        elif self._current_file:
            self.sidebar.select_request_by_file(self._current_file)

        self._update_actions()
        self.statusBar().showMessage("Item deleted", 2000)

    def _count_requests_in_folder(self, folder: FolderItem) -> int:
        count = 0

        def walk(items: list) -> None:
            nonlocal count
            for item in items:
                if isinstance(item, RequestRef):
                    count += 1
                elif isinstance(item, FolderItem):
                    walk(item.items)

        walk(folder.items)
        return count

    def _folder_contains_request_file(self, folder: FolderItem, file_path: str) -> bool:
        def walk(items: list) -> bool:
            for item in items:
                if isinstance(item, RequestRef) and item.file == file_path:
                    return True
                if isinstance(item, FolderItem) and walk(item.items):
                    return True
            return False

        return walk(folder.items)

    def copy_as_curl(self) -> None:
        request = self.request_editor.to_request(self._current_request_name())
        if not request.url.strip():
            QMessageBox.warning(self, "Copy as cURL", "URL is required.")
            return
        command = request_to_curl(request)
        QApplication.clipboard().setText(command)
        self.statusBar().showMessage("cURL command copied to clipboard", 3000)

    def import_from_curl(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Import from cURL")
        editor = QPlainTextEdit()
        editor.setPlaceholderText("Paste cURL command")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout = QVBoxLayout(dialog)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        command = editor.toPlainText().strip()
        if not command:
            return
        try:
            request = curl_to_request(command)
        except ValueError as exc:
            QMessageBox.critical(self, "Import from cURL", str(exc))
            return
        self.request_editor.load_request(request)
        self._dirty = True
        self._update_actions()
        self.statusBar().showMessage("Imported request from cURL", 3000)

    def send_request(self) -> None:
        if self._runner.is_running:
            return

        request = self.request_editor.to_request(self._current_request_name())
        if not request.url.strip():
            QMessageBox.warning(self, "Send Request", "URL is required.")
            return

        auth_error = validate_auth(request.auth)
        if auth_error:
            QMessageBox.warning(self, "Send Request", auth_error)
            return

        path_error = validate_path_params(request.url, request.path_params)
        if path_error:
            QMessageBox.warning(self, "Send Request", path_error)
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

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._center_splitter_initialized:
            return
        self._center_splitter_initialized = True
        if not restore_center_splitter(self.center_splitter):
            apply_default_center_splitter_sizes(self.center_splitter)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard():
            save_center_splitter(self.center_splitter)
            save_window_state(self)
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
        save_last_project_path(session.root)
        self._start_blank_request()

    def _current_request_name(self) -> str:
        selection = self.sidebar.current_selection()
        if selection.item:
            return selection.item.name
        return "Untitled request"

    def _load_request_file(self, file_path: str) -> None:
        assert self._session is not None
        request = self._storage.load_request(self._session, file_path)
        self._loading_editor = True
        try:
            self.request_editor.load_request(request)
            self._current_file = file_path
            self._dirty = False
        finally:
            self._loading_editor = False
        self.sidebar.select_request_by_file(file_path)
        self._update_actions()

    def _mark_dirty(self) -> None:
        if self._loading_editor:
            return
        self._dirty = True
        self._update_actions()

    def _update_actions(self) -> None:
        has_project = self._session is not None
        selection = self.sidebar.current_selection()
        has_item = selection.kind in {"folder", "request"}

        self.open_project_action.setEnabled(True)
        self.new_request_action.setEnabled(True)
        self.save_request_action.setEnabled(self._dirty)
        self.save_project_action.setEnabled(has_project and self._dirty)
        self.copy_curl_action.setEnabled(True)
        self.import_curl_action.setEnabled(True)

        for action in (
            self.add_folder_action,
            self.rename_item_action,
            self.delete_item_action,
        ):
            action.setEnabled(has_project)

        self.add_request_action.setEnabled(True)
        self.save_button.setEnabled(self._dirty)
        self.send_button.setEnabled(not self._runner.is_running)
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
            if not self.save_current_request():
                return False
            return not self._dirty
        if result == QMessageBox.StandardButton.Discard:
            self._dirty = False
            self._update_actions()
            return True
        return False

    def _on_oauth_test_finished(self, response: HttpResponse) -> None:
        self.response_viewer.show_response(response)
        if response.error:
            self.statusBar().showMessage("OAuth token request failed", 3000)
        else:
            self.statusBar().showMessage("OAuth token request completed", 3000)

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

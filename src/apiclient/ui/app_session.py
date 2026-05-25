from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow, QSplitter

CENTER_SPLITTER_STATE_KEY = "centerSplitterState"
REQUEST_PANEL_RATIO = 0.30
RESPONSE_PANEL_RATIO = 0.70


def app_settings() -> QSettings:
    return QSettings()


def resolve_last_project_path(raw: object | None) -> Path | None:
    if raw is None:
        return None

    path = Path(str(raw))
    if not path.is_dir():
        return None
    if not (path / "project.json").is_file():
        return None
    if not (path / "collection.json").is_file():
        return None
    return path.resolve()


def load_last_project_path() -> Path | None:
    return resolve_last_project_path(app_settings().value("lastProjectPath"))


def save_last_project_path(path: Path) -> None:
    app_settings().setValue("lastProjectPath", str(path.resolve()))


def restore_window_state(window: QMainWindow) -> None:
    settings = app_settings()
    geometry = settings.value("geometry")
    if geometry is not None:
        window.restoreGeometry(geometry)
    else:
        window.resize(1200, 800)

    window_state = settings.value("windowState")
    if window_state is not None:
        window.restoreState(window_state)


def save_window_state(window: QMainWindow) -> None:
    settings = app_settings()
    settings.setValue("geometry", window.saveGeometry())
    settings.setValue("windowState", window.saveState())


def restore_center_splitter(splitter: QSplitter) -> bool:
    state = app_settings().value(CENTER_SPLITTER_STATE_KEY)
    if state is None:
        return False
    splitter.restoreState(state)
    return True


def save_center_splitter(splitter: QSplitter) -> None:
    app_settings().setValue(CENTER_SPLITTER_STATE_KEY, splitter.saveState())


def apply_default_center_splitter_sizes(splitter: QSplitter) -> None:
    splitter.setStretchFactor(0, 3)
    splitter.setStretchFactor(1, 7)
    height = splitter.height()
    if height <= 0:
        height = splitter.parentWidget().height() if splitter.parentWidget() else 600
    if height <= 0:
        height = 600
    request_height = max(1, int(height * REQUEST_PANEL_RATIO))
    response_height = max(1, int(height * RESPONSE_PANEL_RATIO))
    splitter.setSizes([request_height, response_height])

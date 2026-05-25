from pathlib import Path

import pytest

from apiclient.ui.app_session import apply_default_center_splitter_sizes, resolve_last_project_path


def test_resolve_last_project_path_missing(tmp_path: Path) -> None:
    assert resolve_last_project_path(None) is None
    assert resolve_last_project_path("") is None
    assert resolve_last_project_path(str(tmp_path / "missing")) is None


def test_resolve_last_project_path_valid_project(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "project.json").write_text('{"name":"Demo"}', encoding="utf-8")
    (project_dir / "collection.json").write_text('{"items":[]}', encoding="utf-8")

    resolved = resolve_last_project_path(str(project_dir))
    assert resolved == project_dir.resolve()


def test_resolve_last_project_path_requires_collection_file(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "project.json").write_text('{"name":"Demo"}', encoding="utf-8")

    assert resolve_last_project_path(str(project_dir)) is None


def test_apply_default_center_splitter_sizes_uses_thirty_seventy_ratio() -> None:
    from PySide6.QtWidgets import QApplication, QSplitter, QWidget

    app = QApplication.instance() or QApplication([])
    splitter = QSplitter()
    top = QWidget()
    bottom = QWidget()
    splitter.addWidget(top)
    splitter.addWidget(bottom)
    splitter.resize(1000, 800)

    apply_default_center_splitter_sizes(splitter)

    request_size, response_size = splitter.sizes()
    total = request_size + response_size
    assert request_size / total == pytest.approx(0.30, abs=0.02)
    assert response_size / total == pytest.approx(0.70, abs=0.02)

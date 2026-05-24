from pathlib import Path

import pytest

from apiclient.models.request import AuthType, BodyMode, HttpAuth, HttpRequest, KeyValueEntry
from apiclient.storage.project_storage import ProjectStorage, ProjectStorageError, slugify


def test_slugify() -> None:
    assert slugify("List Users") == "list-users"
    assert slugify("  Hello!!! World  ") == "hello-world"


def test_create_open_save_round_trip(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo Project")

    folder = storage.add_folder(session, session.collection.items, "users")
    ref = storage.add_request(
        session,
        folder.items,
        "List users",
        HttpRequest(
            name="List users",
            method="GET",
            url="https://example.com/users",
            headers={"Accept": "application/json"},
        ),
        folder_parts=("users",),
    )

    storage.save(session)

    reopened = storage.open(tmp_path / "demo")
    assert reopened.project.name == "Demo Project"
    assert len(reopened.collection.items) == 1

    request = storage.load_request(reopened, ref.file)
    assert request.method == "GET"
    assert request.url == "https://example.com/users"
    assert request.headers[0].name == "Accept"
    assert request.headers[0].value == "application/json"


def test_invalid_request_path_rejected(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")

    with pytest.raises(ProjectStorageError):
        storage.load_request(session, "../outside.json")


def test_body_modes_serialize(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    ref = storage.add_request(
        session,
        session.collection.items,
        "Post",
        HttpRequest(
            name="Post",
            method="POST",
            url="https://example.com",
            body={"mode": BodyMode.JSON, "content": '{"ok": true}'},
        ),
    )
    storage.save(session)

    loaded = storage.load_request(storage.open(tmp_path / "demo"), ref.file)
    assert loaded.body.mode == BodyMode.JSON
    assert loaded.body.content == '{"ok": true}'


def test_auth_field_round_trip(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    ref = storage.add_request(
        session,
        session.collection.items,
        "Secure",
        HttpRequest(
            name="Secure",
            method="GET",
            url="https://example.com",
            auth=HttpAuth(type=AuthType.BEARER, token="secret"),
        ),
    )
    storage.save(session)

    loaded = storage.load_request(storage.open(tmp_path / "demo"), ref.file)
    assert loaded.auth.type == AuthType.BEARER
    assert loaded.auth.token == "secret"


def test_headers_list_format_round_trip(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    ref = storage.add_request(
        session,
        session.collection.items,
        "Headers",
        HttpRequest(
            name="Headers",
            method="GET",
            url="https://example.com",
            headers=[
                KeyValueEntry(name="Accept", value="application/json", enabled=True),
                KeyValueEntry(name="X-Skip", value="1", enabled=False),
            ],
        ),
    )
    storage.save(session)

    loaded = storage.load_request(storage.open(tmp_path / "demo"), ref.file)
    assert len(loaded.headers) == 2
    assert loaded.headers[1].enabled is False


def test_query_params_round_trip(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    ref = storage.add_request(
        session,
        session.collection.items,
        "Query",
        HttpRequest(
            name="Query",
            method="GET",
            url="https://example.com",
            query_params=[KeyValueEntry(name="page", value="2", enabled=True)],
        ),
    )
    storage.save(session)

    loaded = storage.load_request(storage.open(tmp_path / "demo"), ref.file)
    assert loaded.query_params[0].name == "page"
    assert loaded.query_params[0].value == "2"

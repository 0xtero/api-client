from pathlib import Path

import pytest

from apiclient.models.project import FolderItem
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


def test_oauth_auth_field_round_trip(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    ref = storage.add_request(
        session,
        session.collection.items,
        "OAuth",
        HttpRequest(
            name="OAuth",
            method="GET",
            url="https://example.com",
            auth=HttpAuth(
                type=AuthType.OAUTH,
                idp_endpoint="https://idp.example.com/token",
                client_id="client-id",
                client_secret="client-secret",
                grant_type="client_credentials",
                scope="api.read",
                token_content_type="application/x-www-form-urlencoded",
                access_token="saved-token",
            ),
        ),
    )
    storage.save(session)

    loaded = storage.load_request(storage.open(tmp_path / "demo"), ref.file)
    assert loaded.auth.type == AuthType.OAUTH
    assert loaded.auth.idp_endpoint == "https://idp.example.com/token"
    assert loaded.auth.client_id == "client-id"
    assert loaded.auth.client_secret == "client-secret"
    assert loaded.auth.grant_type == "client_credentials"
    assert loaded.auth.scope == "api.read"
    assert loaded.auth.token_content_type == "application/x-www-form-urlencoded"
    assert loaded.auth.access_token == "saved-token"


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


def test_duplicate_request_adds_copy_suffix(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    source = storage.add_request(
        session,
        session.collection.items,
        "List users",
        HttpRequest(name="List users", method="GET", url="https://example.com/users"),
    )
    storage.save(session)

    duplicate = storage.duplicate_request(session, session.collection.items, source)
    assert duplicate.name == "List users (copy)"
    assert duplicate.file != source.file
    assert len(session.collection.items) == 2

    loaded = storage.load_request(session, duplicate.file)
    assert loaded.url == "https://example.com/users"
    assert loaded.name == "List users (copy)"


def test_find_item_location_nested_folder(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    folder = storage.add_folder(session, session.collection.items, "users")
    ref = storage.add_request(
        session,
        folder.items,
        "List users",
        HttpRequest(name="List users", method="GET", url="https://example.com/users"),
        folder_parts=("users",),
    )

    location = storage.find_item_location(session, ref)
    assert location is not None
    parent_items, index = location
    assert parent_items is folder.items
    assert index == 0
    assert parent_items[index] is ref


def test_rename_request_moves_file_immediately(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    ref = storage.add_request(
        session,
        session.collection.items,
        "List users",
        HttpRequest(name="List users", method="GET", url="https://example.com/users"),
    )
    old_file = ref.file
    assert (tmp_path / "demo" / old_file).is_file()

    storage.rename_item(session, ref, "Get users")
    assert ref.name == "Get users"
    assert ref.file == "requests/get-users.json"
    assert not (tmp_path / "demo" / old_file).is_file()
    assert (tmp_path / "demo" / ref.file).is_file()

    loaded = storage.load_request(session, ref.file)
    assert loaded.name == "Get users"


def test_rename_folder_moves_request_files_immediately(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    folder = storage.add_folder(session, session.collection.items, "users")
    ref = storage.add_request(
        session,
        folder.items,
        "List users",
        HttpRequest(name="List users", method="GET", url="https://example.com/users"),
        folder_parts=("users",),
    )
    old_file = ref.file

    storage.rename_item(session, folder, "clients", folder_parts=("users",))
    assert ref.file == "requests/clients/list-users.json"
    assert not (tmp_path / "demo" / old_file).is_file()
    assert (tmp_path / "demo" / ref.file).is_file()


def test_duplicate_then_rename_updates_file_immediately(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    folder = storage.add_folder(session, session.collection.items, "ACME")
    source = storage.add_request(
        session,
        folder.items,
        "list-key",
        HttpRequest(name="list-key", method="GET", url="https://example.com/key"),
        folder_parts=("ACME",),
    )

    duplicate = storage.duplicate_request(
        session,
        folder.items,
        source,
        folder_parts=("ACME",),
    )
    assert duplicate.file != source.file
    assert (tmp_path / "demo" / duplicate.file).is_file()

    storage.rename_item(session, duplicate, "list-key-2", folder_parts=("ACME",))
    assert duplicate.file == "requests/ACME/list-key-2.json"
    assert (tmp_path / "demo" / duplicate.file).is_file()

    loaded = storage.load_request(session, duplicate.file)
    assert loaded.name == "list-key-2"


def test_add_folder_creates_top_level_folder(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    folder = storage.add_folder(session, session.collection.items, "users")
    storage.add_request(
        session,
        folder.items,
        "List users",
        HttpRequest(name="List users", method="GET", url="https://example.com/users"),
        folder_parts=("users",),
    )

    storage.add_folder(session, session.collection.items, "New folder")
    assert len(session.collection.items) == 2
    assert isinstance(session.collection.items[1], FolderItem)
    assert session.collection.items[1].name == "New folder"

    reopened = storage.open(tmp_path / "demo")
    assert len(reopened.collection.items) == 2
    assert isinstance(reopened.collection.items[1], FolderItem)


def test_remove_folder_deletes_contained_requests(tmp_path: Path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    folder = storage.add_folder(session, session.collection.items, "users")
    ref = storage.add_request(
        session,
        folder.items,
        "List users",
        HttpRequest(name="List users", method="GET", url="https://example.com/users"),
        folder_parts=("users",),
    )
    storage.save(session)
    assert (tmp_path / "demo" / ref.file).is_file()

    storage.remove_item(session, session.collection.items, 0)
    storage.save(session)

    assert not (tmp_path / "demo" / ref.file).is_file()
    assert len(session.collection.items) == 0

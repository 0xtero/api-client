from apiclient.storage.project_storage import ProjectStorage
from apiclient.ui.save_request_dialog import list_folder_targets


def test_list_folder_targets_includes_root_and_nested_folders(tmp_path) -> None:
    storage = ProjectStorage()
    session = storage.create(tmp_path / "demo", "Demo")
    users = storage.add_folder(session, session.collection.items, "users")
    storage.add_folder(session, users.items, "admin")
    storage.save(session)

    targets = list_folder_targets(session)
    labels = [label for label, _parent_items, _folder_parts in targets]
    assert labels == ["Collection root", "users", "users / admin"]

    root_target = targets[0]
    users_target = targets[1]
    admin_target = targets[2]
    assert root_target[2] == ()
    assert users_target[2] == ("users",)
    assert admin_target[2] == ("users", "admin")
    assert isinstance(users_target[1], list)
    assert isinstance(admin_target[1], list)

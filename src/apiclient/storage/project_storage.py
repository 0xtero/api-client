import json
import re
from datetime import UTC, datetime
from pathlib import Path

from apiclient.models.project import Collection, CollectionItem, FolderItem, Project, RequestRef
from apiclient.models.request import HttpRequest


class ProjectStorageError(Exception):
    pass


class ProjectSession:
    """In-memory view of an open on-disk project."""

    def __init__(self, root: Path, project: Project, collection: Collection) -> None:
        self.root = root
        self.project = project
        self.collection = collection

    @property
    def name(self) -> str:
        return self.project.name


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "untitled"


class ProjectStorage:
    PROJECT_FILE = "project.json"
    COLLECTION_FILE = "collection.json"
    REQUESTS_DIR = "requests"
    ENVIRONMENTS_DIR = "environments"

    def create(self, root: Path, name: str) -> ProjectSession:
        root = root.resolve()
        if root.exists() and any(root.iterdir()):
            raise ProjectStorageError(f"Directory is not empty: {root}")

        root.mkdir(parents=True, exist_ok=True)
        (root / self.REQUESTS_DIR).mkdir()
        (root / self.ENVIRONMENTS_DIR).mkdir()

        project = Project(name=name)
        collection = Collection()
        self._write_project(root, project)
        self._write_collection(root, collection)
        return ProjectSession(root, project, collection)

    def open(self, root: Path) -> ProjectSession:
        root = root.resolve()
        project_path = root / self.PROJECT_FILE
        collection_path = root / self.COLLECTION_FILE

        if not project_path.is_file():
            raise ProjectStorageError(f"Missing {self.PROJECT_FILE} in {root}")
        if not collection_path.is_file():
            raise ProjectStorageError(f"Missing {self.COLLECTION_FILE} in {root}")

        project = Project.model_validate_json(project_path.read_text(encoding="utf-8"))
        collection = Collection.model_validate_json(collection_path.read_text(encoding="utf-8"))
        return ProjectSession(root, project, collection)

    def save(self, session: ProjectSession) -> None:
        self._commit_session(session)

    def load_request(self, session: ProjectSession, relative_path: str) -> HttpRequest:
        path = self._resolve_request_path(session.root, relative_path)
        if not path.is_file():
            raise ProjectStorageError(f"Request file not found: {relative_path}")
        return HttpRequest.model_validate_json(path.read_text(encoding="utf-8"))

    def save_request(
        self, session: ProjectSession, relative_path: str, request: HttpRequest
    ) -> None:
        path = self._resolve_request_path(session.root, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(request.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )
        session.project.touch()

    def delete_request_file(self, session: ProjectSession, relative_path: str) -> None:
        path = self._resolve_request_path(session.root, relative_path)
        if path.is_file():
            path.unlink()

    def add_request(
        self,
        session: ProjectSession,
        parent_items: list[CollectionItem],
        name: str,
        request: HttpRequest | None = None,
        folder_parts: tuple[str, ...] = (),
    ) -> RequestRef:
        request = request or HttpRequest(name=name)
        request.name = name

        base = Path(*folder_parts) if folder_parts else Path()
        filename = self._unique_request_filename(session, base, slugify(name))
        relative = str(Path(self.REQUESTS_DIR) / base / filename).replace("\\", "/")

        self.save_request(session, relative, request)
        ref = RequestRef(name=name, file=relative)
        parent_items.append(ref)
        self._commit_session(session)
        return ref

    def add_folder(
        self, session: ProjectSession, parent_items: list[CollectionItem], name: str
    ) -> FolderItem:
        folder = FolderItem(name=name)
        parent_items.append(folder)
        self._commit_session(session)
        return folder

    def remove_item(self, session: ProjectSession, items: list[CollectionItem], index: int) -> None:
        item = items.pop(index)
        self._delete_item_files(session, item)
        self._commit_session(session)

    def _delete_item_files(self, session: ProjectSession, item: CollectionItem) -> None:
        if isinstance(item, RequestRef):
            self.delete_request_file(session, item.file)
            return
        if isinstance(item, FolderItem):
            for child in list(item.items):
                self._delete_item_files(session, child)

    def duplicate_request(
        self,
        session: ProjectSession,
        parent_items: list[CollectionItem],
        source: RequestRef,
        folder_parts: tuple[str, ...] = (),
    ) -> RequestRef:
        request = self.load_request(session, source.file)
        copy_name = f"{source.name} (copy)"
        return self.add_request(
            session,
            parent_items,
            copy_name,
            request.model_copy(update={"name": copy_name}),
            folder_parts=folder_parts,
        )

    def rename_item(
        self,
        session: ProjectSession,
        item: CollectionItem,
        new_name: str,
        *,
        folder_parts: tuple[str, ...] = (),
    ) -> None:
        new_name = new_name.strip()
        if not new_name or new_name == item.name:
            return

        if isinstance(item, RequestRef):
            self._rename_request_ref(session, item, new_name, folder_parts)
        elif isinstance(item, FolderItem):
            self._rename_folder_item(session, item, new_name, folder_parts)

        self._commit_session(session)

    def _rename_request_ref(
        self,
        session: ProjectSession,
        ref: RequestRef,
        new_name: str,
        folder_parts: tuple[str, ...],
    ) -> None:
        old_path = ref.file
        ref.name = new_name
        filename = self._unique_request_filename(
            session,
            Path(*folder_parts) if folder_parts else Path(),
            slugify(new_name),
            exclude_relative=old_path,
        )
        new_path = self._relative_request_path(folder_parts, filename)
        ref.file = new_path

        if old_path != new_path:
            self._move_request_files(session, {old_path: new_path})
            return

        request = self.load_request(session, old_path)
        request.name = new_name
        self.save_request(session, old_path, request)

    def _rename_folder_item(
        self,
        session: ProjectSession,
        folder: FolderItem,
        new_name: str,
        folder_parts: tuple[str, ...],
    ) -> None:
        old_parts = folder_parts
        new_parts = (*folder_parts[:-1], new_name) if folder_parts else (new_name,)
        folder.name = new_name
        moves = self._collect_path_remaps(folder.items, old_parts, new_parts)
        if moves:
            self._move_request_files(session, moves)

    def _collect_path_remaps(
        self,
        items: list[CollectionItem],
        old_parts: tuple[str, ...],
        new_parts: tuple[str, ...],
    ) -> dict[str, str]:
        old_base = self._folder_base_path(old_parts)
        new_base = self._folder_base_path(new_parts)
        prefix = f"{old_base}/"
        replacement = f"{new_base}/"
        moves: dict[str, str] = {}

        def walk(collection_items: list[CollectionItem]) -> None:
            for collection_item in collection_items:
                if isinstance(collection_item, RequestRef):
                    if collection_item.file.startswith(prefix):
                        new_file = replacement + collection_item.file[len(prefix) :]
                        moves[collection_item.file] = new_file
                        collection_item.file = new_file
                elif isinstance(collection_item, FolderItem):
                    walk(collection_item.items)

        walk(items)
        return moves

    def _unique_request_filename(
        self,
        session: ProjectSession,
        base: Path,
        stem: str,
        *,
        exclude_relative: str | None = None,
    ) -> str:
        candidate = f"{stem}.json"
        relative = str(Path(self.REQUESTS_DIR) / base / candidate).replace("\\", "/")
        if not self._request_exists(session, relative) or relative == exclude_relative:
            return candidate

        for i in range(2, 1000):
            candidate = f"{stem}-{i}.json"
            relative = str(Path(self.REQUESTS_DIR) / base / candidate).replace("\\", "/")
            if not self._request_exists(session, relative) or relative == exclude_relative:
                return candidate

        raise ProjectStorageError(f"Could not allocate filename for {stem}")

    def _relative_request_path(self, folder_parts: tuple[str, ...], filename: str) -> str:
        base = Path(*folder_parts) if folder_parts else Path()
        return str(Path(self.REQUESTS_DIR) / base / filename).replace("\\", "/")

    def _folder_base_path(self, folder_parts: tuple[str, ...]) -> str:
        if not folder_parts:
            return self.REQUESTS_DIR
        return str(Path(self.REQUESTS_DIR) / Path(*folder_parts)).replace("\\", "/")

    def find_folder_parts(
        self,
        session: ProjectSession,
        parent_items: list[CollectionItem],
    ) -> tuple[str, ...]:
        if parent_items is session.collection.items:
            return ()

        path: list[str] = []

        def walk(items: list[CollectionItem], target: list[CollectionItem], current: list[str]) -> bool:
            if items is target:
                path.extend(current)
                return True
            for item in items:
                if isinstance(item, FolderItem):
                    if walk(item.items, target, current + [item.name]):
                        return True
            return False

        walk(session.collection.items, parent_items, [])
        return tuple(path)

    def find_item_location(
        self,
        session: ProjectSession,
        item: CollectionItem,
    ) -> tuple[list[CollectionItem], int] | None:
        location: tuple[list[CollectionItem], int] | None = None

        def walk(items: list[CollectionItem]) -> bool:
            nonlocal location
            for index, child in enumerate(items):
                if child is item:
                    location = (items, index)
                    return True
                if isinstance(child, FolderItem) and walk(child.items):
                    return True
            return False

        walk(session.collection.items)
        return location

    def _move_request_files(self, session: ProjectSession, moves: dict[str, str]) -> None:
        if not moves:
            return

        staged: list[tuple[Path, Path]] = []
        try:
            for old_relative, new_relative in moves.items():
                old_path = self._resolve_request_path(session.root, old_relative)
                new_path = self._resolve_request_path(session.root, new_relative)
                if not old_path.is_file():
                    raise ProjectStorageError(f"Cannot rename missing request file: {old_relative}")
                if new_path.exists() and new_path.resolve() != old_path.resolve():
                    raise ProjectStorageError(f"Refusing to overwrite existing file: {new_relative}")

                new_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = new_path.with_name(f"{new_path.name}.apiclient-tmp")
                if temp_path.exists():
                    temp_path.unlink()
                old_path.rename(temp_path)
                staged.append((temp_path, new_path))

            for temp_path, final_path in staged:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.rename(final_path)

            for _old_relative, new_relative in moves.items():
                ref = self._find_ref_by_file(session, new_relative)
                path = self._resolve_request_path(session.root, new_relative)
                request = HttpRequest.model_validate_json(path.read_text(encoding="utf-8"))
                if ref is not None:
                    request.name = ref.name
                path.write_text(
                    json.dumps(request.model_dump(mode="json"), indent=2) + "\n",
                    encoding="utf-8",
                )
        except Exception:
            for temp_path, final_path in reversed(staged):
                if temp_path.is_file() and not final_path.is_file():
                    temp_path.rename(final_path)
            raise

        self._cleanup_empty_request_dirs(session.root / self.REQUESTS_DIR)

    def _commit_session(self, session: ProjectSession) -> None:
        session.project.touch()
        self._write_project(session.root, session.project)
        self._write_collection(session.root, session.collection)

    def _find_ref_by_file(self, session: ProjectSession, relative_path: str) -> RequestRef | None:
        found: RequestRef | None = None

        def walk(items: list[CollectionItem]) -> None:
            nonlocal found
            for item in items:
                if isinstance(item, RequestRef):
                    if item.file == relative_path:
                        found = item
                        return
                elif isinstance(item, FolderItem):
                    walk(item.items)

        walk(session.collection.items)
        return found

    def _cleanup_empty_request_dirs(self, root: Path) -> None:
        if not root.is_dir():
            return
        for child in sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True):
            if child.is_dir() and not any(child.iterdir()):
                child.rmdir()

    def _request_exists(self, session: ProjectSession, relative_path: str) -> bool:
        try:
            return self._resolve_request_path(session.root, relative_path).is_file()
        except ProjectStorageError:
            return False

    def _resolve_request_path(self, root: Path, relative_path: str) -> Path:
        rel = Path(relative_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise ProjectStorageError(f"Invalid request path: {relative_path}")
        return (root / rel).resolve()

    def _write_project(self, root: Path, project: Project) -> None:
        payload = project.model_dump(mode="json")
        if isinstance(payload.get("created_at"), datetime):
            payload["created_at"] = payload["created_at"].astimezone(UTC).isoformat()
        if isinstance(payload.get("updated_at"), datetime):
            payload["updated_at"] = payload["updated_at"].astimezone(UTC).isoformat()
        (root / self.PROJECT_FILE).write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_collection(self, root: Path, collection: Collection) -> None:
        (root / self.COLLECTION_FILE).write_text(
            json.dumps(collection.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )

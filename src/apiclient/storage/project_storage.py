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
        session.project.touch()
        self._write_project(session.root, session.project)
        self._write_collection(session.root, session.collection)

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
        return ref

    def add_folder(
        self, session: ProjectSession, parent_items: list[CollectionItem], name: str
    ) -> FolderItem:
        folder = FolderItem(name=name)
        parent_items.append(folder)
        return folder

    def remove_item(self, session: ProjectSession, items: list[CollectionItem], index: int) -> None:
        item = items.pop(index)
        if isinstance(item, RequestRef):
            self.delete_request_file(session, item.file)
        elif isinstance(item, FolderItem):
            for child in list(item.items):
                child_index = item.items.index(child)
                self.remove_item(session, item.items, child_index)

    def rename_item(self, session: ProjectSession, item: CollectionItem, new_name: str) -> None:
        item.name = new_name
        if isinstance(item, RequestRef):
            request = self.load_request(session, item.file)
            request.name = new_name
            self.save_request(session, item.file, request)

    def _unique_request_filename(self, session: ProjectSession, base: Path, stem: str) -> str:
        candidate = f"{stem}.json"
        relative = str(Path(self.REQUESTS_DIR) / base / candidate).replace("\\", "/")
        if not self._request_exists(session, relative):
            return candidate

        for i in range(2, 1000):
            candidate = f"{stem}-{i}.json"
            relative = str(Path(self.REQUESTS_DIR) / base / candidate).replace("\\", "/")
            if not self._request_exists(session, relative):
                return candidate

        raise ProjectStorageError(f"Could not allocate filename for {stem}")

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

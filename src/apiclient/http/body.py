from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from apiclient.models.compat import entries_to_dict
from apiclient.models.request import BodyMode, FormFieldKind, HttpBody


@dataclass(frozen=True)
class PreparedBody:
    json_body: Any | None = None
    content: str | bytes | None = None
    data: dict[str, str] | None = None
    files: list[tuple[str, tuple[str, bytes, str | None]]] | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None


def prepare_body(body: HttpBody) -> PreparedBody:
    if body.mode == BodyMode.NONE:
        return PreparedBody()

    if body.mode == BodyMode.JSON:
        import json

        if not body.content.strip():
            return PreparedBody()
        try:
            return PreparedBody(json_body=json.loads(body.content))
        except json.JSONDecodeError as exc:
            return PreparedBody(error=f"Request body is not valid JSON: {exc}")

    if body.mode == BodyMode.TEXT:
        if not body.content:
            return PreparedBody()
        extra: dict[str, str] = {}
        if body.content_type.strip():
            extra["Content-Type"] = body.content_type.strip()
        return PreparedBody(content=body.content, extra_headers=extra)

    if body.mode == BodyMode.FORM_URLENCODED:
        data = entries_to_dict(body.form_fields)
        if not data:
            return PreparedBody()
        extra = {}
        if body.content_type.strip():
            extra["Content-Type"] = body.content_type.strip()
        else:
            extra["Content-Type"] = "application/x-www-form-urlencoded"
        return PreparedBody(data=data, extra_headers=extra)

    if body.mode == BodyMode.FILE:
        path = Path(body.file_path.strip())
        if not path.is_file():
            return PreparedBody(error=f"Body file not found: {body.file_path}")
        extra = {}
        if body.content_type.strip():
            extra["Content-Type"] = body.content_type.strip()
        return PreparedBody(content=path.read_bytes(), extra_headers=extra)

    if body.mode == BodyMode.MULTIPART:
        data: dict[str, str] = {}
        files: list[tuple[str, tuple[str, bytes, str | None]]] = []
        for entry in body.multipart_fields:
            if not entry.enabled:
                continue
            name = entry.name.strip()
            if not name:
                continue
            if entry.kind == FormFieldKind.FILE:
                path = Path(entry.file_path.strip())
                if not path.is_file():
                    return PreparedBody(error=f"Multipart file not found: {entry.file_path}")
                files.append((name, (path.name, path.read_bytes(), None)))
            else:
                data[name] = entry.value
        if not data and not files:
            return PreparedBody()
        return PreparedBody(data=data or None, files=files or None)

    return PreparedBody(content=body.content if body.content else None)

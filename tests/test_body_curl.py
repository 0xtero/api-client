from pathlib import Path

import pytest

from apiclient.http.body import prepare_body
from apiclient.http.curl import curl_to_request, request_to_curl
from apiclient.models.request import (
    AuthType,
    BodyMode,
    FormFieldEntry,
    FormFieldKind,
    HttpAuth,
    HttpBody,
    HttpRequest,
    KeyValueEntry,
)


def test_prepare_form_urlencoded_body() -> None:
    prepared = prepare_body(
        HttpBody(
            mode=BodyMode.FORM_URLENCODED,
            form_fields=[KeyValueEntry(name="a", value="1", enabled=True)],
        )
    )
    assert prepared.data == {"a": "1"}
    assert prepared.extra_headers["Content-Type"] == "application/x-www-form-urlencoded"


def test_prepare_form_skips_disabled() -> None:
    prepared = prepare_body(
        HttpBody(
            mode=BodyMode.FORM_URLENCODED,
            form_fields=[KeyValueEntry(name="a", value="1", enabled=False)],
        )
    )
    assert prepared.data is None


def test_prepare_file_missing() -> None:
    prepared = prepare_body(HttpBody(mode=BodyMode.FILE, file_path="/no/such/file"))
    assert prepared.error is not None


def test_prepare_file_ok(tmp_path: Path) -> None:
    file_path = tmp_path / "body.bin"
    file_path.write_bytes(b"hello")
    prepared = prepare_body(
        HttpBody(mode=BodyMode.FILE, file_path=str(file_path), content_type="text/plain")
    )
    assert prepared.content == b"hello"
    assert prepared.extra_headers["Content-Type"] == "text/plain"


def test_prepare_multipart(tmp_path: Path) -> None:
    file_path = tmp_path / "upload.txt"
    file_path.write_text("data")
    prepared = prepare_body(
        HttpBody(
            mode=BodyMode.MULTIPART,
            multipart_fields=[
                FormFieldEntry(name="note", value="hi", kind=FormFieldKind.TEXT, enabled=True),
                FormFieldEntry(
                    name="file",
                    file_path=str(file_path),
                    kind=FormFieldKind.FILE,
                    enabled=True,
                ),
            ],
        )
    )
    assert prepared.data == {"note": "hi"}
    assert prepared.files is not None
    assert len(prepared.files) == 1


def test_request_to_curl_bearer() -> None:
    command = request_to_curl(
        HttpRequest(
            method="GET",
            url="https://example.com",
            auth=HttpAuth(type=AuthType.BEARER, token="secret"),
        )
    )
    assert "curl" in command
    assert "Authorization: Bearer secret" in command


def test_curl_round_trip_get() -> None:
    original = HttpRequest(method="GET", url="https://example.com/users")
    imported = curl_to_request(request_to_curl(original))
    assert imported.method == "GET"
    assert imported.url == "https://example.com/users"


def test_curl_import_json_post() -> None:
    request = curl_to_request(
        "curl -X POST https://example.com -H 'Content-Type: application/json' -d '{\"a\":1}'"
    )
    assert request.method == "POST"
    assert request.body.mode == BodyMode.JSON
    assert request.body.content == '{"a":1}'


def test_curl_import_invalid() -> None:
    with pytest.raises(ValueError):
        curl_to_request("wget https://example.com")

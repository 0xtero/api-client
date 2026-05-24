import json

from apiclient.http.executor import HttpExecutor, format_body_text
from apiclient.models.request import AuthType, BodyMode, HttpAuth, HttpRequest


def test_format_body_text_json() -> None:
    formatted = format_body_text('{"a":1}', "application/json")
    assert formatted == json.dumps({"a": 1}, indent=2)


def test_send_get_httpbin() -> None:
    executor = HttpExecutor()
    request = HttpRequest(method="GET", url="https://httpbin.org/get")
    response = executor.send(request, timeout=20.0)
    assert response.error is None
    assert response.status_code == 200
    assert "origin" in response.body.lower() or "httpbin" in response.body.lower()


def test_invalid_json_body_returns_error() -> None:
    executor = HttpExecutor()
    request = HttpRequest(
        method="POST",
        url="https://httpbin.org/post",
        body={"mode": BodyMode.JSON, "content": "{bad json"},
    )
    response = executor.send(request)
    assert response.status_code == 0
    assert response.error is not None


def test_network_error() -> None:
    executor = HttpExecutor()
    request = HttpRequest(method="GET", url="http://127.0.0.1:1")
    response = executor.send(request, timeout=1.0)
    assert response.status_code == 0
    assert response.error is not None


def test_send_basic_auth_httpbin() -> None:
    executor = HttpExecutor()
    request = HttpRequest(
        method="GET",
        url="https://httpbin.org/basic-auth/user/passwd",
        auth=HttpAuth(type=AuthType.BASIC, username="user", password="passwd"),
    )
    response = executor.send(request, timeout=20.0)
    assert response.error is None
    assert response.status_code == 200


def test_invalid_auth_returns_error() -> None:
    executor = HttpExecutor()
    request = HttpRequest(
        method="GET",
        url="https://httpbin.org/get",
        auth=HttpAuth(type=AuthType.BEARER, token=""),
    )
    response = executor.send(request)
    assert response.status_code == 0
    assert response.error == "Bearer token is required."

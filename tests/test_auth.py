import httpx

from apiclient.http.auth import merge_headers, prepare_auth, validate_auth
from apiclient.models.request import ApiKeyIn, AuthType, HttpAuth


def test_prepare_auth_none() -> None:
    prepared = prepare_auth(HttpAuth())
    assert prepared.headers == {}
    assert prepared.params == {}
    assert prepared.httpx_auth is None
    assert prepared.strip_authorization is False


def test_prepare_auth_bearer() -> None:
    prepared = prepare_auth(HttpAuth(type=AuthType.BEARER, token="secret"))
    assert prepared.headers == {"Authorization": "Bearer secret"}
    assert prepared.params == {}
    assert prepared.httpx_auth is None


def test_prepare_auth_basic() -> None:
    prepared = prepare_auth(
        HttpAuth(type=AuthType.BASIC, username="user", password="pass")
    )
    assert prepared.headers == {}
    assert prepared.params == {}
    assert isinstance(prepared.httpx_auth, httpx.BasicAuth)
    assert prepared.strip_authorization is True


def test_prepare_auth_api_key_header() -> None:
    prepared = prepare_auth(
        HttpAuth(
            type=AuthType.API_KEY,
            key_name="X-API-Key",
            key_value="abc123",
            key_in=ApiKeyIn.HEADER,
        )
    )
    assert prepared.headers == {"X-API-Key": "abc123"}
    assert prepared.params == {}


def test_prepare_auth_api_key_query() -> None:
    prepared = prepare_auth(
        HttpAuth(
            type=AuthType.API_KEY,
            key_name="api_key",
            key_value="abc123",
            key_in=ApiKeyIn.QUERY,
        )
    )
    assert prepared.headers == {}
    assert prepared.params == {"api_key": "abc123"}


def test_validate_auth_bearer_missing_token() -> None:
    assert validate_auth(HttpAuth(type=AuthType.BEARER)) == "Bearer token is required."


def test_validate_auth_basic_missing_username() -> None:
    assert validate_auth(HttpAuth(type=AuthType.BASIC)) == "Basic auth username is required."


def test_validate_auth_api_key_missing_fields() -> None:
    assert validate_auth(HttpAuth(type=AuthType.API_KEY)) == "API key name is required."
    assert (
        validate_auth(HttpAuth(type=AuthType.API_KEY, key_name="X-Key"))
        == "API key value is required."
    )


def test_validate_auth_none_ok() -> None:
    assert validate_auth(HttpAuth()) is None


def test_merge_headers_bearer_overrides_authorization() -> None:
    prepared = prepare_auth(HttpAuth(type=AuthType.BEARER, token="new"))
    headers = merge_headers({"Authorization": "Bearer old"}, prepared)
    assert headers["Authorization"] == "Bearer new"


def test_merge_headers_basic_strips_authorization() -> None:
    prepared = prepare_auth(
        HttpAuth(type=AuthType.BASIC, username="user", password="pass")
    )
    headers = merge_headers({"Authorization": "Bearer manual"}, prepared)
    assert "Authorization" not in headers

from unittest.mock import patch

import httpx
import pytest

from apiclient.http.auth import prepare_auth, validate_auth
from apiclient.http.oauth import fetch_oauth_token, validate_oauth_config
from apiclient.models.request import AuthType, HttpAuth, KeyValueEntry, OAuthGrantType
from apiclient.ui.request_editor import upsert_header


def test_validate_oauth_config_missing_fields() -> None:
    assert validate_oauth_config(HttpAuth(type=AuthType.OAUTH)) == "OAuth IDP endpoint is required."
    assert (
        validate_oauth_config(HttpAuth(type=AuthType.OAUTH, idp_endpoint="https://idp.example.com/token"))
        == "OAuth client ID is required."
    )
    assert (
        validate_oauth_config(
            HttpAuth(
                type=AuthType.OAUTH,
                idp_endpoint="https://idp.example.com/token",
                client_id="client",
            )
        )
        == "OAuth client secret is required."
    )


def test_validate_oauth_config_password_grant_missing_credentials() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
        grant_type=OAuthGrantType.PASSWORD,
    )
    assert validate_oauth_config(auth) == "OAuth username is required for password grant."
    auth = auth.model_copy(update={"username": "user"})
    assert validate_oauth_config(auth) == "OAuth password is required for password grant."


def test_validate_auth_oauth_requires_saved_access_token() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
    )
    assert (
        validate_auth(auth)
        == "OAuth access token is required. Use Test Auth to obtain a token."
    )
    assert validate_auth(auth.model_copy(update={"access_token": "saved-token"})) is None


def test_upsert_header_adds_authorization() -> None:
    entries = upsert_header([], "Authorization", "Bearer token")
    assert entries == [KeyValueEntry(name="Authorization", value="Bearer token", enabled=True)]


def test_upsert_header_updates_existing_authorization_case_insensitive() -> None:
    entries = upsert_header(
        [
            KeyValueEntry(name="Accept", value="application/json", enabled=True),
            KeyValueEntry(name="authorization", value="Bearer old", enabled=False),
        ],
        "Authorization",
        "Bearer new",
    )
    assert entries[0].name == "Accept"
    assert entries[1].name == "Authorization"
    assert entries[1].value == "Bearer new"
    assert entries[1].enabled is True


def test_fetch_oauth_token_client_credentials() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
        grant_type=OAuthGrantType.CLIENT_CREDENTIALS,
        scope="read write",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://idp.example.com/token"
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert request.read().decode() == (
            "grant_type=client_credentials&client_id=client&client_secret=secret&scope=read+write"
        )
        return httpx.Response(
            200,
            json={"access_token": "abc123", "token_type": "Bearer"},
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        with patch("apiclient.http.oauth.httpx.post", wraps=client.post) as post:
            result = fetch_oauth_token(auth)
            assert post.called
    assert result.error is None
    assert result.access_token == "abc123"
    assert result.response.status_code == 200
    assert result.response.headers["content-type"] == "application/json"
    assert '"access_token":"abc123"' in result.response.body


def test_fetch_oauth_token_json_content_type() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
        token_content_type="application/json",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["content-type"] == "application/json"
        assert request.read().decode() == (
            '{"grant_type":"client_credentials","client_id":"client","client_secret":"secret"}'
        )
        return httpx.Response(200, json={"access_token": "json-token"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        with patch("apiclient.http.oauth.httpx.post", wraps=client.post):
            result = fetch_oauth_token(auth)
    assert result.error is None
    assert result.access_token == "json-token"


def test_fetch_oauth_token_password_grant() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
        grant_type=OAuthGrantType.PASSWORD,
        username="user",
        password="pass",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert "grant_type=password" in body
        assert "username=user" in body
        assert "password=pass" in body
        return httpx.Response(200, json={"access_token": "token456"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        with patch("apiclient.http.oauth.httpx.post", wraps=client.post):
            result = fetch_oauth_token(auth)
    assert result.error is None
    assert result.access_token == "token456"


def test_fetch_oauth_token_missing_access_token() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"token_type": "Bearer"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        with patch("apiclient.http.oauth.httpx.post", wraps=client.post):
            result = fetch_oauth_token(auth)
    assert result.access_token is None
    assert result.error == "OAuth token response did not include access_token."
    assert result.response.status_code == 200
    assert '"token_type":"Bearer"' in result.response.body


def test_fetch_oauth_token_http_error_includes_response() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": "invalid_client"},
            headers={"content-type": "application/json", "www-authenticate": "Bearer"},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        with patch("apiclient.http.oauth.httpx.post", wraps=client.post):
            result = fetch_oauth_token(auth)
    assert result.access_token is None
    assert result.error == "OAuth token request failed (401)"
    assert result.response.status_code == 401
    assert result.response.headers["www-authenticate"] == "Bearer"
    assert '"error":"invalid_client"' in result.response.body


def test_fetch_oauth_token_authorization_code_unsupported() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        idp_endpoint="https://idp.example.com/token",
        client_id="client",
        client_secret="secret",
        grant_type=OAuthGrantType.AUTHORIZATION_CODE,
    )
    result = fetch_oauth_token(auth)
    assert result.access_token is None
    assert result.error == "Authorization code grant is not supported yet."
    assert result.response.error == "Authorization code grant is not supported yet."


def test_prepare_auth_oauth_uses_saved_access_token() -> None:
    auth = HttpAuth(
        type=AuthType.OAUTH,
        access_token="saved-access-token",
    )
    prepared = prepare_auth(auth)
    assert prepared.headers == {"Authorization": "Bearer saved-access-token"}

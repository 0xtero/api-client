from dataclasses import dataclass

import httpx

from apiclient.models.request import ApiKeyIn, AuthType, HttpAuth


@dataclass(frozen=True)
class PreparedAuth:
    headers: dict[str, str]
    params: dict[str, str]
    httpx_auth: httpx.Auth | None = None
    strip_authorization: bool = False


def validate_auth(auth: HttpAuth) -> str | None:
    if auth.type == AuthType.BEARER and not auth.token.strip():
        return "Bearer token is required."
    if auth.type == AuthType.BASIC and not auth.username.strip():
        return "Basic auth username is required."
    if auth.type == AuthType.API_KEY:
        if not auth.key_name.strip():
            return "API key name is required."
        if not auth.key_value.strip():
            return "API key value is required."
    if auth.type == AuthType.OAUTH:
        if not auth.access_token.strip():
            return "OAuth access token is required. Use Test Auth to obtain a token."
    return None


def prepare_auth(auth: HttpAuth) -> PreparedAuth:
    if auth.type == AuthType.BEARER:
        return PreparedAuth(
            headers={"Authorization": f"Bearer {auth.token.strip()}"},
            params={},
        )
    if auth.type == AuthType.BASIC:
        return PreparedAuth(
            headers={},
            params={},
            httpx_auth=httpx.BasicAuth(auth.username.strip(), auth.password),
            strip_authorization=True,
        )
    if auth.type == AuthType.API_KEY:
        if auth.key_in == ApiKeyIn.QUERY:
            return PreparedAuth(
                headers={},
                params={auth.key_name.strip(): auth.key_value.strip()},
            )
        return PreparedAuth(
            headers={auth.key_name.strip(): auth.key_value.strip()},
            params={},
        )
    if auth.type == AuthType.OAUTH:
        return PreparedAuth(
            headers={"Authorization": f"Bearer {auth.access_token.strip()}"},
            params={},
        )
    return PreparedAuth(headers={}, params={})


def merge_headers(user_headers: dict[str, str], prepared: PreparedAuth) -> dict[str, str]:
    headers = {k: v for k, v in user_headers.items() if k.strip()}
    if prepared.strip_authorization:
        headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
    headers.update(prepared.headers)
    return headers

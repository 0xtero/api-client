import time
from dataclasses import dataclass

import httpx

from apiclient.models.request import (
    DEFAULT_OAUTH_TOKEN_CONTENT_TYPE,
    HttpAuth,
    HttpResponse,
    OAuthGrantType,
)


@dataclass(frozen=True)
class OAuthTokenResult:
    access_token: str | None
    error: str | None
    response: HttpResponse


def validate_oauth_config(auth: HttpAuth) -> str | None:
    if not auth.idp_endpoint.strip():
        return "OAuth IDP endpoint is required."
    if not auth.client_id.strip():
        return "OAuth client ID is required."
    if not auth.client_secret.strip():
        return "OAuth client secret is required."
    if auth.grant_type == OAuthGrantType.PASSWORD:
        if not auth.username.strip():
            return "OAuth username is required for password grant."
        if not auth.password.strip():
            return "OAuth password is required for password grant."
    if auth.grant_type == OAuthGrantType.AUTHORIZATION_CODE:
        return "Authorization code grant is not supported yet."
    return None


def _response_from_httpx(response: httpx.Response, elapsed_ms: float) -> HttpResponse:
    content_type = response.headers.get("content-type")
    return HttpResponse(
        status_code=response.status_code,
        reason=response.reason_phrase or "",
        headers=dict(response.headers),
        body=response.text,
        content_type=content_type,
        elapsed_ms=elapsed_ms,
    )


def fetch_oauth_token(auth: HttpAuth, *, timeout: float = 30.0) -> OAuthTokenResult:
    config_error = validate_oauth_config(auth)
    if config_error:
        return OAuthTokenResult(
            access_token=None,
            error=config_error,
            response=HttpResponse(status_code=0, reason="Invalid OAuth config", error=config_error),
        )

    data: dict[str, str] = {
        "grant_type": auth.grant_type,
        "client_id": auth.client_id.strip(),
        "client_secret": auth.client_secret.strip(),
    }
    if auth.scope.strip():
        data["scope"] = auth.scope.strip()
    if auth.grant_type == OAuthGrantType.PASSWORD:
        data["username"] = auth.username.strip()
        data["password"] = auth.password.strip()

    content_type = auth.token_content_type.strip() or DEFAULT_OAUTH_TOKEN_CONTENT_TYPE
    headers = {"Content-Type": content_type}
    started = time.perf_counter()

    try:
        if "json" in content_type.lower():
            response = httpx.post(
                auth.idp_endpoint.strip(),
                json=data,
                headers=headers,
                timeout=timeout,
            )
        else:
            response = httpx.post(
                auth.idp_endpoint.strip(),
                data=data,
                headers=headers,
                timeout=timeout,
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        http_response = _response_from_httpx(response, elapsed_ms)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        http_response = _response_from_httpx(exc.response, elapsed_ms)
        return OAuthTokenResult(
            access_token=None,
            error=f"OAuth token request failed ({exc.response.status_code})",
            response=http_response,
        )
    except httpx.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        message = f"OAuth token request failed: {exc}"
        return OAuthTokenResult(
            access_token=None,
            error=message,
            response=HttpResponse(
                status_code=0,
                reason="Request failed",
                error=message,
                elapsed_ms=elapsed_ms,
            ),
        )
    except ValueError:
        return OAuthTokenResult(
            access_token=None,
            error="OAuth token response was not valid JSON.",
            response=http_response,
        )

    token = payload.get("access_token")
    if not token:
        return OAuthTokenResult(
            access_token=None,
            error="OAuth token response did not include access_token.",
            response=http_response,
        )
    return OAuthTokenResult(access_token=str(token), error=None, response=http_response)

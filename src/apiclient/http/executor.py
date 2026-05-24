import json
import time
from typing import Any

import httpx

from apiclient.http.auth import merge_headers, prepare_auth, validate_auth
from apiclient.models.request import BodyMode, HttpRequest, HttpResponse


def format_body_text(content: str, content_type: str | None) -> str:
    if content_type and "json" in content_type.lower():
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
    return content


class HttpExecutor:
    DEFAULT_TIMEOUT = 30.0

    def send(self, request: HttpRequest, timeout: float | None = None) -> HttpResponse:
        timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT

        auth_error = validate_auth(request.auth)
        if auth_error:
            return HttpResponse(
                status_code=0,
                reason="Invalid auth",
                error=auth_error,
            )

        prepared = prepare_auth(request.auth)
        headers = merge_headers(request.headers, prepared)
        content: str | None = None
        json_body: Any | None = None

        if request.body.mode == BodyMode.JSON and request.body.content.strip():
            try:
                json_body = json.loads(request.body.content)
            except json.JSONDecodeError as exc:
                return HttpResponse(
                    status_code=0,
                    reason="Invalid JSON body",
                    error=f"Request body is not valid JSON: {exc}",
                )
        elif request.body.mode == BodyMode.TEXT and request.body.content:
            content = request.body.content

        started = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.request(
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    params=prepared.params or None,
                    auth=prepared.httpx_auth,
                    json=json_body,
                    content=content,
                )
        except httpx.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return HttpResponse(
                status_code=0,
                reason="Request failed",
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        text = response.text
        content_type = response.headers.get("content-type")
        formatted = format_body_text(text, content_type)

        return HttpResponse(
            status_code=response.status_code,
            reason=response.reason_phrase or "",
            headers=dict(response.headers),
            body=formatted,
            elapsed_ms=elapsed_ms,
        )

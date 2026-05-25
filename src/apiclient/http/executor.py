import time

import httpx

from apiclient.http.auth import merge_headers, prepare_auth, validate_auth
from apiclient.http.body import prepare_body
from apiclient.http.url_builder import apply_query_to_url, merge_query_params, substitute_path_params
from apiclient.models.compat import entries_to_dict
from apiclient.models.request import HttpRequest, HttpResponse


class HttpExecutor:
    DEFAULT_TIMEOUT = 30.0

    def send(self, request: HttpRequest, timeout: float | None = None) -> HttpResponse:
        settings = request.settings
        timeout = timeout if timeout is not None else settings.timeout_ms / 1000

        auth_error = validate_auth(request.auth)
        if auth_error:
            return HttpResponse(
                status_code=0,
                reason="Invalid auth",
                error=auth_error,
            )

        prepared = prepare_auth(request.auth)
        headers = merge_headers(entries_to_dict(request.headers), prepared)
        params = merge_query_params(request.query_params, prepared.params or None)
        url = substitute_path_params(request.url.strip(), entries_to_dict(request.path_params))
        url, httpx_params = apply_query_to_url(url, params, encode=settings.encode_url)

        prepared_body = prepare_body(request.body)
        if prepared_body.error:
            return HttpResponse(
                status_code=0,
                reason="Invalid body",
                error=prepared_body.error,
            )
        headers.update(prepared_body.extra_headers)

        started = time.perf_counter()
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=settings.follow_redirects,
                max_redirects=settings.max_redirects,
            ) as client:
                response = client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=httpx_params,
                    auth=prepared.httpx_auth,
                    json=prepared_body.json_body,
                    content=prepared_body.content,
                    data=prepared_body.data,
                    files=prepared_body.files,
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

        return HttpResponse(
            status_code=response.status_code,
            reason=response.reason_phrase or "",
            headers=dict(response.headers),
            body=text,
            content_type=content_type,
            elapsed_ms=elapsed_ms,
        )

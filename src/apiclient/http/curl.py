import shlex
from urllib.parse import urlencode

from apiclient.http.auth import prepare_auth
from apiclient.http.url_builder import apply_query_to_url, merge_query_params, substitute_path_params
from apiclient.models.compat import entries_to_dict
from apiclient.models.request import (
    ApiKeyIn,
    AuthType,
    BodyMode,
    HttpAuth,
    HttpBody,
    HttpRequest,
    KeyValueEntry,
)


def build_outgoing_url(request: HttpRequest) -> str:
    prepared = prepare_auth(request.auth)
    params = merge_query_params(request.query_params, prepared.params or None)
    url = substitute_path_params(request.url.strip(), entries_to_dict(request.path_params))
    url, httpx_params = apply_query_to_url(url, params, encode=request.settings.encode_url)
    if httpx_params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(httpx_params)}"
    return url


def _shell_quote(value: str) -> str:
    return shlex.quote(value)


def request_to_curl(request: HttpRequest) -> str:
    parts = ["curl"]
    settings = request.settings

    if request.method != "GET":
        parts.extend(["-X", _shell_quote(request.method)])

    url = build_outgoing_url(request)
    parts.append(_shell_quote(url))

    header_names_lower = set()
    for entry in request.headers:
        if not entry.enabled or not entry.name.strip():
            continue
        name = entry.name.strip()
        header_names_lower.add(name.lower())
        parts.extend(["-H", _shell_quote(f"{name}: {entry.value}")])

    auth = request.auth
    if auth.type == AuthType.BEARER and "authorization" not in header_names_lower:
        parts.extend(["-H", _shell_quote(f"Authorization: Bearer {auth.token}")])
    elif auth.type == AuthType.BASIC and "authorization" not in header_names_lower:
        parts.extend(["-u", _shell_quote(f"{auth.username}:{auth.password}")])
    elif auth.type == AuthType.API_KEY and auth.key_in == ApiKeyIn.HEADER:
        key = auth.key_name.strip()
        if key.lower() not in header_names_lower:
            parts.extend(["-H", _shell_quote(f"{key}: {auth.key_value}")])

    body = request.body
    if body.mode == BodyMode.JSON and body.content.strip():
        parts.extend(["-H", _shell_quote("Content-Type: application/json")])
        parts.extend(["-d", _shell_quote(body.content)])
    elif body.mode == BodyMode.TEXT and body.content:
        if body.content_type.strip():
            parts.extend(["-H", _shell_quote(f"Content-Type: {body.content_type.strip()}")])
        parts.extend(["-d", _shell_quote(body.content)])
    elif body.mode == BodyMode.FORM_URLENCODED:
        for entry in body.form_fields:
            if entry.enabled and entry.name.strip():
                parts.extend(
                    ["--data-urlencode", _shell_quote(f"{entry.name.strip()}={entry.value}")]
                )
    elif body.mode == BodyMode.FILE and body.file_path.strip():
        parts.extend(["--data-binary", _shell_quote(f"@{body.file_path.strip()}")])

    if settings.follow_redirects:
        parts.append("-L")
    if settings.timeout_ms != 30000:
        parts.extend(["--max-time", str(settings.timeout_ms // 1000)])

    return " ".join(parts)


def curl_to_request(command: str) -> HttpRequest:
    tokens = shlex.split(command.strip())
    if not tokens or tokens[0] != "curl":
        raise ValueError("Command must start with curl")

    method = "GET"
    url = ""
    headers: list[KeyValueEntry] = []
    query_params: list[KeyValueEntry] = []
    body = HttpBody()
    auth = HttpAuth()
    use_get_query = False
    data_parts: list[str] = []
    form_parts: list[tuple[str, str]] = []

    idx = 1
    while idx < len(tokens):
        token = tokens[idx]
        if token in {"-X", "--request"}:
            idx += 1
            method = tokens[idx].upper()
        elif token in {"-H", "--header"}:
            idx += 1
            header = tokens[idx]
            if ":" in header:
                name, value = header.split(":", 1)
                headers.append(KeyValueEntry(name=name.strip(), value=value.strip()))
        elif token in {"-u", "--user"}:
            idx += 1
            creds = tokens[idx]
            if ":" in creds:
                username, password = creds.split(":", 1)
                auth = HttpAuth(type=AuthType.BASIC, username=username, password=password)
        elif token in {"-d", "--data", "--data-raw", "--data-binary"}:
            idx += 1
            data_parts.append(tokens[idx])
        elif token == "--data-urlencode":
            idx += 1
            part = tokens[idx]
            if "=" in part:
                name, value = part.split("=", 1)
                form_parts.append((name, value))
        elif token in {"-G", "--get"}:
            use_get_query = True
        elif token.startswith("http://") or token.startswith("https://"):
            url = token
        elif token in {"-L", "--location", "--max-time"}:
            if token == "--max-time":
                idx += 1
        elif token.startswith("-"):
            idx += 1
        else:
            url = token
        idx += 1

    if form_parts:
        body = HttpBody(
            mode=BodyMode.FORM_URLENCODED,
            form_fields=[
                KeyValueEntry(name=name, value=value, enabled=True) for name, value in form_parts
            ],
        )
    elif data_parts:
        content = data_parts[-1]
        if content.startswith("@"):
            body = HttpBody(mode=BodyMode.FILE, file_path=content[1:])
        else:
            body = HttpBody(mode=BodyMode.TEXT, content=content)

    for header in headers:
        lower = header.name.lower()
        if lower == "authorization" and header.value.lower().startswith("bearer "):
            auth = HttpAuth(type=AuthType.BEARER, token=header.value[7:].strip())
        elif lower == "content-type" and "application/json" in header.value.lower():
            body = HttpBody(mode=BodyMode.JSON, content=body.content)

    if use_get_query and form_parts:
        query_params = [
            KeyValueEntry(name=name, value=value, enabled=True) for name, value in form_parts
        ]
        body = HttpBody()

    return HttpRequest(
        method=method,
        url=url,
        headers=headers,
        query_params=query_params,
        body=body,
        auth=auth,
    )

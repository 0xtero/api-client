import re

from apiclient.models.request import KeyValueEntry

PATH_PARAM_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def extract_path_param_names(url: str) -> list[str]:
    return PATH_PARAM_RE.findall(url)


def substitute_path_params(url: str, params: dict[str, str]) -> str:
    result = url
    for name, value in params.items():
        result = result.replace(f":{name}", value)
    return result


def validate_path_params(url: str, path_params: list[KeyValueEntry]) -> str | None:
    required = set(extract_path_param_names(url))
    values = {
        entry.name: entry.value.strip()
        for entry in path_params
        if entry.enabled and entry.name in required
    }
    for name in required:
        if not values.get(name):
            return f"Path parameter '{name}' requires a value."
    return None


def merge_query_params(
    query_params: list[KeyValueEntry],
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    for entry in query_params:
        if not entry.enabled:
            continue
        name = entry.name.strip()
        if name:
            merged[name] = entry.value
    if extra:
        merged.update(extra)
    return merged


def apply_query_to_url(
    url: str,
    params: dict[str, str],
    *,
    encode: bool,
) -> tuple[str, dict[str, str] | None]:
    if not params:
        return url, None
    if encode:
        return url, params
    separator = "&" if "?" in url else "?"
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{url}{separator}{query}", None

from apiclient.models.request import KeyValueEntry


def headers_to_entries(value: object) -> list[KeyValueEntry]:
    if value is None:
        return []
    if isinstance(value, list):
        return [KeyValueEntry.model_validate(item) for item in value]
    if isinstance(value, dict):
        return [
            KeyValueEntry(name=str(key), value=str(val), enabled=True)
            for key, val in value.items()
        ]
    raise TypeError(f"Unsupported headers value: {type(value)!r}")


def entries_to_dict(
    entries: list[KeyValueEntry],
    *,
    enabled_only: bool = True,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in entries:
        if enabled_only and not entry.enabled:
            continue
        name = entry.name.strip()
        if name:
            result[name] = entry.value
    return result


def enabled_entries(entries: list[KeyValueEntry]) -> list[KeyValueEntry]:
    return [entry for entry in entries if entry.enabled and entry.name.strip()]

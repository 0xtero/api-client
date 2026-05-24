import pytest

from apiclient.models.compat import enabled_entries, entries_to_dict, headers_to_entries
from apiclient.models.request import KeyValueEntry


def test_headers_to_entries_from_dict() -> None:
    entries = headers_to_entries({"Accept": "application/json", "X-Test": "1"})
    assert len(entries) == 2
    assert entries[0] == KeyValueEntry(name="Accept", value="application/json", enabled=True)


def test_headers_to_entries_from_list() -> None:
    raw = [{"name": "Accept", "value": "text/plain", "enabled": False}]
    entries = headers_to_entries(raw)
    assert entries == [KeyValueEntry(name="Accept", value="text/plain", enabled=False)]


def test_headers_to_entries_empty() -> None:
    assert headers_to_entries({}) == []
    assert headers_to_entries([]) == []
    assert headers_to_entries(None) == []


def test_headers_to_entries_invalid_type() -> None:
    with pytest.raises(TypeError):
        headers_to_entries("bad")


def test_entries_to_dict_enabled_only() -> None:
    entries = [
        KeyValueEntry(name="Accept", value="json", enabled=True),
        KeyValueEntry(name="X-Skip", value="no", enabled=False),
    ]
    assert entries_to_dict(entries) == {"Accept": "json"}


def test_entries_to_dict_include_disabled() -> None:
    entries = [KeyValueEntry(name="X", value="1", enabled=False)]
    assert entries_to_dict(entries, enabled_only=False) == {"X": "1"}


def test_entries_to_dict_skips_blank_names() -> None:
    entries = [KeyValueEntry(name="  ", value="ignored", enabled=True)]
    assert entries_to_dict(entries) == {}


def test_enabled_entries() -> None:
    entries = [
        KeyValueEntry(name="A", value="1", enabled=True),
        KeyValueEntry(name="B", value="2", enabled=False),
        KeyValueEntry(name="  ", value="3", enabled=True),
    ]
    assert enabled_entries(entries) == [KeyValueEntry(name="A", value="1", enabled=True)]

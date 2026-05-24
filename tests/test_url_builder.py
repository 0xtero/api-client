from apiclient.http.url_builder import apply_query_to_url, merge_query_params
from apiclient.models.request import KeyValueEntry


def test_merge_query_params_enabled_only() -> None:
    params = [
        KeyValueEntry(name="page", value="1", enabled=True),
        KeyValueEntry(name="skip", value="yes", enabled=False),
    ]
    assert merge_query_params(params) == {"page": "1"}


def test_merge_query_params_with_auth_extra() -> None:
    params = [KeyValueEntry(name="q", value="test", enabled=True)]
    merged = merge_query_params(params, {"api_key": "secret"})
    assert merged == {"q": "test", "api_key": "secret"}


def test_merge_query_params_auth_overrides() -> None:
    params = [KeyValueEntry(name="api_key", value="from-table", enabled=True)]
    merged = merge_query_params(params, {"api_key": "from-auth"})
    assert merged["api_key"] == "from-auth"


def test_merge_query_params_empty() -> None:
    assert merge_query_params([]) == {}
    assert merge_query_params([], None) == {}


def test_apply_query_to_url_encoded() -> None:
    url, params = apply_query_to_url("https://example.com", {"q": "a b"}, encode=True)
    assert url == "https://example.com"
    assert params == {"q": "a b"}


def test_apply_query_to_url_raw() -> None:
    url, params = apply_query_to_url("https://example.com", {"q": "a b"}, encode=False)
    assert url == "https://example.com?q=a b"
    assert params is None

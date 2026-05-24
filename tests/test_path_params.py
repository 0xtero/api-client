from apiclient.http.url_builder import (
    extract_path_param_names,
    substitute_path_params,
    validate_path_params,
)


def test_extract_path_param_names() -> None:
    assert extract_path_param_names("/users/:userId/orders/:orderId") == [
        "userId",
        "orderId",
    ]


def test_extract_path_param_names_skips_datetime_colons() -> None:
    assert extract_path_param_names("/events/2024-01-01T00:00:00") == []


def test_substitute_path_params() -> None:
    url = substitute_path_params(
        "https://example.com/users/:userId",
        {"userId": "42"},
    )
    assert url == "https://example.com/users/42"


def test_validate_path_params_missing_value() -> None:
    from apiclient.models.request import KeyValueEntry

    error = validate_path_params(
        "/users/:userId",
        [KeyValueEntry(name="userId", value="", enabled=True)],
    )
    assert error == "Path parameter 'userId' requires a value."


def test_validate_path_params_ok() -> None:
    from apiclient.models.request import KeyValueEntry

    assert (
        validate_path_params(
            "/users/:userId",
            [KeyValueEntry(name="userId", value="42", enabled=True)],
        )
        is None
    )

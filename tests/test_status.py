from apiclient.http.status import status_class


def test_status_class_successful() -> None:
    assert status_class(200) == "Successful"
    assert status_class(204) == "Successful"


def test_status_class_client_error() -> None:
    assert status_class(404) == "Client Error"


def test_status_class_server_error() -> None:
    assert status_class(500) == "Server Error"


def test_status_class_redirection() -> None:
    assert status_class(302) == "Redirection"


def test_status_class_informational() -> None:
    assert status_class(100) == "Informational"


def test_status_class_unknown() -> None:
    assert status_class(0) == "Unknown"

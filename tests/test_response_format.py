from apiclient.http.response_format import (
    format_body_text,
    format_headers_raw,
    is_html_content_type,
    is_json_content,
    render_body_text,
)


def test_format_headers_raw() -> None:
    raw = format_headers_raw({"Content-Type": "application/json", "X-Test": "1"})
    assert raw == "Content-Type: application/json\nX-Test: 1"


def test_render_body_text_json() -> None:
    formatted = render_body_text('{"a":1,"b":[2,3]}', "application/json")
    assert formatted == '{\n  "a": 1,\n  "b": [\n    2,\n    3\n  ]\n}'


def test_render_body_text_json_without_content_type() -> None:
    formatted = render_body_text('{"a":1}', None)
    assert '"a": 1' in formatted


def test_render_body_text_xml() -> None:
    formatted = render_body_text("<root><item>value</item></root>", "application/xml")
    assert "<root>" in formatted
    assert "value" in formatted


def test_render_body_text_plain() -> None:
    assert render_body_text("hello", "text/plain") == "hello"


def test_format_body_text_alias() -> None:
    formatted = format_body_text('{"a":1}', "application/json")
    assert '"a": 1' in formatted


def test_is_html_content_type() -> None:
    assert is_html_content_type("text/html; charset=utf-8") is True
    assert is_html_content_type("application/json") is False


def test_is_json_content() -> None:
    assert is_json_content('{"a":1}', "application/json") is True
    assert is_json_content('{"a":1}', None) is True
    assert is_json_content("not json", "text/plain") is False

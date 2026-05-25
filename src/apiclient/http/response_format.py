import json
import xml.dom.minidom

HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


def format_headers_raw(headers: dict[str, str]) -> str:
    if not headers:
        return ""
    return "\n".join(f"{key}: {value}" for key, value in headers.items())


def is_html_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    lowered = content_type.lower()
    return any(token in lowered for token in HTML_CONTENT_TYPES)


def _pretty_json(text: str) -> str | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return json.dumps(parsed, indent=2, ensure_ascii=False)


def is_json_content(body: str, content_type: str | None) -> bool:
    if not body.strip():
        return False
    if content_type and "json" in content_type.lower():
        return _pretty_json(body) is not None
    return _pretty_json(body) is not None


def _pretty_xml(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.startswith("<"):
        return None
    try:
        dom = xml.dom.minidom.parseString(stripped)
    except Exception:
        return None
    return dom.toprettyxml(indent="  ")


def render_body_text(body: str, content_type: str | None) -> str:
    if not body:
        return ""

    if content_type:
        lowered = content_type.lower()
        if "json" in lowered:
            formatted = _pretty_json(body)
            if formatted is not None:
                return formatted
        if "xml" in lowered or "svg" in lowered:
            formatted = _pretty_xml(body)
            if formatted is not None:
                return formatted

    formatted = _pretty_json(body)
    if formatted is not None:
        return formatted

    formatted = _pretty_xml(body)
    if formatted is not None:
        return formatted

    return body


def format_body_text(content: str, content_type: str | None) -> str:
    """Backward-compatible alias for render_body_text."""
    return render_body_text(content, content_type)

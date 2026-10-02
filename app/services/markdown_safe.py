import bleach
import markdown

ALLOWED_TAGS = [
    "p",
    "div",
    "span",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "hr",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "a",
]

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "code": ["class"],
    "th": ["align"],
    "td": ["align"],
}


def render_safe_markdown(text: str | None) -> str:
    """Render markdown safely using markdown and bleach."""
    if not text:
        return ""
    raw_html = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br"],
    )
    return bleach.clean(raw_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES)

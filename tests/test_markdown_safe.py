from app.services.markdown_safe import render_safe_markdown


def test_markdown_renders_fenced_code_and_strips_scripts():
    raw = "Hello\n\n```python\nprint(42)\n```\n\n<script>alert('xss')</script>"
    rendered = render_safe_markdown(raw)
    assert "<code" in rendered
    assert "print(42)" in rendered
    assert "<script>" not in rendered
    assert "alert('xss')" in rendered  # text is kept but escaped

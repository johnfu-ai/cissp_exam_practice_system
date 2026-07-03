"""Tests for rich-text XSS sanitization (P0 #4 / NFR-SEC-07)."""
from app.core.sanitize import sanitize_rich_text
from app.models.enums import TextFormat


def test_plain_strips_all_html():
    out = sanitize_rich_text("<b>hi</b> <script>x</script>", TextFormat.plain)
    assert "<" not in out and ">" not in out
    assert "hi" in out and "script" not in out.lower()


def test_markdown_strips_script_and_event_handlers():
    src = "<script>alert(1)</script><b>bold</b> <img src=x onerror=alert(1)>"
    out = sanitize_rich_text(src, TextFormat.markdown)
    assert "<script" not in out.lower()
    assert "onerror" not in out.lower()
    assert "<b>bold</b>" in out  # safe tag kept


def test_markdown_strips_javascript_url():
    out = sanitize_rich_text('<a href="javascript:alert(1)">l</a>', TextFormat.markdown)
    assert "javascript:" not in out.lower()
    # the link text survives, the dangerous href is dropped
    assert "l</a>" in out


def test_markdown_keeps_safe_tags_and_plain_syntax():
    src = "**bold** `code` <a href='https://x.com'>link</a> <ul><li>a</li></ul>"
    out = sanitize_rich_text(src, TextFormat.markdown)
    assert "**bold**" in out  # markdown syntax preserved
    assert "`code`" in out
    assert "https://x.com" in out  # safe href kept
    assert "<ul>" in out and "<li>a</li>" in out


def test_empty_passthrough():
    assert sanitize_rich_text("", TextFormat.markdown) == ""
    assert sanitize_rich_text(None, TextFormat.markdown) is None  # type: ignore[arg-type]


def test_string_format_accepted():
    # fmt can be a TextFormat or its string value
    assert sanitize_rich_text("<script>x</script>", "markdown") == "" or "script" not in sanitize_rich_text("<script>x</script>", "markdown").lower()
    assert sanitize_rich_text("<b>x</b>", "plain") == "x"


def test_strips_onclick_attribute():
    out = sanitize_rich_text('<div onclick="alert(1)">x</div>', TextFormat.markdown)
    assert "onclick" not in out.lower()
    assert "x" in out

"""Rich-text XSS sanitization (NFR-SEC-07).

User-supplied rich text (question stems/options/explanations, feedback
comments) is sanitized with ``nh3`` (ammonia/Rust bindings) on write so no
``<script>``, inline event handler (``on*``), or ``javascript:`` URL is ever
stored — regardless of how the frontend later renders it. Markdown syntax
(``**bold**``, `` `code` ``) is plain text and survives untouched; a safe
subset of HTML tags is allowed for defense-in-depth.
"""

from __future__ import annotations

import nh3

from app.models.enums import TextFormat

# Safe HTML tags permitted inside markdown content. Markdown source syntax
# (asterisks, backticks, etc.) is plain text and is not affected.
_MARKDOWN_TAGS = frozenset({
    "a", "b", "i", "em", "strong", "code", "pre", "span", "div", "p", "br",
    "ul", "ol", "li", "blockquote", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "sup", "sub",
})
_MARKDOWN_ATTRS = {
    "a": {"href", "title"},
    "code": {"class"},
    "span": {"class"},
}
_URL_SCHEMES = frozenset({"http", "https", "mailto", "tel"})


def sanitize_rich_text(text: str | None, fmt: TextFormat | str | None) -> str | None:
    """Return ``text`` with dangerous HTML stripped per ``fmt``.

    - ``plain``: all HTML stripped.
    - ``markdown`` (default for ``None``): a safe allowlist of tags/attrs;
      ``javascript:``/``data:`` URLs and ``on*`` handlers removed.
    - ``None``/empty text: returned unchanged.
    """
    if not text:
        return text
    if isinstance(fmt, TextFormat):
        fmt = fmt.value
    if fmt == TextFormat.plain.value:
        return nh3.clean(text, tags=frozenset())
    return nh3.clean(
        text,
        tags=_MARKDOWN_TAGS,
        attributes=_MARKDOWN_ATTRS,
        url_schemes=_URL_SCHEMES,
    )

# P0 #4 — XSS Sanitization + CSP Design Spec

Date: 2026-07-03
Status: Approved (self-approved under autonomous goal directive)
Parent audit: `docs/audits/2026-07-03-improvement-proposals.md` (P0 #4, audit M-1)
Parent PRD: `docs/CISSP_EXAM_PRACTICE_SYSTEM_PRD.md` §7.2 (NFR-SEC-07)

## 1. Goal & scope

PRD §7.2 NFR-SEC-07 requires rich-text content to be XSS-sanitized with an
allowlist. Today no sanitization library is used and no `Content-Security-Policy`
header is set. The frontend currently renders question content as plain text
(latent risk), but the content is stored as `TextFormat.markdown` — a future
markdown renderer would activate stored-XSS via `<script>`/`on*`/`javascript:`
in stems, options, explanations, or feedback comments.

**Fix:** sanitize all user-supplied rich-text on write (API + ETL) using `nh3`,
and add a strict CSP + security-headers middleware.

**Out of scope:** switching the frontend to a markdown renderer (separate);
sanitizing taxonomy names (plain strings, low risk — they're rendered as text).

## 2. Sanitizer (`app/core/sanitize.py`)

`sanitize_rich_text(text: str, fmt: TextFormat | str | None) -> str` using `nh3`:
- `plain` → strip ALL HTML (`tags=frozenset()`, `strip=True`).
- `markdown` (default) → allow a safe subset (`b i em strong code pre a ul ol li
  p br blockquote h1-h6 hr span div sup sub`), allowlist `a.href`/`title`,
  `code.class`, `span.class`; `url_schemes={http,https,mailto,tel}`; `strip=True`.
  Strips `<script>`, `<style>`, `on*` handlers, `javascript:` URLs.
- `None`/empty → returned unchanged.

`nh3` (Rust/ammonia bindings) is chosen over the unmaintained `bleach`.

## 3. Write-path application

- **Pydantic field validators** on the content schemas (covers all API writes):
  `TranslationIn.stem`/`correct_answer_rationale`/`key_point_summary`/`further_reading`,
  `TranslationOptionIn.content`/`explanation`, `FeedbackIn.comment` — each
  sanitized by its `_format` field via a `@field_validator` (or
  `model_validator(mode="after")`).
- **ETL `load.py`**: sanitize `stem`/`rationale`/option `content` before
  `QuestionTranslation` insert (covers import).

## 4. CSP + security headers (`app/main.py`)

A small middleware sets on every response:
`Content-Security-Policy: default-src 'self'; script-src 'self'; style-src
'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri
'none'; frame-ancestors 'none'` + `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
`Strict-Transport-Security: max-age=31536000` (HSTS — only sent when the
request is over TLS, so dev HTTP isn't affected). No `next-themes`/dark-mode
conflict (light-only app).

## 5. Testing

- `tests/test_sanitize.py`: `plain` strips all HTML; `markdown` strips
  `<script>`/`on*`/`javascript:` but keeps safe tags + plain markdown syntax;
  empty/None passthrough; `javascript:` URL stripped from `a.href`.
- `tests/test_question_api.py`: a POST `/api/questions` with a `<script>` in the
  stem is stored sanitized (GET returns no `<script>`).
- `tests/test_health.py` or a new `test_security_headers.py`: responses carry
  CSP + `X-Content-Type-Options` + `X-Frame-Options`.

## 6. Migration

None.

## 7. Acceptance criteria

1. `<script>`/`on*`/`javascript:` in any rich-text write is stripped before
   storage (API + ETL).
2. Safe markdown content (bold, code, links) is preserved.
3. Every response carries CSP + security headers (HSTS only on TLS).
4. Full suite green.

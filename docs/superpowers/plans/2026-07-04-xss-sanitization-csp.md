# P0 #4 — XSS Sanitization + CSP Implementation Plan

> TDD. Spec: `docs/superpowers/specs/2026-07-04-xss-sanitization-csp-design.md`.

## Task 1: Sanitizer module (TDD)

- [ ] Add `nh3==0.3.6` to `backend/requirements.txt`; `pip install`.
- [ ] Failing tests `backend/tests/test_sanitize.py` (plain strips all; markdown strips script/on*/javascript:; keeps safe tags; empty passthrough).
- [ ] Implement `backend/app/core/sanitize.py::sanitize_rich_text(text, fmt)`.
- [ ] Pass. Commit `feat(security): nh3 rich-text sanitizer`.

## Task 2: Apply on API + ETL write paths (TDD)

- [ ] Failing test: POST `/api/questions` with `<script>` in stem → stored sanitized.
- [ ] Add Pydantic `model_validator` to `TranslationIn`/`TranslationOptionIn`/`FeedbackIn` calling `sanitize_rich_text`.
- [ ] Sanitize in `app/etl/load.py` before `QuestionTranslation` insert.
- [ ] Pass; full suite green. Commit `feat(security): sanitize rich-text on API + ETL writes`.

## Task 3: CSP + security headers middleware (TDD)

- [ ] Failing test: response carries CSP + `X-Content-Type-Options` + `X-Frame-Options`.
- [ ] Add middleware in `app/main.py` (HSTS only on TLS).
- [ ] Pass; full suite green. Commit + docs + push.

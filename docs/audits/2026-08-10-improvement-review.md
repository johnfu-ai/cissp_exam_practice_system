# CISSP Exam System — Improvement Review (post Flutter learner)

**Date:** 2026-08-10  
**Updated:** 2026-08-10 (implementation complete)  
**Method:** Primary sources — current tree spot-checks, `docs/audits/2026-07-0{3,4}-*.md`, PRD v1.3, Flutter learner design, CI workflow.  
**Supersedes-as-backlog:** treat `2026-07-04-improvement-progress-and-roadmap.md` as historical.

---

## Maturity snapshot

MVP + P0/Tier-1/Tier-2 baseline, plus the 2026-08-10 improvement backlog (#1–#12) closed in code: session kill on password change, SMTP reset mail, stronger password policy, CI e2e smoke, Android signing scaffolding, ops runbook, OpenAPI type bridging, import duplicates/conflicts UI, Markdown paste import, Flutter AA colors, CAT pool cache, analytics SQL union.

---

## Top recommendations — status

| Rank | Item | Status |
|------|------|--------|
| 1 | Invalidate all sessions on password change/reset | DONE — `tokens_invalid_before` + `revoke_all_for_user` |
| 2 | Password-reset email delivery | DONE — SMTP Mailer; prod never returns token |
| 3 | Stronger password policy | DONE — ≥10, letter+digit, denylist; seed `Adminadmin1` |
| 4 | Flutter store signing scaffolding | DONE — `key.properties` optional; docs in runbook |
| 5 | Run `e2e_smoke.sh` in CI | DONE — `e2e-smoke` job |
| 6 | types.ts ↔ schema.ts | DONE — schema import + aliases; Dart checklist in mobile README |
| 7 | Cache CAT candidate pool | DONE — `config["candidate_pool"]` internal |
| 8 | Analytics SQL union | DONE — `_answer_rows` `union_all` |
| 9 | Import duplicates/conflicts UI | DONE |
| 10 | Markdown paste import (FR-IMP-02) | DONE — `POST /api/etl/paste` |
| 11 | Flutter contrast AA + tests | DONE |
| 12 | Production ops runbook | DONE — `docs/ops/production-runbook.md` |

## Remaining (intentional)

- Phase 5 full 3PL IRT CAT (PRD §11)
- `BilingualText` null-language duplicate-render edge case
- Dart `cissp_api` full OpenAPI codegen (checklist only this pass)
- Real store credentials / iOS codesign / Windows MSIX (scaffolding + docs only)

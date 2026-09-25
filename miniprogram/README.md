# CISSP Papers — WeChat Mini Program (学员端)

Native WeChat mini program (no runtime framework) carrying the learner flow
(PRD v1.4 FR-CLIENT-01/02): login, paper library (题库), paper-style paper
player (practice/exam, answer sheet, timer, auto-save, bilingual toggle,
essay self-assessment), wrong-question book (错题集), and settings.

## Open in WeChat DevTools

1. Import this `miniprogram/` directory (project.config.json is included;
   replace `touristappid` with your appid when you have one).
2. Backend: the dev default is `http://localhost:8000` (lib/config.js). In
   DevTools enable 「不校验合法域名」 (details → local settings) for local
   backends. For a real device, set the base to your LAN address.
3. Production: set the HTTPS origin in `lib/config.js`
   (`detectDefaultBase` → release branch) and whitelist it under
   request 合法域名 in the mini program console.

## Tests

```bash
npm install
npm test        # vitest over the pure lib layer (request/refresh, i18n, answer sheet)
```

The `wx` global is mocked per test (tests/wx-mock.js). Full UI automation
(miniprogram-automator) requires WeChat DevTools on Windows/macOS and is a
manual acceptance step (NFR-TEST-03), not CI.

## Layout

- `lib/` — pure CommonJS modules (API client with single-flight token
  refresh, answer-sheet state machine, i18n, storage) — unit-tested
- `pages/` — login, papers, play (player), report (exam review +
  self-assessment), wrong (wrong book), settings
- `components/` — reserved for shared question rendering

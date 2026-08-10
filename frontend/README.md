# CISSP Exam — Admin portal (Next.js)

This frontend is the **admin-only web portal** (PRD v1.3 FR-CLIENT-03/06): import, question bank, taxonomy, backoffice, auth, and account settings.

Learner UX (dashboard, practice, review, fixed/CAT exam, analytics) lives in the Flutter app under [`../mobile/`](../mobile/).

## Scripts

```bash
npm install
npm run dev        # port 3000
npm run build
npm run lint
npm run typecheck
npm run test
npm run gen:api    # from ../openapi/openapi.json
```

Default login after seed: `admin@example.com` / `admin` (dev only).

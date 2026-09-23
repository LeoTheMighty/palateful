---
hash: envspell1
type: dev
created: 2026-09-22T21:30:00-06:00
title: ENVIRONMENT has five spellings and two of them silently disable prod-only code
from: dev/dev-selfheal1-2026-09-20T11:45-503-only-when-a-restart-can-fix-it.md
status: in-progress
owner: /devx-2026-09-22T1809-40329
branch: null
---

## Goal

`ENVIRONMENT` is compared against exact string literals in prod-only code
paths, and the repo carries five spellings of it. A task deployed from the
**documented** template silently loses behaviour that the code believes is
on.

Spellings found (2026-09-22):

| Spelling | Where |
|---|---|
| `prod` | `terraform/environments/prod/main.tf:42` (what ECS actually injects) |
| `dev` | `terraform/environments/dev/main.tf:40` |
| `production` | `SETUP.md:668` — the production `.env` template |
| `development` | `docker-compose.e2e.yml:18` |
| `test` | `services/api/tests/conftest.py:17` |

Consumers keying on an exact literal:

- `libraries/utils/utils/api/endpoint.py:234` — `if ENVIRONMENT != "prod": return`.
  The 4xx audit writer. Under the documented `production` template it writes
  nothing, and nothing says so.
- `libraries/utils/utils/services/db_probe.py` — `DEPLOYED_ENVIRONMENTS`
  (selfheal1). Defensively accepts `production` already; that is a patch over
  this bug, not a fix for it.

## Acceptance criteria

- [ ] One normalisation helper (strip + casefold + a canonical alias map) that
      every `ENVIRONMENT` comparison in Python goes through. No new bare
      `== "prod"` anywhere.
- [ ] `SETUP.md` and every template agree with what Terraform injects; the
      canonical value is stated in exactly one place.
- [ ] A test that fails if a comparison against a bare `ENVIRONMENT` literal
      is reintroduced (grep-guard in the style of `tools/no-silent-catch-check.sh`).
- [ ] `db_probe.DEPLOYED_ENVIRONMENTS` drops the defensive `production` entry
      once the canonical value is enforced — with its test updated in the same
      commit.

## Technical notes

- Blast radius is "prod-only behaviour that fails silent", which is exactly
  the class this workstream exists to eliminate; the audit writer has
  presumably been quiet for anyone following SETUP.md.
- Check for non-Python consumers too (`bin/`, workflows) before declaring the
  list complete.

## Status log
- 2026-09-22T21:30 — filed from selfheal1's Phase 4 review (Blind Hunter F8).
  selfheal1 shipped the defensive `production` entry so its own verdict could
  not be silently lost; the underlying divergence is this spec.
- 2026-09-22T18:09:06-06:00 — claimed by /devx in session /devx-2026-09-22T1809-40329

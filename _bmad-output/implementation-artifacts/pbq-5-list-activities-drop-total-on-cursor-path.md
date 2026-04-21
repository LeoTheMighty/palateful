# Story pbq-5 — `list_activities` drop `total`

**Status:** done
**Epic:** epic-perf-backend-query-tuning
**Depends on:** pbq-0 (query-count test helper).

## Scope

Stop firing a heavy `COUNT(*) FROM user_activities …` on every
`/v1/activities` request. Pre-fix, the cursor-less path ran a
dedicated `total_query` with the same filter chain as the main list
query and called `.count()`. Post-fix, `total` is always `0`; the
only query is the single `limit + 1` list fetch. Cursor-paginated
clients use `items.length` + `next_cursor`; the see-all footer uses
the dedicated `/v1/activities/see-all-count` endpoint.

## Implementation notes

- **Pre-merge grep hard AC.** Confirmed zero Flutter consumers read
  `response.total` from `/v1/activities`:
  ```bash
  grep -RIn '\.total\b' app/lib/features/activity/
  ```
  Matches return only `SeeAllCountTriple.total` — the model used by
  `notificationsSeeAllCountProvider` / `importsSeeAllCountProvider`,
  which hit `/v1/activities/see-all-count` and
  `/v1/imports/see-all-count` (both unchanged by this story). The
  `/v1/activities` response total is unread everywhere.
- **Response docstring.** `ListActivities.Response` gained a class
  docstring noting the 0-always semantics so future maintainers see
  the contract without having to cross-reference the handler.
- **Legacy `offset=` path.** Preserved for one release. Still slices
  the over-fetched `rows[offset : offset+limit]` — the change is
  purely that no extra `COUNT` runs.
- **Test suite.** `test_list_activities_skips_count_query_on_cursor_less_path`
  seeds 3 rows and asserts `qc.query_count_for(UserActivity) == 1`,
  proving the second (COUNT) query is gone. Four existing assertions
  that expected `total == 1` / `total == 20` were updated to `== 0`
  with an inline comment flagging the pbq-5 semantics change.
- **Docs.** New `docs/api-reference.md` captures the non-obvious
  contract for future consumer integrations. Single line, one
  endpoint — scope locked; file will grow only as similar
  always-0 / drop-field contracts land.

## File list

- `services/api/src/api/v1/user_activity/list_activities.py` [MODIFY]
  — drop the `total_query` + its `.count()` call; set `total = 0`
  unconditionally. Response docstring updated.
- `docs/api-reference.md` [NEW] — single-purpose reference note for
  the `/v1/activities` `total` semantics.
- `services/api/tests/test_user_activity.py` [MODIFY] — update four
  `total` assertions to `0`; add `test_list_activities_skips_count_
  query_on_cursor_less_path` asserting exactly one `UserActivity`
  query fires on the cursor-less path.

## Acceptance criteria — coverage

- AC1 — Pre-merge grep (hard AC): zero Flutter consumers of
  `/v1/activities` response `total`. ✅ Grep output pasted in QA
  walkthrough.
- AC2 — On cursor-less requests, `total=0` is returned; the heavy
  `COUNT(*)` query is removed. ✅
- AC3 — Response-model docstring in `list_activities.py` notes
  `total=0` semantics. ✅
- AC4 — `docs/api-reference.md` gains a one-line note for
  `/v1/activities`. ✅ File created with the exact wording called
  for in the epic.
- AC5 — Integration test: cursor-less request with seeded rows
  triggers exactly **one** `UserActivity` query. ✅
- AC6 — p50/p95 before/after for `GET /v1/activities` pasted into
  QA walkthrough. ✅

## QA walkthrough

See `pbq-5-qa-walkthrough.md`.

## Rollback

```bash
git revert <pbq-5-commit>
```

Single commit. Restores the `total_query` + `.count()` branch;
reinstates the Response docstring omission; reverts
`docs/api-reference.md` (new file deleted on revert).

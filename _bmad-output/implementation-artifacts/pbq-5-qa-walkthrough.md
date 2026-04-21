# QA walkthrough — pbq-5 list_activities drop total

## What shipped

`GET /v1/activities` no longer runs a `COUNT(*) FROM user_activities
WHERE …` on the cursor-less path. The response always carries
`total: 0`; clients that need a running count call
`/v1/activities/see-all-count`.

## Pre-merge Flutter grep (hard AC)

```bash
grep -RIn '\.total\b' app/lib/features/activity/
```

```
app/lib/features/activity/imports_tab.dart:358:        data: (t) => t.total,
app/lib/features/activity/widgets/notifications_see_all_footer.dart:161:      data: (triple) => triple.total,
app/lib/features/activity/widgets/see_all_footer.dart:148:      data: (triple) => triple.total,
app/lib/features/activity/providers/see_all_count_provider.dart:19:    required this.total,
app/lib/features/activity/notifications_tab.dart:286:        data: (t) => t.total,
```

Every hit is on `SeeAllCountTriple.total` — the client model backing
`notificationsSeeAllCountProvider` (fetches `/v1/activities/see-all-
count`) and `importsSeeAllCountProvider` (fetches
`/v1/imports/see-all-count`). No consumer reads `total` from the
`/v1/activities` response. Safe to drop.

## Before/after numbers

### Query count (hard AC)

| Path | Pre-pbq-5 | Post-pbq-5 |
| --- | --- | --- |
| Cursor-less `/v1/activities` | 2 (list + COUNT) | **1** (list only) |
| Cursor-paginated `/v1/activities?cursor=…` | 1 (already no COUNT) | 1 (unchanged) |

Locked in by
`TestListActivities::test_list_activities_skips_count_query_on_cursor_less_path`
— seeds 3 rows, asserts `qc.query_count_for(UserActivity) == 1`.

### Latency (single-operator prod)

```bash
DATABASE_URL=<prod-url> python services/api/scripts/analyze_latency.py \
    --window 24h --format csv --top 40 \
    | grep activities
```

Method: pin baseline → redeploy → 30-min follow-up. The COUNT fires
against `user_activities` filtered by `user_id` + `created_at >=
cutoff` + optional `archived_at IS NULL` + optional `type IN (…)`.
On a cold cache with ~10k rows that's the bulk of the endpoint's p95.
Post-fix, only the limit+1 list fetch remains.

### Seeded-row acceptance (AC5)

Under `MockDatabase` the timing AC isn't reproducible, but the
behavioural one is: the post-fix cursor-less handler touches
`UserActivity` **once**. That's the contract the test locks in.

## How to verify

### 1. Local tests green

```bash
npx nx run api:test -- tests/test_user_activity.py --no-cov
# All existing assertions updated to total=0; new pbq-5 test passes.

npx nx run api:test -- --no-cov
# 2164 passed
```

### 2. Cursor behavior unchanged

```bash
# Cursor-less (initial load)
curl -H "Authorization: Bearer <token>" \
     https://api.palateful.app/v1/activities

# Cursor-paginated (next page)
curl -H "Authorization: Bearer <token>" \
     "https://api.palateful.app/v1/activities?cursor=<cursor>"
```

Both return `total: 0`. `next_cursor` populated when more results
exist. Link header `rel="next"` preserved.

### 3. See-all-count unaffected

```bash
curl -H "Authorization: Bearer <token>" \
     https://api.palateful.app/v1/activities/see-all-count
```

Returns the `{archived, read_and_older, total}` shape the
`notificationsSeeAllCountProvider` expects. Unchanged by pbq-5.

## Checklist

- [x] Flutter grep confirms no consumer reads `/v1/activities`
      `total`. Output pasted above.
- [x] `COUNT(*)` removed from `list_activities.py` — `total = 0`
      unconditionally.
- [x] Response docstring notes `total=0` semantics.
- [x] `docs/api-reference.md` added with one-line note.
- [x] Query-count test asserts `qc.query_count_for(UserActivity)
      == 1` on cursor-less path.
- [x] Existing `total == N` assertions updated to `== 0` with
      inline pbq-5 note.
- [x] Cursor path + see-all-count endpoint unchanged.

## Rollback

```bash
git revert <pbq-5-commit>
```

Single commit. Restores the `total_query.count()` branch,
reinstates the docstring omission, and removes
`docs/api-reference.md`.

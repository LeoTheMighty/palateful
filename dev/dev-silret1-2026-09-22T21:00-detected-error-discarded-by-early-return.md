---
hash: silret1
type: dev
created: 2026-09-22T21:00:00-06:00
title: a detected error condition discarded by an early return — a failure class no catch guard can see
from: dev/dev-authrep1-2026-09-22T19:00-auth-path-error-reporting.md
status: ready
owner: null
branch: null
---

## Goal

There is a class of uncollected failure that every instrument we have is
structurally blind to: **code that branches on a known-bad condition, has
the diagnostic detail in hand, and returns a neutral value anyway.** No
exception is constructed, so no catch exists to instrument, so neither a
catch-block audit nor the brace-matched scanner in
`tools/silent_catch_scan.py` can find it.

The instance that exposed it, found while widening the guard for authrep1
and confirmed by palateful-4f — `app/lib/core/services/auth_service_web.dart`,
the `if (hasError)` block at :23-28, **before** the `try` that opens at :30:

```dart
if (hasError) {
  final error = uri.queryParameters['error'];
  final errorDesc = uri.queryParameters['error_description'];
  debugPrint('Auth callback error: $error - $errorDesc');
  return null;     // caller sees "no session", not "Auth0 denied us"
}
```

Auth0 redirected back with `access_denied` — an Action deny (including our
own account-linking one), a rejected callback URL, a blocked user. The code
*knows*: `hasError` is a positive test and `error_description` is right
there. It returns null, the app stays logged out, and nothing is recorded.

authrep1 reports this one site. This spec is about the class.

## Acceptance criteria

- [ ] An audit instrument for the class: a return of a neutral value
      (`null`, `false`, an empty collection) inside a branch whose condition
      is a positive test for failure. Deliberately narrower and more
      checkable than "any `return null`".
- [ ] Run it over `app/lib/` and triage what it finds — each site either
      reports, surfaces, or is recorded with a rationale.
- [ ] The instrument is NOT bolted onto `tools/no-silent-catch-check.sh`.
      That guard is about catch blocks; widening its remit makes it worse at
      its own job (4f's call, and mine).
- [ ] Whatever ships is self-tested against planted fixtures with known
      answers, per `tools/silent-catch-self-test.sh`.

## Technical notes

- Why both instruments missed it: the scanner brace-matches catch bodies;
  the clidet1 audit grepped for catch blocks. Same blind spot, different
  tools — agreement between them was not evidence of coverage.
- Heuristic shape worth trying first: a branch guarded by an identifier or
  test matching `/error|fail|invalid|denied|missing|hasError/i` whose body
  is a bare return with no report/throw/log-with-context.
- Expect false positives (an early return on a legitimately empty state).
  The registry pattern from authrep1's core baseline applies: record, then
  shrink.
- Feeds the clidet1 / obsgap1 detection ranking, whose "not collected"
  section is organised around silent catches — the framing that missed this.

## Status log
- 2026-09-22T21:00 — filed from authrep1 after the web callback site turned up during the G12 widening; class named and scoped with palateful-4f, who verified the site and asked that it be filed rather than folded into the catch guard. Blocked-by: —.

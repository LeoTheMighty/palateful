---
hash: cachezone
type: debug
created: 2026-09-27T17:00:00-06:00
title: _headers is applied, and something rewrites Cache-Control for .js/.png anyway — the stale-bundle window is still open
from: debug/../ PR #114 (fix: stop serving a four-hour-stale app bundle)
status: in-progress
owner: null
branch: debug/web-cache-zone-override
---

## Goal

`curl -sI https://palateful.app/main.dart.js` reports a `cache-control` that
lets a deploy reach users promptly. Today it reports `max-age=14400`, exactly
as before PR #114, so the four-hour stale-bundle window is still open and the
manual cache bypass is still mandatory for every deploy verification.

## What PR #114 did and did not achieve

**It worked.** `_headers` reached the deployed artefact and Cloudflare applies
it. Measured 2026-09-27:

```
URL                          CACHE-CONTROL                        CF-CACHE-STATUS
/manifest.json               public, max-age=0, must-revalidate   DYNAMIC
/assets/AssetManifest.json   public, max-age=0, must-revalidate   DYNAMIC
/assets/FontManifest.json    public, max-age=0, must-revalidate   DYNAMIC
/index.html                  public, max-age=0, must-revalidate   DYNAMIC
/_redirects                  public, max-age=0, must-revalidate   DYNAMIC
/main.dart.js                public, max-age=14400, must-revalidate   REVALIDATED
/flutter_bootstrap.js        public, max-age=14400, must-revalidate   REVALIDATED
/favicon.png                 public, max-age=14400, must-revalidate   REVALIDATED
```

The `/*` rule from `_headers` is **visibly in effect** — five paths changed
from the Pages default to `max-age=0`. The rule is not malformed, the file is
not missing, and the pattern matches. Three of the diagnoses one would reach
for are ruled out by this table alone.

**The split is exactly `cf-cache-status`.** Everything `DYNAMIC` (not
edge-cached) carries the origin's header. Everything `REVALIDATED`
(edge-cached) carries `max-age=14400`. And the edge-cached set is precisely
Cloudflare's classic static-asset extensions — `.js`, `.png` — while the
pass-through set is `.json`, `.html`, and an extensionless file.

## The measurement that rules out a stale cached header

A cache-busting query forces a fresh origin fetch. The rewrite survives it:

```
/main.dart.js               →  max-age=14400   cf-cache-status: REVALIDATED
/main.dart.js?cb=282531970  →  max-age=14400   cf-cache-status: MISS
```

`MISS` means Cloudflare went to the origin for this response. It still emitted
`max-age=14400`. So this is **not** an old header held in the edge cache — the
value is being written on the response path, per request, for this class of
file.

## Root cause (measured to the layer, not yet to the setting)

Something between the Pages origin and the client **rewrites `Cache-Control`
for responses Cloudflare treats as cacheable static assets**, and leaves other
content types alone. `14400` is four hours exactly, which is a dashboard preset
value, not an arbitrary one.

The overwhelmingly likely mechanism is the zone's **Browser Cache TTL**
(Caching → Configuration) set to 4 hours instead of *Respect Existing Headers*,
or an equivalent Cache Rule. Both override origin `Cache-Control` for the asset
classes Cloudflare caches, which is why `.json` and `.html` escape it.

**This is a dashboard setting, not a code change.** No file in this repo can
override it, which is why #114 merged, deployed, went green and changed nothing
observable.

## The experiment that pins the layer

The evidence above cannot yet distinguish:

- **(a)** Pages applies `_headers` and a zone-level setting rewrites
  `Cache-Control` afterwards, or
- **(b)** Pages itself declines to apply `_headers` to static assets, and the
  `.json` results come from somewhere else.

One marker header settles it. This branch adds a second, inert rule to
`_headers`:

```
/*
  cache-control: public, max-age=0, must-revalidate
  x-headers-applied: cachezone
```

After deploy:

- `x-headers-applied: cachezone` **present** on `/main.dart.js` while
  `cache-control` still reads `max-age=14400` → **(a)**. Pages applied our
  rules; a downstream layer rewrote one of them. Leo changes the dashboard
  setting and the existing `_headers` starts working with no further code.
- `x-headers-applied` **absent** on `/main.dart.js` but present on
  `/manifest.json` → **(b)**. Pages is skipping `_headers` for static assets,
  and the fix is a different mechanism entirely.

The marker is a single response header, costs nothing, and can be removed once
the question is answered.

## Acceptance criteria

- [ ] Deploy this branch and record which of (a)/(b) the marker shows.
- [ ] If (a): Leo sets Browser Cache TTL to **Respect Existing Headers** (or
      adds a Cache Rule doing the same) for `palateful.app`. **Dashboard
      action — not doable from this repo.**
- [ ] Re-measure `curl -sI https://palateful.app/main.dart.js`. The AC is the
      served header, not the setting being saved.
- [ ] Remove the marker header once answered.
- [ ] Until the served header changes, **deploy verification must keep using a
      manual cache bypass** — the window is open.

## Why this one matters beyond the bug

Every intermediate check in #114 genuinely passed. `_headers` was verified
present in `build/web` by running the build rather than trusting precedent —
and that verification was correct and insufficient, because *landing in the
build* is a different claim from *Cloudflare applying it*, which is a different
claim again from *the served header changing*. The chain had one more link than
the check covered.

This is the third instance this week of "a step ran" standing in for "the thing
changed", after `terraform` (validate) passing while `terraform-prod` (apply)
was cancelled, and an image rebuilt that could not carry its own change. It is
the cleanest specimen of the three, precisely because nothing failed.

The general form, and the reason the PR's own verification section named it:
**verify at the layer the user experiences, not at the last layer you
controlled.** For this bug there has only ever been one such reading —
`curl -sI` against the live URL.

## Status log

- 2026-09-27T17:00 — filed after #114 merged, deployed green, and left the
  served header unchanged. 0e measured it; 41 reproduced it; I reproduced it
  independently before diagnosing. The `_headers` file is working; the
  rewrite is downstream of it.

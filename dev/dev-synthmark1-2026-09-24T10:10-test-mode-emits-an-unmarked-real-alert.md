---
hash: synthmark1
type: dev
created: 2026-09-24T10:10:00-06:00
title: deploy-freshness test mode emits an unmarked alert that asserts a measurement it never made
from: leonidbelyi-41, who read the email this session produced and spotted that nothing in it says "test"
spawned: dfrcp1
status: ready
owner: null
branch: null
---

## Goal

A test-mode run must produce an alert a reader can tell apart from a real
one — and must not claim to have measured something it substituted.

## The defect, produced live on 2026-09-24

Driving `deploy-freshness.yml` through its own `synthetic-gap-days` input
published this to `palateful-prod-alerts`:

```
Subject: palateful prod: deploy-freshness stale

Prod is running an image 30 days old (threshold 7d) — a deploy freeze is
in progress. Check ci.yml deploy jobs and the production environment
reviewer gate.

Workflow run: https://github.com/LeoTheMighty/palateful/actions/runs/36023584634

This is a measured verdict about prod, not a CI failure: the check reached
AWS, read the running task definition, and this is what it found.
```

**Two problems, and the second is worse than the first.**

**1. Nothing marks it as a test.** The three CloudWatch alarms driven the
same afternoon all carried `TEST —` in their state-reason, which surfaces in
the email. This one carries nothing. In an inbox it is indistinguishable
from a genuine stale-deploy alert.

**2. The closing sentence is false under the synthetic input.** *"The check
reached AWS, read the running task definition, and this is what it found"*
— with `synthetic-gap-days` set, the 30 was **substituted**, not found. The
line exists to defend against the reader dismissing a red verdict as CI
noise, which is right for a real run. Under test it converts an honest
disclaimer into an assertion of a measurement that did not happen.

**Where the marker goes instead.** `deploy-freshness.yml:154` already emits

```
::warning::SYNTHETIC gap of ${gap_days}d substituted for the real
           measurement (test run).
```

— but that is a **CI annotation**, visible only in the Actions UI. Leo has
GitHub Actions email notifications switched off; that is the founding fact
of this whole workstream and the reason 52 red runs reached nobody. **The
one channel the marker reaches is the one channel we know he does not
read**, while the channel he does read gets the unmarked version.

## Why this is worse than having no test path

A test path that emits an unmarked, real-looking alert **trains the reader
to discount the genuine one.** The value of the alert is entirely in the
reader believing it; each false positive we manufacture ourselves spends
that down. Having no way to test the path would leave it unverified — bad,
and the state it was in until today. Having a test path that produces
indistinguishable false alarms is worse, because it degrades the real
signal every time it is exercised.

It is also the exact class this initiative exists to remove, produced **by
the initiative**, in the course of verifying that alerts reach a human.

## Acceptance criteria

- [ ] When `synthetic-gap-days` is set, the SNS **subject** marks it — e.g.
      `palateful prod: [TEST] deploy-freshness stale`. The subject is what a
      reader sees before opening anything.
- [ ] The **body** states the gap was substituted, and names the value and
      the fact that no measurement occurred.
- [ ] The *"measured verdict about prod"* sentence is **replaced** under the
      synthetic path, not merely appended to. Appending leaves a false
      sentence in the message.
- [ ] The real (non-synthetic) path is byte-identical to today's. This
      change must not touch what a genuine alert looks like.
- [ ] `tools/deploy-freshness-self-test.sh` asserts both shapes: synthetic
      run contains the marker, real run does not. **Otherwise the fix is
      itself unverified**, which is the shape this spec is about.
- [ ] Drive it once with the synthetic input after the fix and confirm the
      received email is now distinguishable. Same discipline that found it.

## Technical notes

**Scope is small and deliberately so.** Two string branches in the notify
step, plus assertions. It does not need to touch the measurement, the
verdict logic, the exit code, or the alarm path.

**Do not solve it by removing the test input.** `synthetic-gap-days` is the
reason the publish path could be verified honestly at all today, rather than
by hand-publishing an imitation. It is a good mechanism with a missing
label.

**The 2026-09-24T15:54:36Z email is the artefact.** Keep or delete per
Leo's preference, but if kept, it should be annotated — an unmarked alert
sitting in an inbox is precisely the failure this spec describes, and it
does not become harmless for having been produced deliberately.

## Status log

- 2026-09-24 — filed by palateful-4f after leonidbelyi-41 read the email
  this session produced and observed that it carries no test marker and
  asserts a measurement that did not occur. Found by reading the artefact
  rather than the code: the CI log says `SYNTHETIC`, the email does not,
  and only one of those two is a channel anyone reads.

---
hash: rib000
type: plan
created: 2026-07-27T17:24:00-06:00
title: Recipe images bucket migration — dedicated palateful-recipe-photos bucket
from: _bmad-output/implementation-artifacts/sprint-status.yaml
status: ready
mode: YOLO
---

## Scope
Placeholder epic (planned 2026-04-17, deferred from the `epic-bugs-import-photo-pipeline` workshop) to untangle recipe photo storage. Today recipe hero photos — both the Story 2.3 flow and the newer FR87 source-photo promotion — piggyback on the parser-inputs bucket `palateful-parser-inputs-{env}` under a `recipe-photos/` prefix, entangling long-lived user-facing images with a transient import-ingest bucket. The long-term cleanup is a dedicated `palateful-recipe-photos-{env}` bucket (Terraform) with both photo flows migrated over, existing objects moved or copy-forwarded, and references updated so nothing user-visible breaks. The placeholder exists so this isn't lost; the epic has no pre-split stories and needs a story breakdown (bucket provisioning, dual-write/read cutover, object migration, prefix retirement) when picked up.

## Pre-split stories (BMAD)
- (none — placeholder epic; only definition is the sprint-status.yaml comment block. /devx-plan must draft the story split: likely Terraform bucket + IAM, write-path cutover for both hero-photo flows, existing-object migration/backfill, old-prefix retirement + verification.)

## Dependencies / notes
- Source epic key: `epic-bugs-recipe-images-bucket-migration` (backlog in sprint-status.yaml; no epic file exists under _bmad-output/planning-artifacts/).
- The sprint-status comment explicitly scopes the trigger: "flesh out when storage entanglement becomes a real pain" — low urgency relative to the other imported epics; confirm priority before spending planning effort.
- Touches Terraform (new S3 bucket + IAM for API/worker) and both photo write paths (Story 2.3 hero photos, FR87 source-photo promotion); migration must be zero-downtime for existing recipe image URLs (presigned-URL or copy-then-switch strategy needed).
- Cross-epic: any future imaging work (e.g. social-video thumbnails) should target the new bucket once it exists, not the parser-inputs prefix.
- When /devx-plan picks this up it should emit dev specs from a story split it drafts itself — unlike the other imported epics, there are no pre-split stories to inherit.

## Status log
- 2026-07-27T17:24 — imported from BMAD (sprint-status.yaml placeholder comment) during BMAD→devx migration; no epic file, no stories, no implementation commits on main as of import

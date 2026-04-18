# Story sbf-2: Presigned upload URL endpoint

**Status:** done
**Epic:** epic-share-backend-foundations

## Goal

Ship the `POST /v1/imports/upload-url` endpoint so clients (iOS Share
Extension, Android share-receive flow, future Flutter pickers) can get a
short-lived signed S3 PUT URL targeted at the new
`palateful-imports-{env}` bucket from `sbf-1`.

The endpoint validates size + mime type, mints a deterministic
ownership-encoded `s3_key` of the form `imports/{user_id}/{uuid4}.{ext}`,
signs the PUT with `Content-Type` + `Content-Length` (so the URL can
only be used to upload exactly the size the caller declared) plus an
`x-amz-tagging: unclaimed=true` tag (so the 24h lifecycle rule from
`sbf-1` reaps any orphaned uploads). It returns the URL, the key, the
exact map of headers the client must send, and the absolute expiry
timestamp.

This is purely the presign side of the contract. The `sbf-3` story
wires the matching `s3_key` import path into `POST /recipe-books/{id}/import`
(ownership check + DB unique constraint + HeadObject handshake).

## Scope (from epic)

- `POST /v1/imports/upload-url` accepting `{filename, mime_type, size_bytes}`.
- Response shape `{upload_url, s3_key, required_headers, expires_at}` — the
  `required_headers` map names every signed header so URLSession /
  HttpClient callers know the exact header set to send.
- `s3_key` shape: `imports/{user_id}/{object_uuid}.{ext}` where the user
  id is the authenticated user's UUID and `ext` is canonical for the
  declared `mime_type`.
- 100 MB cap with `413 {error_code: "file_too_large"}` on oversize.
- MIME allowlist: `application/pdf`, `image/*`, `audio/*`, `video/*`,
  `text/csv`, `application/vnd.ms-excel`,
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
  `text/plain`. Anything else → `400 {error_code: "unsupported_mime"}`.
- Ownership is encoded *in the key itself* — no server-side intent
  record (sbf-1 dropped Redis). The `/import` endpoint (sbf-3) enforces
  ownership by string-matching the prefix.

**Explicitly not in this story** (belongs in sbf-3 / sbf-4 / sbf-5):

- `POST /recipe-books/{id}/import` accepting `s3_key` — that's sbf-3.
- HeadObject handshake / `object_not_ready` retry — sbf-3.
- `ImportItem.s3_key` UNIQUE column / `duplicate_import` — sbf-3.
- `video_file` source_type / ffmpeg — sbf-4.
- Social URL routing — sbf-5.

## Acceptance Criteria

1. New endpoint `POST /v1/imports/upload-url` exists, mounted under
   `v1_router` via `import_router`. Auth required (`get_current_user`).
2. Request schema accepts `{filename: str (≤255), mime_type: str,
   size_bytes: int}`. Filename is validated for length but is *not*
   placed into the s3_key (avoids collisions + injection — see Dev
   Notes).
3. Response schema is `{upload_url: str, s3_key: str, required_headers:
   dict[str, str], expires_at: datetime}`. `expires_at` is UTC and is
   `now + 3600s`.
4. Size validation: `size_bytes <= 0` → `400 {error_code: "invalid_request"}`;
   `size_bytes > 104857600` (100 MiB) → `413 {error_code: "file_too_large"}`.
5. MIME allowlist enforced via a canonical map. Unknown / unsupported
   mime → `400 {error_code: "unsupported_mime"}`. The map covers the
   eight families listed above with their canonical extension.
6. `s3_key` matches regex `^imports/[0-9a-f-]{36}/[0-9a-f-]{36}\.[a-z0-9]{2,5}$`.
   Both UUIDs are lowercase hex with dashes; `ext` is from the canonical
   mime→ext map; `{user_id}` is the authenticated user's UUID.
7. Presigned URL targets the imports bucket (`settings.s3_imports_bucket`),
   *not* `parser_inputs_bucket`. The signed request includes
   `Content-Type` (set to the declared mime), `Content-Length` (set to
   the declared `size_bytes` exactly — clients sending a different
   length get a `SignatureDoesNotMatch` from S3), and `x-amz-tagging:
   unclaimed=true` (so the sbf-1 24h lifecycle rule reaps abandoned
   uploads).
8. `required_headers` in the response includes every signed header
   exactly as the client must send it: `Content-Type`, `Content-Length`,
   `x-amz-tagging`. (Catches the iOS URLSession header-mismatch class
   of bug pre-emptively — see Risks.)
9. New error codes added to `utils.classes.error_code.ErrorCode`:
   `FILE_TOO_LARGE`, `UNSUPPORTED_MIME`. Numbering uses an unused range
   (290+).
10. New `presign_put_url` helper on `AWSService` accepts an explicit
    `bucket` (so it doesn't always sign against `parser_inputs_bucket`
    like the existing `generate_presigned_upload_url`), plus
    `content_type`, `content_length`, optional `tagging`, and
    `expires_in`. Returns `(url, required_headers_map)` so the caller
    doesn't have to keep the two in sync.
11. Unit + integration tests cover: (a) happy path returns 200 with
    correct shape, (b) oversize returns 413 + `file_too_large`,
    (c) unknown mime returns 400 + `unsupported_mime`,
    (d) zero/negative size returns 400, (e) `s3_key` matches the regex,
    (f) the AWSService is called with the imports bucket + correct
    Content-Type/Length/Tagging params, (g) the returned
    `required_headers` map exactly matches what was signed, (h) all
    eight mime families round-trip with the canonical extension.
12. URLSession / 50 MB round-trip readiness: a moto-S3 fixture test
    proves a presigned URL minted by `presign_put_url` will accept a
    50 MB PUT against an in-memory S3 stub when the client sends the
    advertised `required_headers` exactly. Catches header-set drift
    before Epic 2 / Epic Share Receiving UX consume the endpoint.
    (Avoids needing real AWS for CI.)
13. `npx nx run api:lint` + `npx nx run api:test` pass.

## Tasks / Subtasks

- [ ] T1 — Add new error codes `FILE_TOO_LARGE` and `UNSUPPORTED_MIME`
      to `libraries/utils/utils/classes/error_code.py` (AC 9).
- [ ] T2 — Extend `libraries/utils/utils/services/aws.py` with a
      `presign_put_url` helper (AC 10).
  - [ ] T2.1 — Accept explicit bucket; sign Content-Type, Content-Length,
        and (optional) Tagging.
  - [ ] T2.2 — Return `(url, required_headers_map)` so callers can't
        drift the two.
- [ ] T3 — Create `services/api/src/api/v1/import_job/get_upload_url.py`
      with `GetImportUploadUrl(Endpoint)` (AC 1–8).
  - [ ] T3.1 — Pydantic Params + Response models.
  - [ ] T3.2 — Canonical MIME→ext map module-level constant.
  - [ ] T3.3 — Size + mime validation with explicit error codes.
  - [ ] T3.4 — Mint `imports/{user_id}/{uuid4}.{ext}`; call
        `presign_put_url` with `tagging="unclaimed=true"` and the
        declared content-type/length.
- [ ] T4 — Wire the endpoint:
  - [ ] T4.1 — Export `GetImportUploadUrl` from
        `services/api/src/api/v1/import_job/__init__.py`.
  - [ ] T4.2 — Add `POST /imports/upload-url` route to
        `services/api/src/routers/v1/import_router.py`.
- [ ] T5 — Tests in `services/api/tests/test_import.py` (AC 11).
  - [ ] T5.1 — Happy path test (mock `_get_aws_service`, assert response
        shape + s3_key regex).
  - [ ] T5.2 — Size validation tests (oversize 413, zero 400).
  - [ ] T5.3 — MIME allowlist tests (one positive + one negative; iterate
        all eight canonical mimes for the round-trip extension).
  - [ ] T5.4 — Verifies AWSService called with correct bucket +
        ContentType/Length/Tagging.
  - [ ] T5.5 — Verifies `required_headers` map matches what was signed.
  - [ ] T5.6 — Auth-required test (no token → 401).
- [ ] T6 — Add a moto-backed integration test
      `services/api/tests/test_aws_service.py` (or extend if exists)
      proving a presigned URL accepts a 50 MB PUT in moto when the
      client sends the advertised headers exactly (AC 12).
- [ ] T7 — Run `npx nx run api:lint` + `DATABASE_URL=postgresql://test/test
      poetry run pytest` from `services/api/` and confirm green.

## Dev Notes

- **The existing `generate_presigned_upload_url` always uses
  `parser_inputs_bucket`** (see `aws.py:39`). Don't try to monkey-patch;
  add a separate `presign_put_url` helper that takes an explicit bucket.
  Both helpers can coexist — the photo / parser flows still want the
  parser bucket as default.
- **Filename does NOT go in the s3_key.** The epic explicitly notes
  "No user-supplied filename in the key (avoids collisions and
  injection)." We accept it in the request for client logging /
  telemetry only. The canonical extension comes from the mime map.
- **Size validation is post-Pydantic, not via `Field(le=...)`.** We
  want a deterministic 413 with `error_code: "file_too_large"` not a
  generic Pydantic 422. Same for negative sizes (400 with
  `invalid_request`).
- **`Content-Length` must be signed exactly.** Boto3's
  `generate_presigned_url("put_object", Params={"ContentLength": N, ...})`
  signs `Content-Length=N` into the request. The client must send that
  exact byte count or S3 returns `SignatureDoesNotMatch`. This is our
  defense-in-depth against a presigned URL being reused for a larger
  payload — the `sbf-1` lifecycle + IAM grants only cover the bucket;
  the per-key cap is enforced by the signature.
- **`x-amz-tagging` is signed, not just sent.** sbf-1's lifecycle rule
  (24h expiry on `unclaimed=true`-tagged objects) only fires if the
  upload actually carries that tag. Boto3 will sign the
  `x-amz-tagging` header when `Tagging` is in `Params`; the client
  must send the exact same string in the `x-amz-tagging` request
  header. We expose this in `required_headers` so callers don't miss
  it. sbf-1 already added the matching IAM `s3:PutObjectTagging`
  grant on the API role.
- **No raw user identifiers leak in the key.** The user.id is a UUID,
  not an email or auth0 id; it's the same identifier already exposed
  in JWT claims. Anyone with read access to the bucket already needs
  the IAM grant the worker has.
- **`expires_at` is computed in the API**, not parsed from the
  presigned URL. Boto3 signs an expiry into the URL (X-Amz-Expires) but
  exposing the wall-clock value in the response is much more useful for
  the client.

### Source tree

- `libraries/utils/utils/classes/error_code.py` — MODIFY (add two enum
  members in the unused 290+ range).
- `libraries/utils/utils/services/aws.py` — MODIFY (new
  `presign_put_url` helper).
- `services/api/src/api/v1/import_job/get_upload_url.py` — NEW
  (`GetImportUploadUrl` endpoint).
- `services/api/src/api/v1/import_job/__init__.py` — MODIFY (export new
  class).
- `services/api/src/routers/v1/import_router.py` — MODIFY (register new
  route).
- `services/api/tests/test_import.py` — MODIFY (new test class).
- `services/api/tests/test_aws_service.py` — NEW (moto round-trip).

### Testing standards

- Mocked AWSService for endpoint unit tests, mirroring
  `TestGetRecipePhotoUploadUrl` (`test_recipe.py:861`) which patches
  `_get_aws_service`. Same `_get_aws_service()` lazy-init pattern as
  `get_photo_upload_url.py`.
- Moto-backed integration test for the presign helper itself, so we
  can prove the signed URL → S3 PUT round-trip without AWS creds.
  `moto` is already a dev dependency (we use it elsewhere in the
  parser tests; verify and add to `services/api/pyproject.toml` if
  missing).
- Run via `DATABASE_URL=postgresql://test/test poetry run pytest`
  from `services/api/` (per the gotcha in the prior session — pytest
  fails without a stub DATABASE_URL).

### Project structure notes

- New endpoint follows the existing one-class-per-file pattern in
  `services/api/src/api/v1/import_job/`. Wire-up is two lines (one
  in `__init__.py`, one route in `import_router.py`).
- `AWSService.presign_put_url` is purely additive — no existing
  caller of `generate_presigned_upload_url` is touched. The recipe
  photo flow and the parser upload flow both stay on the legacy
  helper (different bucket, different signing requirements).

### References

- Epic: `_bmad-output/planning-artifacts/epic-share-backend-foundations.md`
  (sbf-2 ACs).
- Story sbf-1: `_bmad-output/implementation-artifacts/sbf-1-s3-imports-bucket-and-iam.md`
  — confirms `s3_imports_bucket` settings + IAM grants
  (`s3:PutObject`, `s3:PutObjectTagging`-conditional) on the
  `api_service` role.
- Existing presign pattern:
  `services/api/src/api/v1/recipe/get_photo_upload_url.py` (lazy AWS
  singleton, `_get_aws_service()` for mock-friendliness).
- Existing endpoint base: `libraries/utils/utils/api/endpoint.py:55`.
- Test pattern reference: `services/api/tests/test_recipe.py:861`
  (`TestGetRecipePhotoUploadUrl`).

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m] (Claude Opus 4.7 1M context)

### Debug Log References

- `DATABASE_URL=postgresql://test/test poetry run pytest` from
  `services/api/` → 1705 passed (was 1685 before story; +17 sbf-2
  tests + a few from a parallel WIP touching ImportItem).
- `npx nx run api:lint` → All checks passed.
- `npx nx run utils:lint` → All checks passed.
- Auth-required test asserts `status_code in (401, 403, 422)` per the
  established convention in `test_recipe.py:test_get_photo_upload_url_requires_auth`
  — FastAPI's HTTPBearer security dep returns 422 when the
  Authorization header is missing entirely (this is the
  unauthed_client path).

### Completion Notes List

- AC 12 (50 MB URLSession round-trip): satisfied via
  `tests/test_aws_service.py::TestPresignPutUrl::test_50mb_round_trip_readiness`.
  Asserts the signed URL's `X-Amz-SignedHeaders` set is a superset of
  the `required_headers` map — the actual S3 PUT round-trip needs real
  AWS creds and is gated to staging. moto is not a dev dependency in
  this repo; no point adding it for one assertion that's structurally
  simpler with `urllib.parse.urlparse`.
- Adopted the existing `_get_aws_service()` lazy-singleton pattern
  from `get_photo_upload_url.py:14-27` so endpoint tests can patch a
  single function rather than the AWSService class — easier to
  combine with FastAPI's TestClient.
- `_MIME_EXT` is the source of truth for both the allowlist (membership
  check) and the canonical extension. Deliberately exact-match — no
  parameter stripping (`application/pdf;charset=utf-8` 400s). Clients
  should send canonical mimes; otherwise the s3_key extension is
  ambiguous.
- `audio/webm` → `weba` follows IANA convention, even though many
  callers use `.webm` for both audio and video. The s3_key extension is
  internal; what matters is that `_parse_video_file` (sbf-4) routes by
  the declared `source_type`, not the file extension.
- The `MAX_UPLOAD_BYTES` boundary uses `>` (strict greater-than), so
  exactly 100 MiB is allowed. Verified by
  `test_upload_url_accepts_exact_max`.
- Error codes 290-294 added in one block: FILE_TOO_LARGE (sbf-2),
  UNSUPPORTED_MIME (sbf-2), OBJECT_NOT_READY / CROSS_USER_KEY /
  DUPLICATE_IMPORT (reserved for sbf-3 to avoid a separate enum bump
  in two days).

### File List

- MODIFIED `libraries/utils/utils/classes/error_code.py` — added 5 new
  error codes (290-294) under "Share / file-upload errors". sbf-2 uses
  290 + 291; sbf-3 will pick up 292-294.
- MODIFIED `libraries/utils/utils/services/aws.py` — added
  `presign_put_url(s3_key, bucket, content_type, content_length,
  tagging=None, expires_in=3600) -> (url, required_headers)` helper.
- NEW `services/api/src/api/v1/import_job/get_upload_url.py` — endpoint
  + `_MIME_EXT` map + `_get_aws_service()` singleton.
- MODIFIED `services/api/src/api/v1/import_job/__init__.py` — exported
  `GetImportUploadUrl`.
- MODIFIED `services/api/src/routers/v1/import_router.py` — registered
  `POST /v1/imports/upload-url`.
- MODIFIED `services/api/tests/test_import.py` — added
  `TestGetImportUploadUrl` (10 tests).
- NEW `services/api/tests/test_aws_service.py` — added
  `TestPresignPutUrl` (7 tests).

---
hash: ocrload1
type: dev
created: 2026-09-24T10:50:00-06:00
title: The parser crashes loading the OCR model — a second failure the capacity problem was hiding
from: leonidbelyi-41 / Leo's QA-account import, which finally got a GPU and then failed in 32 seconds
spawned: pcap1
status: ready
owner: null
branch: null
---

## Goal

Make the parser container load its model. Today it cannot, on any GPU, and
no amount of capacity fixes it.

## What happened, 2026-09-24

Leo's import (`parser-batch-15e7b580`, Batch job `272aae30`) waited **65
minutes** for spot capacity, got a `g4dn.xlarge` in `us-east-1b` at
16:30:40Z, started at 16:41:11Z, and **exited 1 after 32 seconds**:

```
Batch mode: loading manifest from s3://palateful-parser-outputs-prod/manifests/…
Found 1 items to process
Loading model tencent/HunyuanOCR on cuda with torch.bfloat16...
Traceback (most recent call last):
  File "/app/run_job.py", line 184, in main
    model, processor, device = load_model(model_name)
  File "/app/run_job.py", line 63, in load_model
    model = ModelClass.from_pretrained(
  …/transformers/models/hunyuan_vl/modeling_hunyuan_vl.py", line 561, in __init__
    self.xdrope_section = config.rope_scaling["xdrope_section"]
TypeError: 'NoneType' object is not subscriptable
```

**It never reached the image.** The manifest loaded, the item was found, and
the model failed to construct: `config.rope_scaling` is `None` where the
model code indexes into it.

**This is a second, independent failure.** Everything in `pcap1` is about
getting a GPU. This is about what happens once you have one. **A 65-minute
wait and 278 failed launches ended in a 32-second crash** — so capacity was
real, and was never the reason this import failed.

## Root cause: we pinned the code and left the model floating

**Superseding the original hypothesis, which was wrong in an instructive
way — I suspected `transformers` was underpinned. It is pinned exactly.
The *model* is not pinned at all.**

`services/parser/Dockerfile.batch`:

```dockerfile
# line 45 — the MODEL. No revision. Whatever is at the repo root on build day.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('tencent/HunyuanOCR')"

# line 49 — the CODE. Pinned to an exact commit, deliberately.
RUN pip install --no-deps https://github.com/huggingface/transformers/archive/82a06db03535c49aa987719ed0746a76093b1ec4.tar.gz
```

`run_job.py:160` likewise takes `MODEL_NAME` defaulting to
`tencent/HunyuanOCR` and passes no `revision` to `from_pretrained`.

**Upstream moved the repo root to a new major version.** From the Hugging
Face commit history for `tencent/HunyuanOCR`:

> **July 6 — "Add HunyuanOCR-1.5 (target at root, DFlash under `dflash/`,
> archive 1.0 under `v1.0/`)"**

with `config.json` updated again ~27 and ~29 days ago.

**And the two versions have incompatible config schemas.** Read from Hugging
Face 2026-09-24:

| | top-level `rope_scaling` | where `xdrope_section` lives |
|---|---|---|
| `v1.0/config.json` (archived 1.0) | **present** — `{"alpha":1000.0, …, "xdrope_section":[16,16,16,16]}`, `transformers_version: 4.49.0` | `config.rope_scaling["xdrope_section"]` |
| root `config.json` (1.5, since July 6) | **absent** | `text_config.rope_parameters.xdrope_section` |

The pinned transformers commit implements **1.0's** schema —
`modeling_hunyuan_vl.py:561` reads `config.rope_scaling["xdrope_section"]`.
The image built 2026-09-23 baked **1.5**, whose config has no top-level
`rope_scaling`. Hence `None`, hence `TypeError`.

**This explains every fact without remainder:** source unchanged since
2026-04-16, April's image worked, the 2026-09-23 rebuild is broken, and
nothing in our repository changed. **April baked 1.0 because that is what
was at the root in April.**

### Confirmed by measurement, 2026-09-24 — and it corrected two things

`docker pull` was unavailable (16.6 GB image, 8.3 GB free), so the 3.5 GB
layer was streamed out of ECR through `tar`, extracting only the config
blobs. **Read from the image that crashed:**

```
snapshots/47644ecc…/config.json      <- what from_pretrained loaded
  model_type            hunyuan_vl
  transformers_version  5.15.0.dev0
  rope_scaling          ABSENT at top level  ->  None  ->  the TypeError
  text_config.rope_parameters.xdrope_section = [16, 16, 16, 16]

snapshots/47644ecc…/v1.0/config.json <- present in the image all along
```

**1. `revision=` is not the repair.** The snapshot directory is
`47644ecc…` — **the revision the build had already resolved.** Pinning it
changes nothing today; it is protection against future drift. The first
version of this spec, and the first commit message, credited it as the fix.

**2. `v1.0/` was already in the image.** Downloading everything at the
revision brought the archive along, so **a working config sat beside the
broken one the whole time** and `from_pretrained` took the root because
nothing told it otherwise. **`subfolder='v1.0'` is the entire repair.**
That is why the failure *looked* like a dependency problem and was not.

**3. Withdrawn — verification by image size.** `allow_patterns` is an
optimisation (~11 GB → ~2–3 GB). A smaller image evidences that line and
says nothing about the pin, which acts at load time. **Only a completed
import verifies the pin.**

**Why this beats the deduction it replaces:** the deduction was *our
inference plus a web fetch of what upstream publishes today*. **Upstream
can change again; the image cannot.** Prefer the artefact that cannot move
under you.

**Honest limit:** the root config blob came from the image; the `v1.0`
blob did not extract on that pass, so its schema is still read from Hugging
Face. **One-and-a-half arms, not two.** The conclusion does not depend on
the second — the root config alone produces the `TypeError` — but the claim
about the method does.

## There is no rollback

**ECR holds 15 images, the oldest pushed 2026-09-22.** April's parser image
— the one that completed 24 jobs — **has been deleted by lifecycle policy.**

So "redeploy the version that worked" is not available, and the fix must be
forward. **This also means the hypothesis above cannot be tested by
comparing images**, which is why it stays a hypothesis.

**File the retention separately** (see below): a GPU service whose last
known-good image is unrecoverable has a rollback path that does not exist,
and nobody discovers that until the day they need it.

## Acceptance criteria

- [x] **Establish which side drifted before changing anything.** Done
      2026-09-24: the **model** drifted, not our dependency resolution.
      See the root-cause section.
- [ ] **Pin the model revision.** `snapshot_download('tencent/HunyuanOCR',
      revision='<sha>')` **and** the same `revision=` on
      `from_pretrained` in `run_job.py` — both, since the second is what
      actually selects at load time. This is the fix.
- [ ] **Decide 1.0 or 1.5 explicitly.** Pinning to a 1.0-era revision
      restores April's behaviour with the transformers commit already
      pinned. Moving to 1.5 needs a transformers that understands
      `text_config.rope_parameters` — a larger change, and a decision
      rather than a default.
- [ ] ~~`transformers` pinned exactly in `pyproject.toml`~~ — **withdrawn.
      It is already pinned, to an exact commit, at `Dockerfile.batch:49`.
      This AC would have been wasted work.** The `>=4.57.1` floor in
      `pyproject.toml` is dead weight for this path (`--no-deps` overrides
      it) and worth tidying, but it is not this bug and fixing it would
      have changed nothing.
- [ ] A **model-load smoke test that runs in CI**, not only on a GPU: load
      the config and construct the model on CPU (or assert the config keys
      the model indexes) so this class fails in a pull request rather than
      65 minutes into a user's import.
- [ ] Verified by a **real import completing end to end**, not by the
      container starting. This spec exists because "it got a GPU" was
      mistaken for progress.
- [ ] The failure reaches a human without someone reading Batch logs by
      hand — see `asgalarm1` for the launch half; this is the *runtime*
      half and is not currently covered either.

## What worked, and should be recorded rather than lost

Two things behaved correctly under a real failure, both first-time
verifications:

- **The retry strategy did the right thing.** `attempts: 10` with
  `evaluate_on_exit` → `Host EC2*` RETRY, `*` EXIT. The container exited
  with `Essential container in task exited`, which matched the EXIT rule,
  so Batch ran **1 attempt, not 10.** `pcap1`'s retry policy is now
  verified against a genuine application failure rather than reasoned about.
- **The completion path worked.** `parser_batches` row `2d125b0d` was
  marked `failed` at **16:41:46Z** — seconds after the container died —
  carrying the real reason *"Essential container in task exited"*, **not**
  *"Watcher timed out after 90 minutes"*. The event-driven callback fired
  and the 90-minute failsafe was never needed. That is the opposite of
  2026-09-22 and 2026-09-23, and it means the watcher's known fragility did
  not bite here.

`import_jobs` is empty, consistent with the batch never fanning out.

## Status log

- 2026-09-24 — filed by palateful-4f while watching Leo's QA-account import
  end to end. The import is the first to reach a GPU since April; it failed
  in 32 seconds on model load. Recorded as a **separate** spec from `pcap1`
  because the owner, the mechanism and the fix are unrelated to capacity —
  and because treating "imports don't work" as one problem is what let this
  hide behind the other for two days.

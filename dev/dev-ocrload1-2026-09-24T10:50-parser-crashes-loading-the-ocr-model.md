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

## Hypothesis: an unpinned dependency, resolved differently on rebuild

**Marked as a hypothesis, not a finding.** The traceback is fact; the cause
below is inference and the one experiment that would settle it is no longer
available.

- `services/parser/` has not changed since **2026-04-16**.
- The running image is `palateful-parser:72289714…`, **built 2026-09-23** —
  same source, eleven days ago, against different upstream state.
- `services/parser/pyproject.toml:13` declares `transformers = ">=4.57.1"`
  — a **floor, not a pin**.
- `services/parser/Dockerfile.batch:49` then force-installs a **specific
  transformers commit** for `hunyuan_vl` support:
  `pip install --no-deps https://github.com/huggingface/transformers/archive/82a06db0….tar.gz`,
  after pre-downloading weights, with a comment that the ordering matters
  (`# Pre-download model weights BEFORE overriding transformers`).

So two mechanisms decide which `transformers` is present, one of them
unpinned, and `--no-deps` means the override cannot correct the
dependencies around it. A rebuild resolving the floor differently is
sufficient to produce a model implementation and a config that disagree
about `rope_scaling`.

**Also possible and not excluded:** the pinned commit's `hunyuan_vl` now
expects a `rope_scaling` the **published model config** no longer provides
— i.e. the drift is on the Hugging Face side, not ours. Distinguishing
these is the first task, not an afterthought; they have different fixes.

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

- [ ] **Establish which side drifted** before changing anything: our
      resolved `transformers` version, or the published `HunyuanOCR`
      config. `docker run` the current image and print both
      `transformers.__version__` and the loaded `config.rope_scaling`.
- [ ] `transformers` is **pinned exactly**, not floored, in
      `pyproject.toml` — consistent with `Dockerfile.batch` already pinning
      a commit. Two mechanisms disagreeing is the defect whatever caused
      this instance.
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

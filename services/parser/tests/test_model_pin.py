"""ocrload1: the model pin must not drift between the Dockerfile and the code.

The 2026-09-24 outage was caused by the *model* being unpinned while
transformers was pinned to an exact commit: upstream re-pointed the repo
root to HunyuanOCR-1.5 and the rebuilt image crashed on a config schema
the pinned transformers does not understand.

At runtime the Dockerfile's ENV wins over `run_job.py`'s literal default,
so the two cannot disagree *inside a built image*. They can drift in the
source, and then a local run, a CI run, or any invocation that does not go
through the image silently uses a different model than production. These
tests pin the pin.
"""

import re
from pathlib import Path

PARSER = Path(__file__).resolve().parent.parent
DOCKERFILE = PARSER / "Dockerfile.batch"
RUN_JOB = PARSER / "run_job.py"


def _dockerfile_arg(name: str) -> str:
    m = re.search(rf"^ARG {name}=(\S+)$", DOCKERFILE.read_text(), re.M)
    assert m, f"{name} ARG missing from Dockerfile.batch — the model is unpinned"
    return m.group(1)


def _run_job_default(name: str) -> str:
    src = RUN_JOB.read_text()
    m = re.search(rf'{name} = os\.environ\.get\(\s*"{name}",\s*"([^"]+)"', src, re.S)
    assert m, f"{name} default missing from run_job.py — the model is unpinned"
    return m.group(1)


def test_model_revision_matches_between_dockerfile_and_code():
    assert _dockerfile_arg("MODEL_REVISION") == _run_job_default("MODEL_REVISION")


def test_model_subfolder_matches_between_dockerfile_and_code():
    assert _dockerfile_arg("MODEL_SUBFOLDER") == _run_job_default("MODEL_SUBFOLDER")


def test_snapshot_download_passes_a_revision():
    """The original defect: snapshot_download('tencent/HunyuanOCR') with no revision."""
    body = DOCKERFILE.read_text()
    assert "snapshot_download" in body, "pre-bake step disappeared"
    call = body[body.index("snapshot_download") :]
    call = call[: call.index(")") + 1]
    assert "revision=" in call, (
        "snapshot_download has no revision= — this is exactly the ocrload1 defect, "
        "which bakes whatever is at the repo root on build day"
    )


def test_from_pretrained_calls_pass_a_revision():
    """Pinning only the download looks correct and fixes nothing."""
    src = RUN_JOB.read_text()
    calls = [m.start() for m in re.finditer(r"\.from_pretrained\(", src)]
    assert calls, "no from_pretrained calls found — test is pointed at the wrong file"
    for start in calls:
        call = src[start : src.index(")", start)]
        assert "revision=MODEL_REVISION" in call, (
            "a from_pretrained call has no revision= — from_pretrained is what "
            "selects the model at load time, so this one is unpinned"
        )

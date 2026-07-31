#!/usr/bin/env python3
"""Judge a repo's observed GitHub Actions schedule cadence against E-7's threshold.

E-7 asks for the deploy gap to be surfaced "within 24h of crossing 7 days". The
usual way to argue that is to point at the cron (`0 15 * * *`, therefore daily,
therefore within 24h) — but a cron expression is a *request*. What actually
matters is how far apart the scheduler really fires, so this reads that off the
repo's own `event: schedule` run history instead.

It also predicts, from the declared cron, how many firings the observed window
should have contained, and reports the disagreement. That fidelity check is
informational on purpose: firing *more* often than declared still satisfies a
"within 24h" threshold, so it must not fail the run — but it does mean the
nominal time of any single run cannot be inferred from the cron, which is
exactly what a next-morning observer would otherwise assume.

Usage: deploy-freshness-cadence.py RUNS_TSV THRESHOLD_HOURS WITNESS_PATH [CRON]
  RUNS_TSV: created_at<TAB>path<TAB>status<TAB>conclusion, any order.
Exit: 0 within threshold, 1 a silence longer than the threshold, 2 unusable input.
"""

import datetime
import sys


def parse_field(spec: str, lo: int, hi: int) -> set[int]:
    """Expand one cron field into the set of values it matches."""
    values: set[int] = set()
    for part in spec.split(","):
        step = 1
        if "/" in part:
            part, raw_step = part.split("/", 1)
            step = int(raw_step)
        if part in ("*", ""):
            start, end = lo, hi
        elif "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
        else:
            start = int(part)
            # `5/10` means "from 5, every 10" — a bare `5` is just itself.
            end = hi if step != 1 else start
        values.update(range(start, end + 1, step))
    return values


def cron_firings(expr: str, start: datetime.datetime, end: datetime.datetime) -> int | None:
    """Count minutes in [start, end] that the 5-field cron `expr` matches."""
    fields = expr.split()
    if len(fields) != 5:
        return None
    try:
        minutes = parse_field(fields[0], 0, 59)
        hours = parse_field(fields[1], 0, 23)
        doms = parse_field(fields[2], 1, 31)
        months = parse_field(fields[3], 1, 12)
        dows = {d % 7 for d in parse_field(fields[4], 0, 7)}
    except ValueError:
        return None
    # Standard cron: when both day-of-month and day-of-week are restricted the
    # two are OR'd; otherwise they are AND'd with the rest.
    dom_restricted = fields[2] != "*"
    dow_restricted = fields[4] != "*"

    count = 0
    cursor = start.replace(second=0, microsecond=0)
    while cursor <= end:
        if cursor.minute in minutes and cursor.hour in hours and cursor.month in months:
            # cron weekdays are 0=Sunday; Python's weekday() is 0=Monday.
            dow = (cursor.weekday() + 1) % 7
            if dom_restricted and dow_restricted:
                day_ok = cursor.day in doms or dow in dows
            else:
                day_ok = (not dom_restricted or cursor.day in doms) and (
                    not dow_restricted or dow in dows
                )
            if day_ok:
                count += 1
        cursor += datetime.timedelta(minutes=1)
    return count


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    runs_path, threshold_hours, witness_path = argv[1], float(argv[2]), argv[3]
    cron = argv[4] if len(argv) > 4 else ""

    with open(runs_path) as handle:
        rows = [line.split("\t") for line in handle.read().splitlines() if line.strip()]
    times = sorted(
        datetime.datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%SZ") for row in rows if row[0]
    )
    if len(times) < 2:
        print(
            "  NOT OBSERVABLE: fewer than two schedule runs, so there is no interval to measure.",
            file=sys.stderr,
        )
        return 2

    span_h = (times[-1] - times[0]).total_seconds() / 3600
    gaps = [((b - a).total_seconds() / 3600, a, b) for a, b in zip(times, times[1:], strict=False)]
    worst_h, worst_from, worst_to = max(gaps)
    print(
        f"  window: {times[0]:%Y-%m-%dT%H:%MZ} .. {times[-1]:%Y-%m-%dT%H:%MZ}"
        f" ({span_h:.1f}h, {len(times)} runs)"
    )
    print(
        f"  longest silence: {worst_h:.1f}h ({worst_from:%m-%dT%H:%MZ} -> {worst_to:%m-%dT%H:%MZ})"
    )

    # Fidelity: does the observed cadence track the cron that asked for it?
    # Informational — over-firing still satisfies a "within Nh" threshold.
    if cron:
        predicted = cron_firings(cron, times[0], times[-1])
        if predicted is None:
            print(f"  NOTE: could not parse the witness cron '{cron}' — no fidelity check.")
        elif predicted == len(times):
            print(
                f"  fidelity: '{cron}' in {witness_path} predicts {predicted} firing(s) — matches."
            )
        else:
            print(
                f"  ⚠ FIDELITY: {witness_path} declares '{cron}', which predicts"
                f" {predicted} firing(s) over this window. {len(times)} were observed."
            )
            print(
                "    The scheduler in this repo does NOT fire on the cadence its cron asks for, so"
            )
            print(
                "    the nominal time of any single run cannot be inferred from the cron. A next-"
            )
            print("    morning observer must record the actual UTC time a run lands rather than")
            print("    confirming it 'ran at 09:00'. Frequency, not punctuality, is what")
            print("    the threshold below is judged on.")

    if worst_h <= threshold_hours:
        print(
            f"  OK: no silence longer than {threshold_hours:.0f}h, so a gap crossing the"
            f" 7-day line is surfaced within the threshold"
        )
        return 0
    print(
        f"  FAIL: the scheduler went quiet for {worst_h:.1f}h, longer than E-7's"
        f" {threshold_hours:.0f}h threshold — a freeze could cross 7 days and stay unreported"
        f" past it",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

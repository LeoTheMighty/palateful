/// The ImportJob status vocabulary, in ONE place.
///
/// Mirrors the server's list at `libraries/utils/utils/models/import_job.py`
/// (a `String(20)` column with the legal values in a comment — there is no
/// enum and no CHECK constraint, so this is a mirror, not a guarantee).
///
/// Why one file: the Imports tab and the parser-batch model each used to
/// keep their own closed set, in different files, and the two only happened
/// to partition the vocabulary. Adding one server status — `queued`, say —
/// would have made a job count as in-flight for the Add Recipe strip while
/// rendering nowhere in the Imports tab: the exact "badge says 1, tab is
/// empty" bug this work exists to fix, back in a new shape.
///
/// [isUnknownJobStatus] is the safety valve. An unrecognised status is
/// treated as in-progress everywhere, so a new server status shows up as a
/// visible row rather than as a silent absence.
library;

/// Statuses where the job is still moving and the user is waiting.
const kInProgressJobStatuses = {
  'pending',
  'processing',
  'extracting',
  'matching',
  'awaiting_parser',
};

/// Statuses where the job has stopped moving.
///
/// `awaiting_review` counts as stopped: the import is done and the ball is
/// in the user's court, and its items already surface in Needs Review.
const kTerminalJobStatuses = {
  'completed',
  'failed',
  'cancelled',
  'awaiting_review',
};

/// Statuses where the user deliberately ended the import. Their leftover
/// items are abandoned, not in flight, and must not be rendered as work in
/// progress.
const kAbandonedJobStatuses = {'cancelled'};

/// Everything this client knows about.
const kKnownJobStatuses = {
  ...kInProgressJobStatuses,
  ...kTerminalJobStatuses,
};

/// True for a status the server has that this build does not.
bool isUnknownJobStatus(String? status) =>
    status != null && !kKnownJobStatuses.contains(status);

/// True when the job is still working — including any status this build
/// doesn't recognise, so a new server status errs toward being visible.
bool isJobInProgress(String? status) =>
    kInProgressJobStatuses.contains(status) || isUnknownJobStatus(status);

/// True when the job has stopped, for the purpose of deciding whether a
/// parser batch still has anything to report. Unknown statuses are NOT
/// terminal, for the same reason.
bool isJobTerminal(String? status) =>
    kTerminalJobStatuses.contains(status) && !isUnknownJobStatus(status);

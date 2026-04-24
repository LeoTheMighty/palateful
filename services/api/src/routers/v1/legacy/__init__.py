"""Legacy sync routers kept in-tree during the aam-* dual-dispatch window.

Each per-domain story (`aam-10` onward) lands its async handler at the
canonical `/v1/<domain>` prefix while leaving the pre-conversion sync
handler mounted under `/_legacy_v1/<domain>`. Client traffic only ever
hits the async mount; the legacy mount is the fast-revert path per
`docs/async-migration-runbook.md#dual-register--observation-window-procedure`.

`aam-24` deletes this package after every domain's observation window
closes green.
"""

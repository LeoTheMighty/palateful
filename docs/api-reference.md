# API reference notes

Lightweight reference doc for non-obvious response-shape contracts.
Source of truth for the full API is the code in
`services/api/src/api/v1/` — this file holds the idioms that would
otherwise be easy to miss in a consumer integration.

## `/v1/activities`

- **`total` is `0`** on every response (cursor-paginated and
  cursor-less alike). The original heavy `COUNT(*)` was removed in
  `pbq-5` after a pre-merge grep confirmed no Flutter consumer reads
  the field. Clients that need a count should call
  `/v1/activities/see-all-count`; clients that page should use
  `items.length` and `next_cursor`.

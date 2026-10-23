# Changelog

All notable changes to this library are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-10-23

### Removed

- `documents.create()` — the API no longer accepts PDF uploads; write contracts as text in templates or the request.

## [1.0.0] - 2026-10-14

First stable release, targeting API version `2026-07-01`.

### Added

- `wthaiq.Client` (synchronous) and `wthaiq.AsyncClient` (asynchronous) with the same resources:
  `account`, `usage`, `balance`, `templates`, `signature_requests`, `sessions`, `signers`, `documents`,
  `identity_verifications`, `verifications`, `webhook_endpoints`, `events` and `flows`.
- Typed parameters (`TypedDict`) for every method and typed, immutable response objects with attribute access,
  item access, `to_dict()` / `to_json()` and the HTTP details of each call (`last_response`).
- Exception hierarchy mapped by HTTP status (`ValidationError`, `AuthenticationError`, `PaymentRequiredError`,
  `PermissionDeniedError`, `NotFoundError`, `ConflictError`, `RateLimitError`, `ServerError`, ...).
- Automatic retries with exponential backoff and jitter that honour `Retry-After` and never retry quota-style
  `429` responses; automatic idempotency keys on every `POST`, reused across retries; timeouts.
- Cursor pagination: `list()` pages, `auto_paging_iter()` and lazy `all()` iterators (`async for` on the async
  client), protected against repeated cursors.
- PDF download as bytes (checked against `X-File-Sha256`) or to a file (written atomically); multipart PDF upload.
- `wthaiq.Webhook.construct_event()` with constant-time HMAC-SHA256 verification and timestamp tolerance,
  verified against a delivery signed by the platform's own webhook code.
- Pluggable transports: standard library by default (no dependencies), `httpx` adapters (extra `wthaiq[httpx]`),
  or any callable.
- Event types `signer.identity_match_hold` and `signer.identity_match_decided` in `EventType` and `EVENT_TYPES`:
  the name on the signer's identity document differs from the name in the request, and the decision on that
  difference. `EVENT_TYPES` now lists 21 types.
- `signers.decide_identity_match(id, decision="approve" | "reject", note=...)` (sync and async) for
  `POST /signers/{id}/identity_match`: decides a name difference held for review and returns the signer.
- `wthaiq.NameMatch` (with `is_awaiting_decision`): `identity.name_match` on signers, `name_match` on identity
  verifications, and `identity_match` on the signer inside the two name-match events.
- `TooManySignersError` (a `ValidationError`) for `400 too_many_signers`, with `max_signers` read from the
  error's `max_signers` (falls back to the new `wthaiq.MAX_SIGNERS` constant, 5).
- `PermissionError.verify_url` reads `verify_url` from `kyb_required` errors (falls back to `VERIFY_URL`).
  `upgrade_url` reads the `upgrade_url` the API now sends on `plan_required`, `plan_expired` and
  `plan_feature_unavailable`.
- Client option `language` (`"en"` or `"ar"`), sent as `Accept-Language`, for English error messages. The
  default is unchanged: no header, Arabic messages. Error codes do not change with the language.
- `webhook_endpoints.list()` and `all()` accept `starting_after` and follow `next_cursor` across pages, now that
  the API paginates webhook endpoints like other lists.
- `verifications.retrieve()` also returns `found=False` when the API answers an unknown reference with a `404`
  error whose code is `not_found`, so its result does not depend on the server version.

[1.1.0]: https://github.com/wthaiq/wthaiq-python/releases/tag/v1.1.0
[1.0.0]: https://github.com/wthaiq/wthaiq-python/releases/tag/v1.0.0

# Changelog

All notable changes to this library are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-10-07

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

[Unreleased]: https://github.com/wthaiq/wthaiq-python/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/wthaiq/wthaiq-python/releases/tag/v1.0.0

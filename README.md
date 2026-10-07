# Wthaiq Python Library

> مكتبة Python الرسمية لواجهة الربط البرمجية في منصة وثائق للتوقيع الإلكتروني. تتيح لتطبيقك إنشاء طلبات التوقيع
> وإرسالها ومتابعة حالتها، واستعمال القوالب ومسارات العمل، وتضمين التوقيع في موقعك، وتنزيل الوثيقة النهائية ومحضر
> الأدلّة، والتحقّق من توقيع إشعارات الأحداث (Webhooks). وتعمل المكتبة في وضع الاختبار مجانًا دون أن تُرسَل أيّ رسالة
> إلى طرف آخر، ثم تنتقل إلى الوضع الحيّ بتغيير المفتاح وحده.

The official Python library for the [Wthaiq](https://developers.wthaiq.com) e-signature API. Create and send
signature requests, use templates and workflows, embed signing in your site, download the signed PDF and the
sealed evidence record, and verify webhook signatures.

- Synchronous `Client` and asynchronous `AsyncClient` with the same methods.
- No required dependencies (standard library only); uses `httpx` for async I/O when it is installed.
- Fully typed (`py.typed`): typed parameters for every method and typed response objects.
- Typed exceptions, automatic retries with backoff, automatic idempotency keys and timeouts.
- Auto-pagination, verified PDF downloads, multipart uploads and constant-time webhook verification.

## Contents

- [Installation](#installation)
- [Quick start](#quick-start)
- [Authentication and modes](#authentication-and-modes)
- [Configuration](#configuration)
- [Resources](#resources)
- [Responses](#responses)
- [Pagination](#pagination)
- [Async usage](#async-usage)
- [Error handling](#error-handling)
- [Retries, idempotency and timeouts](#retries-idempotency-and-timeouts)
- [Webhooks](#webhooks)
- [Custom HTTP transport](#custom-http-transport)
- [Versioning](#versioning)
- [Support and security](#support-and-security)

## Installation

```bash
pip install wthaiq
```

For true asynchronous I/O with `AsyncClient`, install the optional `httpx` extra:

```bash
pip install "wthaiq[httpx]"
```

Requirements: Python 3.10 or later. The base package has no dependencies.

## Quick start

```python
import os
import wthaiq

wt = wthaiq.Client(os.environ["WTHAIQ_API_KEY"])  # sk_test_... while you build

sr = wt.signature_requests.create(
    title="عقد عمل — أحمد سامي",
    source={"type": "template", "template_id": "tpl_123"},
    legal_level="aes",
    signers=[
        {
            "name": "أحمد سامي",
            "email": "ahmed@example.com",
            "method": "draw",
            "require_identity": True,
            "fields": {"job_title": "محاسب", "salary": "25000"},
        }
    ],
    reminders={"enabled": True, "interval_hours": 48, "max": 3},
    metadata={"order_id": "A-1024"},
)

print(sr.id, sr.status)  # sr_3n8Kd2Qa1V... sent
print(sr.signers[0].signing_url)
```

## Authentication and modes

Every request is authenticated with your secret key (`Authorization: Bearer sk_...`). Create and rotate keys in
the developer portal at <https://developers.wthaiq.com>. If you do not pass a key, the client reads the
`WTHAIQ_API_KEY` environment variable.

| Key | Mode | Behaviour |
|---|---|---|
| `sk_test_...` | Test | Free. Nothing is charged and no message reaches anyone: emails go to your own address, WhatsApp is simulated. Signers must be the account owner or team members. Limits: 20 created requests per 24 hours, 5 signers per request. Documents carry a watermark and have no legal effect. |
| `sk_...` | Live | Real sends. Each sent request uses one send from your annual plan, then the wallet. Requires a paid plan and a verified company. |

```python
wt.is_test_mode()  # True for sk_test_ keys
```

This is a server-side library: keep secret keys on your server. Publishable keys (`pk_...`) are accepted but are
limited to a few routes and are meant for the embeddable console in the browser.

## Configuration

```python
wt = wthaiq.Client(
    "sk_test_...",
    base_url="https://wthaiq.com/api/v1",  # default
    timeout=60.0,  # seconds per attempt
    connect_timeout=10.0,  # seconds to connect (httpx transport)
    max_retries=2,  # automatic retries of transient failures
    app_info={"name": "AcmeHR", "version": "3.2.0", "url": "https://acme.example"},
)
```

| Option | Default | Notes |
|---|---|---|
| `api_key` | `WTHAIQ_API_KEY` | `sk_...`, `sk_test_...` (or `pk_...` for allowed routes). |
| `base_url` | `https://wthaiq.com/api/v1` | Must be `https://` (plain `http://` only for localhost). |
| `timeout` | `60.0` | Seconds allowed for each attempt. |
| `connect_timeout` | `10.0` | Seconds allowed to connect, where the transport supports it. |
| `max_retries` | `2` | Retries after the first attempt (`0` disables retries). |
| `api_version` | `2026-07-01` | Sent as the `Wthaiq-Version` header. |
| `app_info` | `None` | Appended to the `User-Agent` (`wthaiq-python/1.0.0 Python/3.12.4 AcmeHR/3.2.0`). |
| `http_client` | standard library | See [Custom HTTP transport](#custom-http-transport). |
| `retry_policy` | `RetryPolicy()` | Backoff settings. |

Use the client as a context manager (or call `close()`) to release connections:

```python
with wthaiq.Client() as wt:
    print(wt.account.retrieve().plan.id)
```

## Resources

Every method takes the API's parameters as keyword arguments, with the API's own names. You can also pass a
`dict` as the first positional argument (useful for parameters added to the API after this release). Request
options (`idempotency_key`, `timeout`, `max_retries`, `headers`, `api_key`) are keyword arguments of every method.

### Account, usage and balance

```python
root = wt.account.retrieve()  # GET /
print(root.account.name, root.plan.id, root.livemode)

usage = wt.usage.retrieve()  # GET /usage
print(usage.balance.amount, usage.balance.currency, usage.plan.sends_left)

balance = wt.balance.retrieve()  # GET /balance
```

### Templates

```python
template = wt.templates.create(
    name="Service agreement",
    content="<p>I, {{signer_name}}, accept the amount of {{amount}}.</p>",
    fields=[{"key": "amount", "label": "Amount", "type": "number", "required": True}],
)

template = wt.templates.retrieve("tpl_123", include="content")
page = wt.templates.list(scope="mine", search="agreement", limit=20)  # your own templates
for t in wt.templates.all():  # the public catalogue
    print(t.id, t.name)
```

### Signature requests

```python
# Create a draft, then send it later
draft = wt.signature_requests.create(
    source={"type": "template", "template_id": "tpl_123"},
    signers=[{"name": "Noha", "email": "noha@example.com"}],
    fields={"amount": "1500"},
    send=False,
)
wt.signature_requests.send(draft.id)

sr = wt.signature_requests.retrieve("sr_...")
wt.signature_requests.remind("sr_...")  # reminder to signers who have not signed
wt.signature_requests.cancel("sr_...")  # links stop working; nothing is refunded

events = wt.signature_requests.list_events("sr_...")  # audit trail
certificate = wt.signature_requests.certificate("sr_...")  # completion certificate

# One request per recipient (plan feature "bulk")
bulk = wt.signature_requests.create_bulk(
    source={"type": "template", "template_id": "tpl_123"},
    recipients=[{"name": "A", "email": "a@example.com"}, {"name": "B", "email": "b@example.com"}],
)
print(bulk.created, bulk.failed)

# Completed requests
download = wt.signature_requests.download("sr_...")  # metadata: pdf_status, pdf_sha256, ...
pdf = wt.signature_requests.download_pdf("sr_...")  # bytes, checked against X-File-Sha256
print(pdf.filename, pdf.sha256, len(pdf))
wt.signature_requests.download_pdf_to("sr_...", "signed/contract.pdf")  # written atomically
evidence = wt.signature_requests.evidence("sr_...")  # sealed evidence record (Ed25519 + RFC 3161)
```

`download_pdf` raises `ConflictError` with `code == "pdf_not_ready"` while the PDF is being prepared: retry later.

### Sessions (workflows)

A session is a signature request created from a workflow configured in the developer portal (or the built-in
`default` workflow). Sessions accept options that `signature_requests.create` does not, such as `channel`,
`language`, `expires_in`, `return_url` and `vendor_data`.

```python
session = wt.sessions.create(
    workflow_id="default",
    template_id="tpl_123",
    channel="link",  # send nothing: you deliver session.sign_url yourself
    language="en",
    vendor_data="user-42",
    signers=[{"name": "Noha", "email": "noha@example.com"}],
)
print(session.sign_url)

wt.sessions.retrieve(session.id)
for s in wt.sessions.all(vendor_data="user-42"):
    print(s.id, s.status)
```

The session id is a signature request id: every `signature_requests` method works on it.

### Signers and embedded signing

```python
signer = wt.signers.retrieve("sgr_...")

link = wt.signers.create_signing_session("sgr_...")  # iframe mode (plan feature "embed")
print(link.signing_url, link.expires_at)  # valid for 30 minutes

redirect = wt.signers.create_signing_session(
    "sgr_...", mode="redirect", success_url="https://acme.example/signed"
)
```

### Documents

```python
document = wt.documents.create(
    "contract.pdf", kind="pdf"
)  # path, bytes, file object or (name, bytes)
document = wt.documents.retrieve(document.id)
```

The file must be a PDF of at most 20 MB.

### Identity verifications and public verification

```python
idv = wt.identity_verifications.retrieve("idv_12")
print(idv.status)  # pending, approved, in_review, resubmission_requested, declined, expired

result = wt.verifications.retrieve("WTQ-1A2B3C4D5E6F")
if result.found:
    print(result.status, result.integrity)
else:
    print("unknown reference")  # an unknown reference is a result, not an exception
```

### Webhook endpoints and events

```python
endpoint = wt.webhook_endpoints.create(
    url="https://acme.example/hooks/wthaiq",
    enabled_events=["signature_request.completed", "signer.signed"],
)
print(endpoint.secret)  # whsec_... returned only once: store it now

wt.webhook_endpoints.update(endpoint.id, status="disabled")
wt.webhook_endpoints.deliveries(endpoint.id)  # last 50 deliveries
wt.webhook_endpoints.test(endpoint.id)  # sends a synthetic event
wt.webhook_endpoints.event_types()  # every event type
wt.webhook_endpoints.delete(endpoint.id)

for event in wt.events.all(type="signature_request.completed"):
    print(event.id, event.data.object.id)
wt.events.redeliver("evt_...", endpoint="we_...")
```

### Flows

```python
flows = wt.flows.list()  # embeddable console flows (read-only)
flow = wt.flows.retrieve("flow_...")
```

## Responses

Responses are immutable objects with attribute access, item access and `to_dict()`:

```python
sr = wt.signature_requests.retrieve("sr_...")
sr.status  # "sent"
sr["status"]  # same
sr.signers[0].email  # nested objects are typed (Signer)
sr.metadata.order_id  # your metadata
sr.to_dict()  # plain JSON data
sr.to_json(indent=2)
```

Typed classes (`SignatureRequest`, `Signer`, `Template`, `Session`, `Event`, ...) give editors and type checkers
the documented fields. Fields added to the API later remain readable as attributes; documented fields absent
from a response read as `None`.

Every top-level object carries the HTTP details of the call that returned it:

```python
info = sr.last_response
info.status_code  # 200
info.request_id  # "req_281e9f1032a69557b2" — quote it to support
info.idempotent_replayed  # True when a stored response was replayed
info.rate_limit  # RateLimit(limit=100, remaining=97, reset=1791353300)
```

## Pagination

`list()` returns one page; `auto_paging_iter()` and `all()` iterate over every item and request the next pages
lazily.

```python
page = wt.signature_requests.list(status="completed", limit=100)
page.data, page.has_more, page.next_cursor

for sr in wt.signature_requests.list(status="completed", limit=100).auto_paging_iter():
    print(sr.id, sr.reference)

for sr in wt.signature_requests.all(created_after="2026-10-01"):
    ...

next_page = page.next_page()  # None on the last page
```

## Async usage

`AsyncClient` has the same resources and methods; every call is awaited. `all()` and
`auto_paging_iter()` return async iterators.

```python
import asyncio
import wthaiq


async def main() -> None:
    async with wthaiq.AsyncClient() as wt:
        root, usage = await asyncio.gather(wt.account.retrieve(), wt.usage.retrieve())

        sr = await wt.signature_requests.create(
            source={"type": "template", "template_id": "tpl_123"},
            signers=[{"name": "Noha", "email": "noha@example.com"}],
        )

        async for item in wt.signature_requests.all(status="completed"):
            print(item.id)

        page = await wt.templates.list(scope="mine")
        async for template in page.auto_paging_iter():
            print(template.name)


asyncio.run(main())
```

With `httpx` installed (`pip install "wthaiq[httpx]"`), `AsyncClient` uses `httpx.AsyncClient`. Without it,
requests run on the standard library in a worker thread, so the async client works everywhere.

## Error handling

Every exception derives from `wthaiq.WthaiqError`; HTTP errors derive from `wthaiq.ApiError` and carry
`status_code`, `code`, `param`, `type`, `request_id`, `error` (the decoded error object), `raw_body` and
`headers`. Branch on `code`, never on the message (the message is human text, currently in Arabic).

```python
import wthaiq

try:
    wt.signature_requests.create(
        source={"type": "template", "template_id": "tpl_123"},
        signers=[{"name": "Noha", "email": "not-an-email"}],
    )
except wthaiq.ValidationError as e:  # 400
    print(e.code, e.param, e.field_errors)  # invalid_request signers[0].email {...}
except wthaiq.PaymentRequiredError as e:  # 402 plan_required / plan_expired / insufficient_balance
    print(e.code, e.upgrade_url)
except wthaiq.PermissionDeniedError as e:  # 403
    if e.is_plan_feature_unavailable():
        print(f"Needs the {e.required_plan} plan for {e.feature}: {e.upgrade_url}")
    elif e.is_kyb_required():
        print("Verify your company:", e.upgrade_url)
except wthaiq.RateLimitError as e:  # 429
    print(e.code, e.retry_after)
except wthaiq.ApiError as e:
    print(e.status_code, e.code, e.request_id)
except wthaiq.ApiConnectionError as e:  # network failure or timeout
    print("network:", e, e.timed_out)
```

| Exception | When |
|---|---|
| `ValidationError` (`InvalidRequestError`) | 400: missing or invalid parameter (`param` names it). |
| `AuthenticationError` | 401: missing, invalid or revoked key; inactive account. |
| `PaymentRequiredError` | 402: `plan_required`, `plan_expired`, `insufficient_balance`. |
| `PermissionDeniedError` | 403: `forbidden`, `plan_feature_unavailable`, `kyb_required`, `ip_not_allowed`, `holder_only`. Also importable as `wthaiq.error.PermissionError`. |
| `NotFoundError` (`InvalidRequestError`) | 404: not found, another account's object, or the other mode. |
| `ConflictError` (`InvalidRequestError`) | 409: `idempotency_key_reused`, `idempotency_in_progress`, `request_not_cancelable`, `pdf_not_ready`, ... |
| `InvalidRequestError` | Other 4xx, e.g. 405. |
| `RateLimitError` | 429: `too_many_requests` (retried automatically), `daily_cap_reached`, `reminder_*`, `test_*_limit`. |
| `ServerError` | 5xx: `internal_error`, `delivery_failed`, `feature_unavailable`, `not_implemented`. |
| `ApiConnectionError` | No response: DNS, TLS, connection failure or timeout (`timed_out`). |
| `UnexpectedResponseError` | A response that is not valid JSON, or a PDF that fails its fingerprint check. |
| `SignatureVerificationError` | Webhook signature, timestamp or payload invalid. |
| `InvalidArgumentError` | Invalid arguments, detected before any request (also a `ValueError`). |

## Retries, idempotency and timeouts

- Retried automatically (default 2 retries): connection errors and timeouts, `429 too_many_requests`,
  `409 idempotency_in_progress`, `500`, `502` (except `delivery_failed`), `503` (except `feature_unavailable`)
  and `504`. Quota-style `429` codes (`daily_cap_reached`, `reminder_limit_reached`, `reminder_too_soon`,
  `test_daily_limit`, `test_email_limit`) and other `4xx` are never retried.
- Delays honour `Retry-After` (capped at 60 s); otherwise exponential backoff from 0.5 s to 8 s with jitter.
- Every `POST` carries an `Idempotency-Key` (a random UUID unless you pass one), reused on each retry, so a
  retried create never creates two requests. Pass your own key to make your own retries safe:

```python
sr = wt.signature_requests.create(..., idempotency_key=f"order-{order.id}")
sr.last_response.idempotent_replayed  # True if the API replayed the first response
```

Per-call options override the client settings:

```python
wt.signature_requests.retrieve("sr_...", timeout=10, max_retries=5)
wt.signature_requests.list(api_key="sk_test_other...", headers={"X-Trace-Id": "abc"})
```

Fine-tune backoff with `RetryPolicy(initial_delay=0.5, max_delay=8.0, max_retry_after=60.0)`.

## Webhooks

Wthaiq signs every delivery with your endpoint secret in the `Wthaiq-Signature` header
(`t=<unix seconds>,v1=<hex HMAC-SHA256>`). `Webhook.construct_event()` verifies the signature in constant time,
rejects timestamps older than `tolerance` seconds (default 300), and returns the typed event. Always pass the
**raw** request body. Deliveries can repeat: dedupe on `event.id` (also sent as `Wthaiq-Event-Id`).

### Flask

```python
import os
import wthaiq
from flask import Flask, request

app = Flask(__name__)
endpoint_secret = os.environ["WTHAIQ_WEBHOOK_SECRET"]


@app.post("/hooks/wthaiq")
def handle():
    payload = request.get_data()
    sig = request.headers.get("Wthaiq-Signature")
    try:
        event = wthaiq.Webhook.construct_event(payload, sig, endpoint_secret)
    except wthaiq.error.SignatureVerificationError:
        return "invalid signature", 400
    if event.type == "signature_request.completed":
        sr = event.data.object  # SignatureRequest
        print(sr.id, sr.reference)
    return {"received": True}
```

### FastAPI

```python
import os
import wthaiq
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()
endpoint_secret = os.environ["WTHAIQ_WEBHOOK_SECRET"]


@app.post("/hooks/wthaiq")
async def handle(request: Request) -> dict[str, bool]:
    payload = await request.body()
    try:
        event = wthaiq.Webhook.construct_event(
            payload, request.headers.get("Wthaiq-Signature"), endpoint_secret
        )
    except wthaiq.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="invalid signature")
    if event.type == "signer.signed":
        signer = event.data.object  # Signer (+ signature_request)
        print(signer.name, signer.signature_request)
    return {"received": True}
```

### Django

```python
import os
import wthaiq
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

endpoint_secret = os.environ["WTHAIQ_WEBHOOK_SECRET"]


@csrf_exempt
@require_POST
def wthaiq_webhook(request):
    try:
        event = wthaiq.Webhook.construct_event(
            request.body, request.headers.get("Wthaiq-Signature"), endpoint_secret
        )
    except wthaiq.SignatureVerificationError:
        return HttpResponseBadRequest("invalid signature")
    if event.type == "signature_request.completed":
        ...
    return HttpResponse(status=200)
```

Respond with a `2xx` within 10 seconds; failed deliveries are retried with growing delays (9 attempts over
about two days). Other helpers:
`Webhook.verify_header(...)` (verify without decoding), `Webhook.is_valid(...)` (returns a bool) and
`Webhook.generate_test_header(payload, secret)` for your own tests. `wthaiq.EVENT_TYPES` lists every event type.

## Custom HTTP transport

The default synchronous transport uses only the standard library (`urllib`): TLS certificates are always
verified, redirects are never followed (so the key never leaves the API host), and proxies come from the usual
`HTTPS_PROXY` / `NO_PROXY` environment variables. Pass `http_client` to change it:

```python
import httpx
import wthaiq

# An httpx client (connection pooling, HTTP/2, your proxy and TLS settings)
wt = wthaiq.Client(http_client=httpx.Client(proxy="http://proxy.internal:3128"))
awt = wthaiq.AsyncClient(http_client=httpx.AsyncClient(http2=True))

# Custom TLS or proxies with the standard library
import ssl

wt = wthaiq.Client(
    http_client=wthaiq.UrllibTransport(
        ssl_context=ssl.create_default_context(cafile="corp-ca.pem"),
        proxies={"https": "http://proxy.internal:3128"},
    )
)


# Any callable that takes an HttpRequest and returns an HttpResponse (logging, tests, ...)
def send(request: wthaiq.HttpRequest) -> wthaiq.HttpResponse: ...


wt = wthaiq.Client(http_client=send)
```

A transport is any object with `send(request: HttpRequest) -> HttpResponse` (`async def send` for
`AsyncClient`). It returns a response for every HTTP status and raises `ApiConnectionError` when no response
was received. Never log the `Authorization` header, request bodies with personal data, or webhook secrets.

## Versioning

This library follows [Semantic Versioning](https://semver.org). Version 1.x targets API version `2026-07-01`
(`wthaiq.API_VERSION`), sent with every request as `Wthaiq-Version`. New endpoints and fields arrive in minor
releases; a change of the pinned API version or a removal is a major release. Supported Python versions:
3.10 to 3.13. See [CHANGELOG.md](CHANGELOG.md).

## Support and security

- Documentation: <https://developers.wthaiq.com/docs>
- Developer portal (keys, plans, workflows): <https://developers.wthaiq.com>
- Support: <support@wthaiq.com> — include the `request_id` of the failing call.
- Security issues: please report privately as described in [SECURITY.md](SECURITY.md).

Licensed under the [MIT License](LICENSE).

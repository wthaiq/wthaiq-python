from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest

import wthaiq
from wthaiq import HttpRequest, HttpResponse, RetryPolicy

TEST_KEY = "sk_test_" + "a" * 40
LIVE_KEY = "sk_" + "b" * 40
BASE = "https://wthaiq.com/api/v1"


def response(
    status: int = 200,
    body: Any = None,
    headers: dict[str, str] | None = None,
    raw: bytes | None = None,
) -> HttpResponse:
    payload = raw if raw is not None else json.dumps(body if body is not None else {}).encode()
    base = {"content-type": "application/json", "wthaiq-request-id": "req_0123456789abcdef01"}
    base.update({k.lower(): v for k, v in (headers or {}).items()})
    return HttpResponse(status, base, payload)


def error(
    status: int, code: str | None, *, type: str = "invalid_request_error", **extra: Any
) -> HttpResponse:
    headers = extra.pop("headers", None)
    body: dict[str, Any] = {"type": type, "message": "رسالة الخطأ", "request_id": "req_err"}
    if code is not None:
        body["code"] = code
    body.update(extra)
    return response(status, {"error": body}, headers)


Responder = HttpResponse | Exception | Callable[[HttpRequest], HttpResponse]


class FakeTransport:
    """Records requests and replays queued responses (the last one repeats)."""

    def __init__(self, *responses: Responder) -> None:
        self.queue: list[Responder] = list(responses) or [response(200, {})]
        self.requests: list[HttpRequest] = []

    def _next(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        item = self.queue.pop(0) if len(self.queue) > 1 else self.queue[0]
        if isinstance(item, Exception):
            raise item
        if callable(item):
            return item(request)
        return item

    def send(self, request: HttpRequest) -> HttpResponse:
        return self._next(request)

    @property
    def last(self) -> HttpRequest:
        return self.requests[-1]


class AsyncFakeTransport(FakeTransport):
    async def send(self, request: HttpRequest) -> HttpResponse:  # type: ignore[override]
        return self._next(request)


class SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)

    async def asleep(self, seconds: float) -> None:
        self.calls.append(seconds)


def make_client(
    transport: FakeTransport, *, sleeper: SleepRecorder | None = None, **options: Any
) -> wthaiq.Client:
    sleeper = sleeper or SleepRecorder()
    policy = RetryPolicy(sleep=sleeper, async_sleep=sleeper.asleep, random=lambda: 1.0)
    options.setdefault("retry_policy", policy)
    return wthaiq.Client(options.pop("api_key", TEST_KEY), http_client=transport, **options)


def make_async_client(
    transport: AsyncFakeTransport, *, sleeper: SleepRecorder | None = None, **options: Any
) -> wthaiq.AsyncClient:
    sleeper = sleeper or SleepRecorder()
    policy = RetryPolicy(sleep=sleeper, async_sleep=sleeper.asleep, random=lambda: 1.0)
    options.setdefault("retry_policy", policy)
    return wthaiq.AsyncClient(options.pop("api_key", TEST_KEY), http_client=transport, **options)


def path_of(request: HttpRequest) -> str:
    return urlsplit(request.url).path.removeprefix("/api/v1") or "/"


def query_of(request: HttpRequest) -> list[tuple[str, str]]:
    return parse_qsl(urlsplit(request.url).query, keep_blank_values=True)


def body_of(request: HttpRequest) -> Any:
    assert request.body is not None
    return json.loads(request.body.decode("utf-8"))


def page(
    items: Iterable[dict[str, Any]], has_more: bool = False, cursor: str | None = None
) -> HttpResponse:
    return response(
        200, {"object": "list", "data": list(items), "has_more": has_more, "next_cursor": cursor}
    )


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def sleeper() -> SleepRecorder:
    return SleepRecorder()


SIGNATURE_REQUEST = {
    "id": "sr_cd5a6eb8468344583538",
    "object": "signature_request",
    "livemode": False,
    "status": "draft",
    "title": "عقد خدمات",
    "legal_level": "ses",
    "format": "pades-lt",
    "source": {"type": "template", "template_id": "tpl_998488"},
    "signers": [
        {
            "id": "sgr_71769e6564cbb1d00ccc",
            "object": "signer",
            "name": "Noha",
            "email": "noha@example.com",
            "phone": None,
            "type": "individual",
            "method": "draw",
            "require_identity": False,
            "order": 1,
            "status": "pending",
            "signing_url": None,
            "viewed_at": None,
            "signed_at": None,
            "fields": {"amount": "100"},
        }
    ],
    "ordered": False,
    "require_identity": False,
    "reference": None,
    "cc": [{"name": "", "email": "legal@example.com"}],
    "reminders": {"enabled": True, "interval_hours": 48, "max": 3},
    "metadata": {"order": "A1"},
    "expires_at": 1791958089,
    "completed_at": None,
    "download_url": None,
    "created_at": 1791353289,
}

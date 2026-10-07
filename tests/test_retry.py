from __future__ import annotations

import asyncio

import pytest

import wthaiq
from wthaiq import RetryPolicy

from .conftest import (
    SIGNATURE_REQUEST,
    AsyncFakeTransport,
    FakeTransport,
    SleepRecorder,
    error,
    make_async_client,
    make_client,
    response,
)

OK = response(200, {"object": "api_root"})


@pytest.mark.parametrize(
    "failure",
    [
        error(500, "internal_error", type="api_error"),
        error(502, None, type="api_error"),
        error(503, None, type="api_error"),
        error(504, None, type="api_error"),
        error(429, "too_many_requests", type="rate_limit_error"),
        error(409, "idempotency_in_progress", type="idempotency_error"),
        wthaiq.ApiConnectionError("connection reset"),
        wthaiq.ApiConnectionError("timed out", timed_out=True),
    ],
)
def test_transient_failures_are_retried(failure: object, sleeper: SleepRecorder) -> None:
    transport = FakeTransport(failure, failure, OK)  # type: ignore[arg-type]
    client = make_client(transport, sleeper=sleeper)
    assert client.account.retrieve().object == "api_root"
    assert len(transport.requests) == 3
    assert sleeper.calls == [0.5, 1.0]


@pytest.mark.parametrize(
    "failure",
    [
        error(502, "delivery_failed", type="api_error"),
        error(503, "feature_unavailable", type="api_error"),
        error(501, "not_implemented", type="api_error"),
        error(429, "daily_cap_reached", type="rate_limit_error"),
        error(429, "reminder_limit_reached", type="rate_limit_error"),
        error(429, "reminder_too_soon", type="rate_limit_error"),
        error(429, "test_daily_limit", type="rate_limit_error"),
        error(429, "test_email_limit", type="rate_limit_error"),
        error(409, "idempotency_key_reused", type="idempotency_error"),
        error(400, "parameter_missing"),
        error(401, "invalid_api_key"),
        error(402, "insufficient_balance"),
        error(403, "forbidden"),
        error(404, "resource_missing"),
    ],
)
def test_permanent_failures_are_not_retried(failure: object, sleeper: SleepRecorder) -> None:
    transport = FakeTransport(failure, OK)  # type: ignore[arg-type]
    client = make_client(transport, sleeper=sleeper)
    with pytest.raises(wthaiq.ApiError):
        client.account.retrieve()
    assert len(transport.requests) == 1
    assert sleeper.calls == []


def test_gives_up_after_max_retries(sleeper: SleepRecorder) -> None:
    failure = error(503, None, type="api_error")
    transport = FakeTransport(failure)
    client = make_client(transport, sleeper=sleeper)
    with pytest.raises(wthaiq.ServerError):
        client.account.retrieve()
    assert len(transport.requests) == 3
    transport = FakeTransport(failure)
    with pytest.raises(wthaiq.ServerError):
        make_client(transport, max_retries=0).account.retrieve()
    assert len(transport.requests) == 1
    transport = FakeTransport(failure)
    with pytest.raises(wthaiq.ServerError):
        make_client(transport).account.retrieve(max_retries=4)
    assert len(transport.requests) == 5


def test_connection_error_surfaces_after_retries() -> None:
    transport = FakeTransport(wthaiq.ApiConnectionError("refused"))
    with pytest.raises(wthaiq.ApiConnectionError, match="refused"):
        make_client(transport, max_retries=1).account.retrieve()
    assert len(transport.requests) == 2


def test_other_transport_exceptions_propagate() -> None:
    transport = FakeTransport(RuntimeError("bug in a custom transport"))
    with pytest.raises(RuntimeError):
        make_client(transport).account.retrieve()
    assert len(transport.requests) == 1


def test_retry_after_is_honoured_and_capped(sleeper: SleepRecorder) -> None:
    transport = FakeTransport(
        error(429, "too_many_requests", headers={"Retry-After": "7"}),
        error(409, "idempotency_in_progress", headers={"Retry-After": "600"}),
        OK,
    )
    make_client(transport, sleeper=sleeper).account.retrieve()
    assert sleeper.calls == [7.0, 60.0]


def test_idempotency_key_is_reused_across_retries(sleeper: SleepRecorder) -> None:
    transport = FakeTransport(
        error(500, "internal_error"),
        wthaiq.ApiConnectionError("reset"),
        response(201, SIGNATURE_REQUEST),
    )
    make_client(transport, sleeper=sleeper).signature_requests.create(title="x")
    keys = {request.headers["Idempotency-Key"] for request in transport.requests}
    assert len(transport.requests) == 3
    assert len(keys) == 1


def test_backoff_schedule() -> None:
    policy = RetryPolicy(random=lambda: 0.0)
    assert [policy.delay(n) for n in range(6)] == [0.25, 0.5, 1.0, 2.0, 4.0, 4.0]
    policy = RetryPolicy(random=lambda: 1.0)
    assert [policy.delay(n) for n in range(6)] == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0]
    assert policy.delay(0, "2.5") == 2.5
    assert policy.delay(0, "abc") == 0.5
    assert policy.delay(0, "") == 0.5
    assert policy.delay(0, chr(0x663)) == 0.5, "only ASCII digits are read"
    custom = RetryPolicy(initial_delay=1, max_delay=3, max_retry_after=5, random=lambda: 1.0)
    assert [custom.delay(n) for n in range(4)] == [1.0, 2.0, 3.0, 3.0]
    assert custom.delay(0, "10") == 5.0


def test_should_retry_matrix() -> None:
    policy = RetryPolicy()
    assert policy.should_retry(None, None)
    assert policy.should_retry(429, None)
    assert not policy.should_retry(409, None)
    assert not policy.should_retry(400, None)
    assert not policy.should_retry(500, "delivery_failed")


def test_default_policy_sleeps_with_time_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []
    monkeypatch.setattr("time.sleep", calls.append)
    policy = RetryPolicy()
    policy.sleep(0.01)
    assert calls == [0.01]


def test_async_retries(sleeper: SleepRecorder) -> None:
    async def run() -> None:
        transport = AsyncFakeTransport(
            error(503, None),
            wthaiq.ApiConnectionError("reset"),
            response(201, SIGNATURE_REQUEST),
        )
        client = make_async_client(transport, sleeper=sleeper)
        sr = await client.signature_requests.create(title="x")
        assert sr.id == SIGNATURE_REQUEST["id"]
        assert len({r.headers["Idempotency-Key"] for r in transport.requests}) == 1
        assert sleeper.calls == [0.5, 1.0]

        failing = AsyncFakeTransport(error(429, "test_daily_limit"))
        with pytest.raises(wthaiq.RateLimitError):
            await make_async_client(failing).signature_requests.create(title="x")
        assert len(failing.requests) == 1

        down = AsyncFakeTransport(wthaiq.ApiConnectionError("down"))
        with pytest.raises(wthaiq.ApiConnectionError):
            await make_async_client(down, max_retries=1).account.retrieve()
        assert len(down.requests) == 2

    asyncio.run(run())


def test_default_async_sleep() -> None:
    asyncio.run(RetryPolicy().async_sleep(0))

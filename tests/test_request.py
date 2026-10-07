from __future__ import annotations

import datetime as dt
import re
import uuid

import pytest

import wthaiq
from wthaiq import InvalidArgumentError

from .conftest import (
    LIVE_KEY,
    SIGNATURE_REQUEST,
    TEST_KEY,
    FakeTransport,
    body_of,
    make_client,
    path_of,
    query_of,
    response,
)


def test_standard_headers_on_get() -> None:
    transport = FakeTransport(response(200, SIGNATURE_REQUEST))
    client = make_client(transport)
    client.signature_requests.retrieve("sr_1")
    request = transport.last
    assert request.method == "GET"
    assert request.url == "https://wthaiq.com/api/v1/signature_requests/sr_1"
    assert request.headers["Authorization"] == f"Bearer {TEST_KEY}"
    assert request.headers["Wthaiq-Version"] == "2026-07-01"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-Agent"].startswith("wthaiq-python/1.0.0 Python/")
    assert "Idempotency-Key" not in request.headers
    assert "Content-Type" not in request.headers
    assert request.body is None
    assert request.timeout == 60.0
    assert request.connect_timeout == 10.0


def test_post_gets_json_body_and_automatic_idempotency_key() -> None:
    transport = FakeTransport(response(201, SIGNATURE_REQUEST))
    client = make_client(transport)
    client.signature_requests.create(
        title="عقد / خدمات",
        source={"type": "template", "template_id": "tpl_1"},
        signers=[{"name": "Noha", "email": "noha@example.com"}],
        metadata={"path": "/a/b"},
    )
    request = transport.last
    assert request.headers["Content-Type"] == "application/json"
    key = request.headers["Idempotency-Key"]
    assert uuid.UUID(key).version == 4
    assert request.body is not None
    text = request.body.decode("utf-8")
    assert "عقد / خدمات" in text, "unicode and slashes are sent unescaped"
    assert body_of(request)["metadata"] == {"path": "/a/b"}


def test_each_post_gets_a_new_idempotency_key() -> None:
    transport = FakeTransport(response(200, SIGNATURE_REQUEST))
    client = make_client(transport)
    client.signature_requests.cancel("sr_1")
    client.signature_requests.cancel("sr_1")
    keys = {request.headers["Idempotency-Key"] for request in transport.requests}
    assert len(keys) == 2


def test_post_without_params_sends_empty_object() -> None:
    transport = FakeTransport(response(200, SIGNATURE_REQUEST))
    make_client(transport).signature_requests.send("sr_1")
    assert transport.last.body == b"{}"


def test_request_options() -> None:
    transport = FakeTransport(response(201, SIGNATURE_REQUEST))
    client = make_client(transport)
    client.signature_requests.create(
        {"title": "x"},
        idempotency_key="order-1024",
        timeout=5,
        headers={"X-Trace": "abc", "Wthaiq-Version": "2099-01-01"},
        api_key=LIVE_KEY,
    )
    request = transport.last
    assert request.headers["Idempotency-Key"] == "order-1024"
    assert request.timeout == 5.0
    assert request.headers["X-Trace"] == "abc"
    assert request.headers["Wthaiq-Version"] == "2099-01-01"
    assert request.headers["Authorization"] == f"Bearer {LIVE_KEY}"
    assert body_of(request) == {"title": "x"}, "request options never reach the body"


def test_positional_params_and_keywords_merge() -> None:
    transport = FakeTransport(response(201, SIGNATURE_REQUEST))
    make_client(transport).signature_requests.create(
        {"title": "a", "future_param": 1}, title="b", send=False
    )
    assert body_of(transport.last) == {"title": "b", "future_param": 1, "send": False}


@pytest.mark.parametrize(
    "options",
    [
        {"idempotency_key": ""},
        {"idempotency_key": "x" * 201},
        {"timeout": 0},
        {"timeout": "5"},
        {"max_retries": -1},
        {"max_retries": True},
        {"headers": {"Authorization": "Bearer other"}},
        {"headers": {"X": 1}},
        {"api_key": "bad"},
    ],
)
def test_invalid_request_options(options: dict[str, object]) -> None:
    client = make_client(FakeTransport())
    with pytest.raises(InvalidArgumentError):
        client.signature_requests.retrieve("sr_1", **options)  # type: ignore[arg-type]


def test_unknown_keyword_on_method_without_params() -> None:
    client = make_client(FakeTransport())
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        client.signature_requests.retrieve("sr_1", expand="signers")  # type: ignore[call-arg]


def test_positional_params_must_be_a_mapping() -> None:
    client = make_client(FakeTransport())
    with pytest.raises(InvalidArgumentError):
        client.signature_requests.create(["x"])  # type: ignore[arg-type]


def test_params_must_be_json_encodable() -> None:
    client = make_client(FakeTransport())
    with pytest.raises(InvalidArgumentError):
        client.signature_requests.create(metadata={"x": object()})


def test_query_encoding() -> None:
    transport = FakeTransport(response(200, {"object": "list", "data": [], "has_more": False}))
    client = make_client(transport)
    client.signature_requests.list(
        status="completed",
        limit=5,
        created_after=dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc),
        created_before=dt.date(2026, 10, 2),
        starting_after=None,  # type: ignore[arg-type]
    )
    assert query_of(transport.last) == [
        ("status", "completed"),
        ("limit", "5"),
        ("created_after", "1790812800"),
        ("created_before", "1790899200"),
    ]
    client.templates.list({"scope": "mine", "flag": True, "ids": ["a", "b"]})
    assert query_of(transport.last) == [
        ("scope", "mine"),
        ("flag", "true"),
        ("ids[]", "a"),
        ("ids[]", "b"),
    ]


def test_invalid_query_value() -> None:
    client = make_client(FakeTransport())
    with pytest.raises(InvalidArgumentError):
        client.templates.list({"x": {"nested": 1}})


def test_ids_are_url_encoded() -> None:
    transport = FakeTransport(response(200, {"object": "verification", "found": True}))
    client = make_client(transport)
    client.verifications.retrieve("WTQ-1/2 3?x")
    assert transport.last.url.endswith("/verifications/WTQ-1%2F2%203%3Fx")
    client.templates.retrieve(123)
    assert path_of(transport.last) == "/templates/123"


@pytest.mark.parametrize("bad_id", ["", "  ", None, True, 1.5])
def test_invalid_ids(bad_id: object) -> None:
    client = make_client(FakeTransport())
    with pytest.raises(InvalidArgumentError):
        client.signature_requests.retrieve(bad_id)  # type: ignore[arg-type]


def test_base_url_with_path() -> None:
    transport = FakeTransport(response(200, {"object": "api_root"}))
    make_client(transport, base_url="http://127.0.0.1:8782/api/v1/").account.retrieve()
    assert transport.last.url == "http://127.0.0.1:8782/api/v1/"


def test_client_timeout_applies() -> None:
    transport = FakeTransport(response(200, {"object": "api_root"}))
    make_client(transport, timeout=12.5, connect_timeout=3).account.retrieve()
    assert transport.last.timeout == 12.5
    assert transport.last.connect_timeout == 3.0


def test_response_metadata() -> None:
    headers = {
        "Wthaiq-Request-Id": "req_281e9f1032a69557b2",
        "Wthaiq-Version": "2026-07-01",
        "Idempotent-Replayed": "true",
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "97",
        "X-RateLimit-Reset": "1791353300",
    }
    transport = FakeTransport(response(201, SIGNATURE_REQUEST, headers))
    sr = make_client(transport).signature_requests.create(title="x")
    info = sr.last_response
    assert info is not None
    assert info.status_code == 201
    assert info.request_id == "req_281e9f1032a69557b2"
    assert info.api_version == "2026-07-01"
    assert info.idempotent_replayed is True
    assert info.rate_limit == wthaiq.objects.RateLimit(100, 97, 1791353300)
    assert info.get_header("X-RATELIMIT-LIMIT") == "100"
    plain = FakeTransport(response(200, SIGNATURE_REQUEST, {"wthaiq-request-id": ""}))
    other = make_client(plain).signature_requests.retrieve("sr_1").last_response
    assert other is not None
    assert other.idempotent_replayed is False
    assert other.rate_limit is None


@pytest.mark.parametrize("raw", [b"<html>oops</html>", b"[1, 2]", b"", b"null"])
def test_unexpected_success_body(raw: bytes) -> None:
    client = make_client(FakeTransport(response(200, raw=raw)))
    with pytest.raises(wthaiq.UnexpectedResponseError) as info:
        client.account.retrieve()
    assert info.value.status_code == 200
    assert re.search("expected a JSON object", str(info.value))

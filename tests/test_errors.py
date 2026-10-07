from __future__ import annotations

import pytest

import wthaiq
from wthaiq import error as errors

from .conftest import FakeTransport, error, make_client, response


@pytest.mark.parametrize(
    ("status", "code", "cls"),
    [
        (400, "parameter_missing", errors.ValidationError),
        (401, "invalid_api_key", errors.AuthenticationError),
        (402, "plan_required", errors.PaymentRequiredError),
        (403, "forbidden", errors.PermissionError),
        (404, "resource_missing", errors.NotFoundError),
        (405, "method_not_allowed", errors.InvalidRequestError),
        (409, "request_not_cancelable", errors.ConflictError),
        (429, "test_daily_limit", errors.RateLimitError),
        (501, "not_implemented", errors.ServerError),
        (418, None, errors.InvalidRequestError),
    ],
)
def test_status_mapping(status: int, code: str | None, cls: type[errors.ApiError]) -> None:
    client = make_client(FakeTransport(error(status, code)), max_retries=0)
    with pytest.raises(cls) as info:
        client.account.retrieve()
    exc = info.value
    assert type(exc) is cls
    assert isinstance(exc, wthaiq.ApiError)
    assert isinstance(exc, wthaiq.WthaiqError)
    assert exc.status_code == exc.http_status == status
    assert exc.code == code
    assert exc.message == "رسالة الخطأ"
    assert exc.request_id == "req_err"
    assert str(exc) == "رسالة الخطأ (request_id: req_err)"
    assert "status_code=" in repr(exc)


def test_validation_error_details() -> None:
    body = error(400, "invalid_request", param="signers[0].email")
    client = make_client(FakeTransport(body))
    with pytest.raises(wthaiq.ValidationError) as info:
        client.signature_requests.create(title="x")
    exc = info.value
    assert exc.type == "invalid_request_error"
    assert exc.param == "signers[0].email"
    assert exc.field_errors == {"signers[0].email": "رسالة الخطأ"}
    assert exc.error["param"] == "signers[0].email"
    assert exc.get_header("Content-Type") == "application/json"
    assert '"param"' in exc.raw_body


def test_validation_without_param() -> None:
    client = make_client(FakeTransport(error(400, "invalid_json")))
    with pytest.raises(wthaiq.ValidationError) as info:
        client.account.retrieve()
    assert info.value.field_errors == {}


def test_permission_error_helpers() -> None:
    feature = error(
        403,
        "plan_feature_unavailable",
        type="permission_error",
        feature="bulk",
        required_plan="ap_ent",
        upgrade_url="https://developers.wthaiq.com/plans?f=bulk",
    )
    client = make_client(FakeTransport(feature))
    with pytest.raises(wthaiq.PermissionDeniedError) as info:
        client.signature_requests.create_bulk(recipients=[])
    exc = info.value
    assert isinstance(exc, wthaiq.error.PermissionError)
    assert exc.is_plan_feature_unavailable() and not exc.is_kyb_required()
    assert exc.feature == "bulk"
    assert exc.required_plan == "ap_ent"
    assert exc.upgrade_url == "https://developers.wthaiq.com/plans?f=bulk"

    client = make_client(FakeTransport(error(403, "plan_feature_unavailable", feature="embed")))
    with pytest.raises(wthaiq.PermissionDeniedError) as info:
        client.account.retrieve()
    assert info.value.upgrade_url == wthaiq.PLANS_URL

    client = make_client(FakeTransport(error(403, "kyb_required", type="permission_error")))
    with pytest.raises(wthaiq.PermissionDeniedError) as info:
        client.account.retrieve()
    assert info.value.is_kyb_required()
    assert info.value.upgrade_url == wthaiq.VERIFY_URL

    client = make_client(FakeTransport(error(403, "forbidden")))
    with pytest.raises(wthaiq.PermissionDeniedError) as info:
        client.account.retrieve()
    assert info.value.upgrade_url is None
    assert info.value.feature is None


@pytest.mark.parametrize(
    ("code", "check"),
    [
        ("plan_required", "is_plan_required"),
        ("plan_expired", "is_plan_expired"),
        ("insufficient_balance", "is_insufficient_balance"),
    ],
)
def test_payment_required(code: str, check: str) -> None:
    client = make_client(FakeTransport(error(402, code, type="quota_error")))
    with pytest.raises(wthaiq.PaymentRequiredError) as info:
        client.signature_requests.create(title="x")
    assert getattr(info.value, check)() is True
    assert info.value.upgrade_url == wthaiq.PLANS_URL


def test_rate_limit_error() -> None:
    quota = error(
        429, "daily_cap_reached", type="rate_limit_error", headers={"Retry-After": "3600"}
    )
    client = make_client(FakeTransport(quota))
    with pytest.raises(wthaiq.RateLimitError) as info:
        client.signature_requests.create(title="x")
    assert info.value.retry_after == 3600
    assert info.value.is_transient() is False

    client = make_client(FakeTransport(error(429, "too_many_requests")), max_retries=0)
    with pytest.raises(wthaiq.RateLimitError) as info:
        client.account.retrieve()
    assert info.value.retry_after is None
    assert info.value.is_transient() is True


def test_non_json_error_body() -> None:
    raw = response(502, raw=b"<html><body><h1>502 Bad Gateway</h1></body></html>")
    client = make_client(FakeTransport(raw), max_retries=0)
    with pytest.raises(wthaiq.ServerError) as info:
        client.account.retrieve()
    exc = info.value
    assert exc.message == "The Wthaiq API returned HTTP 502: 502 Bad Gateway"
    assert exc.code is None
    assert exc.request_id == "req_0123456789abcdef01", "falls back to the response header"
    assert exc.error == {}


def test_empty_error_body() -> None:
    client = make_client(FakeTransport(response(404, raw=b"")))
    with pytest.raises(wthaiq.NotFoundError) as info:
        client.account.retrieve()
    assert info.value.message == "The Wthaiq API returned HTTP 404."


def test_parse_error_body_edge_cases() -> None:
    assert errors.parse_error_body("") == {}
    assert errors.parse_error_body("not json") == {}
    assert errors.parse_error_body('{"error": "x"}') == {}
    assert errors.parse_error_body('{"error": {"code": 1}}') == {"code": 1}
    exc = errors.error_from_response(400, {}, '{"error": {"code": 7, "message": ""}}')
    assert exc.code == "7"
    assert exc.message.startswith("The Wthaiq API returned HTTP 400")


def test_connection_error_attributes() -> None:
    exc = wthaiq.ApiConnectionError("down", timed_out=True)
    assert exc.timed_out is True
    assert str(exc) == "down"
    assert isinstance(wthaiq.SignatureVerificationError("x", header="t=1"), wthaiq.WthaiqError)

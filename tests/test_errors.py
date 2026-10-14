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


def test_too_many_signers_is_typed_and_carries_the_limit() -> None:
    client = make_client(
        FakeTransport(
            error(400, "too_many_signers", param="signers", max_signers=5),
            error(400, "too_many_signers", param="signers", max_signers=3),
            error(400, "too_many_signers", param="signers"),
            error(400, "too_many_signers", param="signers", max_signers="5"),
            error(400, "too_many_signers", param="signers", max_signers=True),
            error(400, "test_signer_limit", param="signers"),
        )
    )
    limits = []
    for _ in range(5):
        with pytest.raises(wthaiq.TooManySignersError) as info:
            client.signature_requests.create(title="x")
        assert isinstance(info.value, wthaiq.ValidationError)
        assert isinstance(info.value, errors.TooManySignersError)
        assert info.value.code == "too_many_signers"
        assert info.value.field_errors == {"signers": "رسالة الخطأ"}
        limits.append(info.value.max_signers)
    assert limits == [5, 3, wthaiq.MAX_SIGNERS, wthaiq.MAX_SIGNERS, wthaiq.MAX_SIGNERS]
    assert wthaiq.MAX_SIGNERS == 5
    with pytest.raises(wthaiq.ValidationError) as other:
        client.signature_requests.create(title="x")
    assert not isinstance(other.value, wthaiq.TooManySignersError)
    conflict = make_client(FakeTransport(error(409, "too_many_signers")))
    with pytest.raises(wthaiq.ConflictError) as info409:
        conflict.account.retrieve()
    assert not isinstance(info409.value, wthaiq.TooManySignersError)


def test_plan_and_kyb_errors_use_the_urls_sent_by_the_api() -> None:
    plans = "https://developers.wthaiq.com/plans"
    verify = "https://developers.wthaiq.com/verify"
    for code in ("plan_required", "plan_expired"):
        client = make_client(
            FakeTransport(error(402, code, type="quota_error", upgrade_url=f"{plans}?from={code}"))
        )
        with pytest.raises(wthaiq.PaymentRequiredError) as paid:
            client.signature_requests.send("sr_x")
        assert paid.value.upgrade_url == f"{plans}?from={code}"

    client = make_client(
        FakeTransport(error(403, "kyb_required", type="permission_error",
                            verify_url=f"{verify}?step=2"))
    )  # fmt: skip
    with pytest.raises(wthaiq.PermissionDeniedError) as kyb:
        client.signature_requests.send("sr_x")
    assert kyb.value.is_kyb_required()
    assert kyb.value.verify_url == f"{verify}?step=2"
    assert kyb.value.upgrade_url == f"{verify}?step=2"

    client = make_client(FakeTransport(error(403, "kyb_required", type="permission_error")))
    with pytest.raises(wthaiq.PermissionDeniedError) as kyb_default:
        client.signature_requests.send("sr_x")
    assert kyb_default.value.verify_url == wthaiq.VERIFY_URL

    client = make_client(
        FakeTransport(error(403, "plan_feature_unavailable", type="permission_error",
                            feature="embed", required_plan="ap_biz", upgrade_url=plans))
    )  # fmt: skip
    with pytest.raises(wthaiq.PermissionDeniedError) as feature:
        client.signers.create_signing_session("sgr_1")
    assert feature.value.upgrade_url == plans
    assert feature.value.verify_url is None
    assert feature.value.required_plan == "ap_biz"

    client = make_client(FakeTransport(error(403, "forbidden")))
    with pytest.raises(wthaiq.PermissionDeniedError) as forbidden:
        client.account.retrieve()
    assert forbidden.value.verify_url is None


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

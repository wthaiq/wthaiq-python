"""Exceptions raised by the Wthaiq library.

Every exception derives from :class:`WthaiqError`. HTTP errors returned by the API derive from
:class:`ApiError` and are mapped by HTTP status. Branch on :attr:`ApiError.code` (machine readable),
never on the message (human text, currently in Arabic).
"""

from __future__ import annotations

import builtins
import json
import re
from collections.abc import Mapping
from typing import Any

__all__ = [
    "PLANS_URL",
    "VERIFY_URL",
    "ApiConnectionError",
    "ApiError",
    "AuthenticationError",
    "ConflictError",
    "InvalidArgumentError",
    "InvalidRequestError",
    "NotFoundError",
    "PaymentRequiredError",
    "PermissionDeniedError",
    "PermissionError",
    "RateLimitError",
    "ServerError",
    "SignatureVerificationError",
    "UnexpectedResponseError",
    "ValidationError",
    "WthaiqError",
]

PLANS_URL = "https://developers.wthaiq.com/plans"
"""Developer portal page where API plans are bought or upgraded."""

VERIFY_URL = "https://developers.wthaiq.com/verify"
"""Developer portal page where the company is verified (required for live mode)."""


class WthaiqError(Exception):
    """Base class of every exception raised by this library."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class InvalidArgumentError(WthaiqError, ValueError):
    """The library was called with an invalid argument. Raised before any request is sent."""


class ApiConnectionError(WthaiqError):
    """The API could not be reached: DNS, TLS or network failure, or a timeout.

    No HTTP response was received. These failures are retried automatically.
    """

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out
        """``True`` when the request timed out."""


class UnexpectedResponseError(WthaiqError):
    """The API returned a body the library cannot read (not JSON, or a PDF that fails its check)."""

    def __init__(self, message: str, *, status_code: int | None = None, raw_body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.raw_body = raw_body


class SignatureVerificationError(WthaiqError):
    """A webhook signature or timestamp could not be verified."""

    def __init__(self, message: str, *, header: str = "") -> None:
        super().__init__(message)
        self.header = header
        """The ``Wthaiq-Signature`` header that was checked."""


class ApiError(WthaiqError):
    """The API answered with an HTTP error status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        type: str | None = None,
        code: str | None = None,
        param: str | None = None,
        request_id: str | None = None,
        error: Mapping[str, Any] | None = None,
        raw_body: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        """HTTP status code."""
        self.type = type
        """Error type, e.g. ``invalid_request_error`` or ``permission_error``."""
        self.code = code
        """Machine code, e.g. ``parameter_missing``, ``plan_feature_unavailable``."""
        self.param = param
        """The request field the error refers to, e.g. ``signers[0].email``."""
        self.request_id = request_id
        """Request id (``req_…``) to quote to support."""
        self.error: dict[str, Any] = dict(error or {})
        """The decoded ``error`` object of the response body, including fields not modelled here."""
        self.raw_body = raw_body
        """The raw response body."""
        self.headers: dict[str, str] = {k.lower(): v for k, v in (headers or {}).items()}
        """Response headers with lower-case names."""

    @property
    def http_status(self) -> int:
        """Alias of :attr:`status_code`."""
        return self.status_code

    def get_header(self, name: str) -> str | None:
        """Returns a response header (case-insensitive), or ``None``."""
        return self.headers.get(name.lower())

    def __str__(self) -> str:
        if self.request_id:
            return f"{self.message} (request_id: {self.request_id})"
        return self.message

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status_code={self.status_code!r}, code={self.code!r}, "
            f"param={self.param!r}, request_id={self.request_id!r}, message={self.message!r})"
        )


class InvalidRequestError(ApiError):
    """400, 405, 409 and other client errors."""


class ValidationError(InvalidRequestError):
    """400: a parameter is missing or invalid. :attr:`param` names the field."""

    @property
    def field_errors(self) -> dict[str, str]:
        """``{param: message}``, or ``{}`` when the error is not tied to one field."""
        return {} if self.param is None else {self.param: self.message}


class NotFoundError(InvalidRequestError):
    """404: the object does not exist, belongs to another account, or is in the other mode."""


class ConflictError(InvalidRequestError):
    """409: idempotency conflicts and state conflicts.

    Codes: ``idempotency_key_reused``, ``idempotency_in_progress``, ``request_not_cancelable``,
    ``pdf_not_ready``, ``pdf_unavailable``, ``workflow_not_live``.
    """


class AuthenticationError(ApiError):
    """401: the API key is missing, malformed, revoked, or the account is inactive."""


class PermissionError(ApiError):
    """403: the key, plan or company verification does not allow this call.

    Codes: ``forbidden`` (read-only or publishable key), ``plan_feature_unavailable``,
    ``kyb_required``, ``ip_not_allowed``, ``holder_only``. Also available as
    :class:`PermissionDeniedError`, which does not shadow the built-in ``PermissionError``.
    """

    @property
    def feature(self) -> str | None:
        """The missing plan capability (with ``plan_feature_unavailable``), e.g. ``bulk``."""
        return _string_field(self.error, "feature")

    @property
    def required_plan(self) -> str | None:
        """The plan that includes the feature, e.g. ``ap_biz``."""
        return _string_field(self.error, "required_plan")

    @property
    def upgrade_url(self) -> str | None:
        """Where to upgrade the plan or verify the company."""
        url = _string_field(self.error, "upgrade_url")
        if url is not None:
            return url
        if self.is_kyb_required():
            return VERIFY_URL
        return PLANS_URL if self.is_plan_feature_unavailable() else None

    def is_plan_feature_unavailable(self) -> bool:
        return self.code == "plan_feature_unavailable"

    def is_kyb_required(self) -> bool:
        return self.code == "kyb_required"


PermissionDeniedError = PermissionError


class PaymentRequiredError(ApiError):
    """402: no paid plan, plan expired, or wallet balance too low.

    Codes: ``plan_required``, ``plan_expired``, ``insufficient_balance``.
    """

    @property
    def upgrade_url(self) -> str:
        return _string_field(self.error, "upgrade_url") or PLANS_URL

    def is_plan_required(self) -> bool:
        return self.code == "plan_required"

    def is_plan_expired(self) -> bool:
        return self.code == "plan_expired"

    def is_insufficient_balance(self) -> bool:
        return self.code == "insufficient_balance"


class RateLimitError(ApiError):
    """429: too many requests.

    Only ``too_many_requests`` is transient and retried automatically. Quota codes such as
    ``daily_cap_reached``, ``reminder_too_soon`` or ``test_daily_limit`` are not retried.
    """

    @property
    def retry_after(self) -> int | None:
        """Seconds to wait, from the ``Retry-After`` header, or ``None``."""
        value = (self.get_header("retry-after") or "").strip()
        return int(value) if value.isascii() and value.isdigit() else None

    def is_transient(self) -> bool:
        return self.code is None or self.code == "too_many_requests"


class ServerError(ApiError):
    """5xx: ``internal_error``, ``not_implemented``, ``delivery_failed`` or ``feature_unavailable``.

    ``delivery_failed`` and ``feature_unavailable`` are not retried.
    """


def _string_field(source: Mapping[str, Any], key: str) -> str | None:
    value = source.get(key)
    return value if isinstance(value, str) and value != "" else None


def _error_class(status: int) -> builtins.type[ApiError]:
    mapping: dict[int, builtins.type[ApiError]] = {
        400: ValidationError,
        401: AuthenticationError,
        402: PaymentRequiredError,
        403: PermissionError,
        404: NotFoundError,
        409: ConflictError,
        429: RateLimitError,
    }
    if status in mapping:
        return mapping[status]
    if status >= 500:
        return ServerError
    if status >= 400:
        return InvalidRequestError
    return ApiError


def parse_error_body(body: str) -> dict[str, Any]:
    """Returns the ``error`` object of an error response body, or ``{}``."""
    if not body:
        return {}
    try:
        decoded = json.loads(body)
    except ValueError:
        return {}
    if isinstance(decoded, dict) and isinstance(decoded.get("error"), dict):
        return dict(decoded["error"])
    return {}


def error_from_response(status: int, headers: Mapping[str, str], body: str) -> ApiError:
    """Builds the typed exception for an HTTP error response."""
    error = parse_error_body(body)

    def text(key: str) -> str | None:
        value = error.get(key)
        if isinstance(value, str):
            return value or None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return None

    lower = {k.lower(): v for k, v in headers.items()}
    message = text("message")
    if message is None:
        snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", body)).strip()[:200]
        message = f"The Wthaiq API returned HTTP {status}" + (f": {snippet}" if snippet else ".")
    return _error_class(status)(
        message,
        status_code=status,
        type=text("type"),
        code=text("code"),
        param=text("param"),
        request_id=text("request_id") or lower.get("wthaiq-request-id"),
        error=error,
        raw_body=body,
        headers=lower,
    )

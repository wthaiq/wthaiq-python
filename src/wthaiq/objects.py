"""Response objects.

Every JSON object returned by the API becomes a :class:`WthaiqObject`: read-only attribute access
(``sr.status``), item access (``sr["status"]``), nested objects (``event.data.object.id``) and
:meth:`WthaiqObject.to_dict` for the decoded JSON. Typed subclasses are chosen from the JSON
``object`` field and document their fields for editors and type checkers. Fields the API adds later
stay readable as attributes, so new API fields never break existing code.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypeVar

__all__ = [
    "Account",
    "AuditEvent",
    "Balance",
    "BulkSend",
    "Certificate",
    "DeletedWebhookEndpoint",
    "Document",
    "Download",
    "Event",
    "EventRedelivery",
    "Evidence",
    "Flow",
    "IdentityVerification",
    "Money",
    "PdfFile",
    "RateLimit",
    "Reminder",
    "ResponseInfo",
    "SavedPdf",
    "Session",
    "SessionSigner",
    "SignatureRequest",
    "Signer",
    "SigningSession",
    "Template",
    "TemplateField",
    "Usage",
    "Verification",
    "WebhookDelivery",
    "WebhookEndpoint",
    "WebhookTestResult",
    "WthaiqObject",
    "convert",
]

T = TypeVar("T", bound="WthaiqObject")


@dataclass(frozen=True)
class RateLimit:
    """The ``X-RateLimit-*`` headers of a response."""

    limit: int
    remaining: int
    reset: int
    """Unix timestamp at which the window resets."""


@dataclass(frozen=True)
class ResponseInfo:
    """HTTP metadata of the call that produced an object (``obj.last_response``)."""

    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)
    """Response headers with lower-case names."""

    @property
    def request_id(self) -> str | None:
        """The ``Wthaiq-Request-Id`` header (``req_…``). Quote it to support."""
        return self.headers.get("wthaiq-request-id")

    @property
    def api_version(self) -> str | None:
        """The ``Wthaiq-Version`` header."""
        return self.headers.get("wthaiq-version")

    @property
    def idempotent_replayed(self) -> bool:
        """``True`` when the API replayed a stored response for the same ``Idempotency-Key``."""
        return self.headers.get("idempotent-replayed", "").strip().lower() == "true"

    @property
    def rate_limit(self) -> RateLimit | None:
        """The rate-limit window, when the headers are present."""
        values = [
            self.headers.get(f"x-ratelimit-{name}", "").strip()
            for name in ("limit", "remaining", "reset")
        ]
        if not all(value.isascii() and value.isdigit() for value in values):
            return None
        return RateLimit(int(values[0]), int(values[1]), int(values[2]))

    def get_header(self, name: str) -> str | None:
        """Returns a header (case-insensitive) or ``None``."""
        return self.headers.get(name.lower())


_REGISTRY: dict[str, type[WthaiqObject]] = {}
_FIELDS: dict[type[WthaiqObject], frozenset[str]] = {}


def _declared_fields(cls: type[WthaiqObject]) -> frozenset[str]:
    cached = _FIELDS.get(cls)
    if cached is not None:
        return cached
    names: set[str] = set()
    for klass in cls.__mro__:
        if klass is WthaiqObject or not issubclass(klass, WthaiqObject):
            continue
        for name, annotation in inspect.get_annotations(klass).items():
            if not name.startswith("_") and "ClassVar" not in str(annotation):
                names.add(name)
    result = frozenset(names)
    _FIELDS[cls] = result
    return result


def _register(name: str) -> Any:
    def decorator(cls: type[T]) -> type[T]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def convert(value: Any, cls: type[WthaiqObject] | None = None) -> Any:
    """Converts decoded JSON into response objects (dicts become objects, lists stay lists)."""
    if isinstance(value, list):
        return [convert(item, cls) for item in value]
    if isinstance(value, dict):
        target = cls
        if target is None:
            name = value.get("object")
            target = _REGISTRY.get(name, WthaiqObject) if isinstance(name, str) else WthaiqObject
        return target(value)
    return value


def _to_plain(value: Any) -> Any:
    if isinstance(value, WthaiqObject):
        return value.to_dict()
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value


def _restore(cls: type[WthaiqObject], values: dict[str, Any]) -> WthaiqObject:
    return cls(values)


def _mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (f"{item[:6]}…" if key == "secret" and isinstance(item, str) else _mask(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_mask(item) for item in value]
    return value


class WthaiqObject:
    """An immutable API object with attribute and item access."""

    __slots__ = ("_last_response", "_values")

    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {}

    def __init__(
        self, values: Mapping[str, Any] | None = None, *, last_response: ResponseInfo | None = None
    ) -> None:
        nested = type(self)._nested
        converted = {
            key: convert(item, nested.get(key)) for key, item in dict(values or {}).items()
        }
        object.__setattr__(self, "_values", converted)
        object.__setattr__(self, "_last_response", last_response)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        if name in values:
            return values[name]
        if name in _declared_fields(type(self)):
            return None
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"{type(self).__name__} objects are read-only.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"{type(self).__name__} objects are read-only.")

    def __getitem__(self, key: str) -> Any:
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        return values[key]

    def __contains__(self, key: object) -> bool:
        return key in object.__getattribute__(self, "_values")

    def get(self, key: str, default: Any = None) -> Any:
        """Returns the field ``key`` or ``default`` when it is absent."""
        return object.__getattribute__(self, "_values").get(key, default)

    def keys(self) -> Iterator[str]:
        """The field names present in the response."""
        return iter(object.__getattribute__(self, "_values"))

    def to_dict(self) -> dict[str, Any]:
        """Returns the object as plain JSON-compatible data."""
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        return {key: _to_plain(item) for key, item in values.items()}

    def to_json(self, *, indent: int | None = None) -> str:
        """Returns the object as a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @property
    def last_response(self) -> ResponseInfo | None:
        """HTTP metadata of the call that returned this object (top-level objects only)."""
        info: ResponseInfo | None = object.__getattribute__(self, "_last_response")
        return info

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WthaiqObject):
            return type(self) is type(other) and self.to_dict() == other.to_dict()
        if isinstance(other, Mapping):
            return self.to_dict() == dict(other)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __dir__(self) -> list[str]:
        return sorted(set(super().__dir__()) | set(object.__getattribute__(self, "_values")))

    def __reduce__(self) -> tuple[Any, ...]:
        return (_restore, (type(self), self.to_dict()))

    def __repr__(self) -> str:
        values: dict[str, Any] = object.__getattribute__(self, "_values")
        ident = values.get("id")
        head = (
            f"<{type(self).__name__}" + (f" id={ident!r}" if isinstance(ident, str) else "") + ">"
        )
        return f"{head} {json.dumps(_mask(self.to_dict()), ensure_ascii=False)}"

    def __str__(self) -> str:
        return json.dumps(_mask(self.to_dict()), ensure_ascii=False, indent=2)


# --- shared nested objects -------------------------------------------------------------------


class Money(WthaiqObject):
    """An amount of money: ``amount`` (decimal), ``amount_minor`` (piastres/cents), ``currency``."""

    __slots__ = ()
    amount: float
    amount_minor: int
    currency: str


class AccountInfo(WthaiqObject):
    __slots__ = ()
    id: str
    name: str
    email: str | None


class RootPlan(WthaiqObject):
    __slots__ = ()
    id: str
    paid: bool
    sends_left: int


class RootPricing(WthaiqObject):
    __slots__ = ()
    overage_per_request: float
    identity_per_signer: float
    currency: str


@_register("api_root")
class Account(WthaiqObject):
    """``GET /``: the account, plan and pricing of the API key."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        "account": AccountInfo,
        "plan": RootPlan,
        "pricing": RootPricing,
    }
    object: str
    name: str
    version: str
    livemode: bool
    base_url: str
    account: AccountInfo
    plan: RootPlan
    pricing: RootPricing
    docs: str


class UsagePlan(WthaiqObject):
    __slots__ = ()
    id: str
    name: str
    paid: bool
    period_start: int | None
    period_end: int | None
    sends_quota: int
    sends_used: int
    sends_left: int
    auto_renew: bool


class UsagePricing(WthaiqObject):
    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        "overage_per_request": Money,
        "identity_per_signer": Money,
        "min_topup": Money,
    }
    overage_per_request: Money
    identity_per_signer: Money
    min_topup: Money
    currency: str


class UsageCounts(WthaiqObject):
    __slots__ = ()
    total: int
    last_30_days: int
    completed: int


@_register("balance")
class Balance(WthaiqObject):
    """``GET /balance``: wallet balance and plan quota."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        "balance": Money,
        "month_spent": Money,
        "plan": UsagePlan,
    }
    object: str
    livemode: bool
    balance: Money
    month_spent: Money
    plan: UsagePlan


@_register("usage")
class Usage(Balance):
    """``GET /usage``: balance, plan quota, pricing and request counts."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        **Balance._nested,
        "pricing": UsagePricing,
        "signature_requests": UsageCounts,
    }
    pricing: UsagePricing
    signature_requests: UsageCounts


# --- templates -------------------------------------------------------------------------------


class TemplateField(WthaiqObject):
    """A placeholder field of a template."""

    __slots__ = ()
    key: str
    label: str
    type: str
    required: bool
    type_declared: bool | None
    vtype: str | None


@_register("template")
class Template(WthaiqObject):
    """A contract template."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {"fields": TemplateField}
    id: str
    object: str
    name: str
    category: str | None
    languages: list[str]
    fields: list[TemplateField]
    created_at: int
    content: str | None
    """Only with ``include="content"`` on your own templates."""


# --- signature requests ----------------------------------------------------------------------


class SignerIdentity(WthaiqObject):
    """Identity verification state of a signer."""

    __slots__ = ()
    status: str
    provider: str
    level: str
    verification_id: str | None
    reason_code: str | None
    updated_at: int | None
    resubmit_steps: list[str] | None


@_register("signer")
class Signer(WthaiqObject):
    """A signer of a signature request."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {"identity": SignerIdentity}
    id: str
    object: str
    name: str
    email: str | None
    phone: str | None
    type: str
    method: str
    require_identity: bool
    order: int
    status: str
    signing_url: str | None
    viewed_at: int | None
    signed_at: int | None
    fields: WthaiqObject
    identity: SignerIdentity | None
    signature_request: str | None
    """Only inside ``signer.*`` webhook payloads."""
    workflow_id: str | None
    workflow_version: int | None
    vendor_data: str | None


class Source(WthaiqObject):
    __slots__ = ()
    type: str
    template_id: str | None
    document_id: str | None


class Reminders(WthaiqObject):
    __slots__ = ()
    enabled: bool
    interval_hours: int | None
    max: int | None


class CcRecipient(WthaiqObject):
    __slots__ = ()
    name: str
    email: str


@_register("signature_request")
class SignatureRequest(WthaiqObject):
    """A signature request."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        "source": Source,
        "signers": Signer,
        "cc": CcRecipient,
        "reminders": Reminders,
    }
    id: str
    object: str
    livemode: bool
    status: str
    title: str
    legal_level: str
    format: str
    source: Source
    signers: list[Signer]
    ordered: bool
    require_identity: bool
    reference: str | None
    cc: list[CcRecipient]
    reminders: Reminders
    metadata: WthaiqObject
    expires_at: int | None
    completed_at: int | None
    download_url: str | None
    created_at: int
    workflow_id: str | None
    workflow_version: int | None
    vendor_data: str | None
    channel: str | None
    return_url: str | None
    trial: bool | None


class BulkSendResult(WthaiqObject):
    __slots__ = ()
    signature_request: str
    email: str | None
    phone: str | None
    status: str


class BulkSendError(WthaiqObject):
    __slots__ = ()
    email: str | None
    phone: str | None
    error: str
    code: str


@_register("bulk_send")
class BulkSend(WthaiqObject):
    """Result of ``POST /signature_requests/bulk``."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        "requests": BulkSendResult,
        "errors": BulkSendError,
    }
    object: str
    created: int
    failed: int
    requests: list[BulkSendResult]
    errors: list[BulkSendError]


@_register("reminder")
class Reminder(WthaiqObject):
    __slots__ = ()
    object: str
    signature_request: str
    reminders_sent: int


class AuditEvent(WthaiqObject):
    """An entry of ``GET /signature_requests/{id}/events``."""

    __slots__ = ()
    id: str
    object: str
    type: str
    actor: str
    ip: str | None
    signature_request: str
    created_at: int
    to: str | None
    description: str | None


class CertificateSigner(WthaiqObject):
    __slots__ = ()
    name: str
    email: str | None
    phone: str | None
    status: str
    signed_at: int | None


class AuditTrailEntry(WthaiqObject):
    __slots__ = ()
    event: str
    actor: str
    ip: str | None
    at: int


@_register("certificate")
class Certificate(WthaiqObject):
    """Completion certificate of a signature request."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        "signers": CertificateSigner,
        "audit_trail": AuditTrailEntry,
    }
    object: str
    signature_request: str
    status: str
    reference: str | None
    legal_level: str
    format: str
    completed_at: int | None
    signers: list[CertificateSigner]
    audit_trail: list[AuditTrailEntry]
    verify_url: str | None
    test: bool | None
    legal_effect: str | None
    watermark: str | None


@_register("download")
class Download(WthaiqObject):
    """Metadata of the final document of a completed request."""

    __slots__ = ()
    object: str
    signature_request: str
    pdf_url: str | None
    pdf_status: str
    pdf_sha256: str | None
    pdf_bytes: int | None
    pdf_generated_at: int | None
    final_document_url: str | None
    reference: str | None
    format: str
    legal_level: str
    test: bool | None
    legal_effect: str | None
    watermark: str | None


class EvidenceSeal(WthaiqObject):
    __slots__ = ()
    signature_alg: str
    signature: str
    public_key: str
    key_id: str
    trust_url: str
    timestamp_token: str
    timestamp_gentime: str


@_register("evidence")
class Evidence(WthaiqObject):
    """Sealed evidence record (live) or unsealed test record (test mode, ``seal`` is ``None``)."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {"seal": EvidenceSeal}
    object: str
    signature_request: str
    format: str
    issued_at: str
    verify_ref: str | None
    record: WthaiqObject
    record_raw: str | None
    seal: EvidenceSeal | None
    platform_verification: WthaiqObject | None
    how_to_verify: str | None
    livemode: bool | None
    test: bool | None
    legal_effect: str | None
    watermark: str | None
    notice: str | None


# --- sessions, signers, documents ------------------------------------------------------------


class SessionSigner(WthaiqObject):
    __slots__ = ()
    id: str
    name: str
    email: str | None
    phone: str | None
    status: str
    sign_url: str | None


class SessionCost(WthaiqObject):
    __slots__ = ()
    amount: float
    currency: str
    source: str | None


@_register("session")
class Session(WthaiqObject):
    """A signature request created from a workflow (``POST /sessions``)."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {
        "signers": SessionSigner,
        "cost": SessionCost,
    }
    id: str
    object: str
    status: str
    workflow_id: str
    workflow_version: int | None
    vendor_data: str | None
    channel: str
    signers: list[SessionSigner]
    sign_url: str | None
    """Only when the session has exactly one signer."""
    created_at: int
    expires_at: int | None
    livemode: bool
    cost: SessionCost
    return_url: str | None
    trial: bool | None


@_register("signing_session")
class SigningSession(WthaiqObject):
    """A short-lived embedded or redirect signing link (valid for 30 minutes)."""

    __slots__ = ()
    object: str
    signer: str
    mode: str
    signing_url: str
    expires_at: int
    success_url: str | None
    cancel_url: str | None


@_register("document")
class Document(WthaiqObject):
    """An uploaded PDF document."""

    __slots__ = ()
    id: str
    object: str
    kind: str
    filename: str
    pages: int
    bytes: int
    sha256: str
    fields: list[WthaiqObject]
    created_at: int


@_register("identity_verification")
class IdentityVerification(WthaiqObject):
    __slots__ = ()
    id: str
    object: str
    provider: str
    signer: str | None
    status: str
    level: str
    verification_url: str | None
    created_at: int


@_register("verification")
class Verification(WthaiqObject):
    """Result of a reference lookup. ``found`` is ``False`` when the reference is unknown."""

    __slots__ = ()
    object: str
    reference: str
    found: bool
    status: str
    integrity: str
    structure: str | None
    document: WthaiqObject | None
    signed_at: int | None
    parties: list[WthaiqObject] | None
    events: list[WthaiqObject] | None
    qr: str | None
    verify_url: str | None
    signature_request: str | None
    created_at: int | None


# --- webhooks and events ---------------------------------------------------------------------


@_register("webhook_endpoint")
class WebhookEndpoint(WthaiqObject):
    """A webhook endpoint. ``secret`` is only present in the create response."""

    __slots__ = ()
    id: str
    object: str
    url: str
    enabled_events: list[str]
    status: str
    livemode: bool
    created_at: int
    secret: str | None


class DeletedWebhookEndpoint(WthaiqObject):
    __slots__ = ()
    id: str
    object: str
    deleted: bool


@_register("webhook_delivery")
class WebhookDelivery(WthaiqObject):
    __slots__ = ()
    object: str
    event: str
    event_type: str
    status: str
    attempts: int
    response_code: int | None
    created_at: int
    updated_at: int | None


@_register("webhook_test")
class WebhookTestResult(WthaiqObject):
    __slots__ = ()
    object: str
    endpoint: str
    response_code: int | None
    error: str
    ok: bool


class EventData(WthaiqObject):
    __slots__ = ()
    object: Any
    """The event resource: :class:`SignatureRequest`, :class:`Signer` or :class:`Verification`."""


@_register("event")
class Event(WthaiqObject):
    """A webhook event (also returned by ``GET /events``)."""

    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {"data": EventData}
    id: str
    object: str
    type: str
    created_at: int
    livemode: bool
    data: EventData


class RedeliveryAttempt(WthaiqObject):
    __slots__ = ()
    endpoint: str
    status: str
    response_code: int | None
    error: str | None


@_register("event_redelivery")
class EventRedelivery(WthaiqObject):
    __slots__ = ()
    _nested: ClassVar[Mapping[str, type[WthaiqObject]]] = {"deliveries": RedeliveryAttempt}
    object: str
    event: str
    deliveries: list[RedeliveryAttempt]


@_register("flow")
class Flow(WthaiqObject):
    """An embeddable console flow (read-only)."""

    __slots__ = ()
    id: str
    object: str
    name: str
    template_id: str | None
    legal_level: str
    reminders: bool
    lock_contract: bool
    cc: list[Any]
    created_at: int


# --- downloads -------------------------------------------------------------------------------


class PdfFile(bytes):
    """The bytes of a downloaded PDF, with the HTTP details of the download."""

    sha256: str
    """SHA-256 of the bytes (checked against the ``X-File-Sha256`` header when sent)."""
    filename: str | None
    """File name from the ``Content-Disposition`` header."""
    last_response: ResponseInfo | None

    def __new__(
        cls,
        content: bytes,
        *,
        sha256: str,
        filename: str | None = None,
        last_response: ResponseInfo | None = None,
    ) -> PdfFile:
        instance = super().__new__(cls, content)
        instance.sha256 = sha256
        instance.filename = filename
        instance.last_response = last_response
        return instance

    def __reduce__(self) -> tuple[Any, ...]:
        return (bytes, (bytes(self),))


@dataclass(frozen=True)
class SavedPdf:
    """Result of ``download_pdf_to``."""

    path: str
    bytes: int
    sha256: str

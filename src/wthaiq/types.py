"""Typed parameters accepted by the resource methods.

Every method accepts its API parameters as keyword arguments (checked by type checkers through the
``TypedDict`` classes below) or as a positional ``dict``. The positional ``dict`` is never checked
and is the way to send parameters this version of the library does not know yet.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypedDict, Union

__all__ = [
    "EVENT_TYPES",
    "BulkCreateParams",
    "CcParams",
    "EventListParams",
    "EventRedeliverParams",
    "EventType",
    "IdentityMatchDecisionParams",
    "LegalLevel",
    "ListParams",
    "RemindersParams",
    "RequestOptions",
    "SessionCreateParams",
    "SessionListParams",
    "SessionSignerParams",
    "SignatureRequestCreateParams",
    "SignatureRequestListParams",
    "SignatureRequestStatus",
    "SignerParams",
    "SigningSessionCreateParams",
    "SourceParams",
    "TemplateCreateParams",
    "TemplateFieldParams",
    "TemplateListParams",
    "TemplateRetrieveParams",
    "WebhookEndpointCreateParams",
    "WebhookEndpointListParams",
    "WebhookEndpointUpdateParams",
]

EventType = Literal[
    "signature_request.created",
    "signature_request.sent",
    "signature_request.viewed",
    "signature_request.partially_signed",
    "signature_request.completed",
    "signature_request.declined",
    "signature_request.expired",
    "signature_request.canceled",
    "signer.sent",
    "signer.viewed",
    "signer.otp_verified",
    "signer.identity_verified",
    "signer.identity_in_review",
    "signer.identity_resubmission_requested",
    "signer.identity_declined",
    "signer.identity_match_hold",
    "signer.identity_match_decided",
    "signer.signed",
    "signer.declined",
    "document.sealed",
    "verification.created",
]

EVENT_TYPES: tuple[str, ...] = (
    "signature_request.created",
    "signature_request.sent",
    "signature_request.viewed",
    "signature_request.partially_signed",
    "signature_request.completed",
    "signature_request.declined",
    "signature_request.expired",
    "signature_request.canceled",
    "signer.sent",
    "signer.viewed",
    "signer.otp_verified",
    "signer.identity_verified",
    "signer.identity_in_review",
    "signer.identity_resubmission_requested",
    "signer.identity_declined",
    "signer.identity_match_hold",
    "signer.identity_match_decided",
    "signer.signed",
    "signer.declined",
    "document.sealed",
    "verification.created",
)
"""Every webhook event type known to this version of the library."""

LegalLevel = Literal["ses", "aes", "qes"]
PdfFormat = Literal["pades-b", "pades-t", "pades-lt", "pades-lta"]
SignatureRequestStatus = Literal[
    "draft", "sent", "partially_signed", "completed", "declined", "expired", "canceled"
]
Timestamp = Union[int, str, _dt.datetime, _dt.date]


class RequestOptions(TypedDict, total=False):
    """Options accepted by every method, next to its API parameters."""

    idempotency_key: str
    """Idempotency key for ``POST`` requests. A random UUID is used when omitted."""
    timeout: float
    """Seconds allowed for each attempt. Overrides the client ``timeout``."""
    max_retries: int
    """Automatic retries for this call. Overrides the client ``max_retries``."""
    headers: Mapping[str, str]
    """Extra request headers. ``Authorization`` is refused: use ``api_key``."""
    api_key: str
    """Use another API key for this call only."""


class ListParams(TypedDict, total=False):
    limit: int
    """1 to 100, default 20."""
    starting_after: str
    """The ``next_cursor`` of the previous page."""


class SourceParams(TypedDict, total=False):
    type: Literal["template", "document"]
    template_id: str
    document_id: str


class SignerParams(TypedDict, total=False):
    name: str
    email: str
    phone: str
    """WhatsApp number in international format, e.g. ``201012345678``."""
    type: Literal["individual", "company"]
    method: Literal["draw", "token"]
    require_identity: bool
    fields: Mapping[str, Any]


class CcParams(TypedDict, total=False):
    name: str
    email: str


class RemindersParams(TypedDict, total=False):
    enabled: bool
    interval_hours: int
    max: int


class _SignatureRequestBase(TypedDict, total=False):
    source: SourceParams
    title: str
    legal_level: LegalLevel
    require_identity: bool
    format: PdfFormat
    ordered: bool
    send: bool
    """``False`` creates a draft; send it later with ``signature_requests.send(id)``."""
    fields: Mapping[str, Any]
    cc: Sequence[CcParams | str]
    reminders: RemindersParams | bool
    metadata: Mapping[str, Any]


class SignatureRequestCreateParams(_SignatureRequestBase, total=False):
    signers: Sequence[SignerParams]


class BulkCreateParams(_SignatureRequestBase, total=False):
    recipients: Sequence[SignerParams]
    """One signature request is created per recipient (1 to 200)."""


class SignatureRequestListParams(ListParams, total=False):
    status: SignatureRequestStatus
    created_after: Timestamp
    created_before: Timestamp


class TemplateListParams(ListParams, total=False):
    scope: Literal["mine", "own"]
    """``mine`` lists your own templates; otherwise the public catalogue is listed."""
    owner: Literal["me"]
    search: str


class TemplateRetrieveParams(TypedDict, total=False):
    include: Literal["content"]
    scope: Literal["mine", "own"]


class TemplateFieldParams(TypedDict, total=False):
    key: str
    label: str
    type: Literal["text", "number", "date", "email", "tel", "signature"]
    required: bool


class TemplateCreateParams(TypedDict, total=False):
    name: str
    content: str
    """HTML with ``{{key}}`` placeholders."""
    fields: Sequence[TemplateFieldParams]


class SessionSignerParams(TypedDict, total=False):
    name: str
    email: str
    phone: str
    type: Literal["individual", "company"]
    fields: Mapping[str, Any]
    access_code: str


class SessionCreateParams(TypedDict, total=False):
    workflow_id: str
    """``wf_…`` of a published workflow, or ``default``."""
    template_id: str | int
    document_id: str
    signers: Sequence[SessionSignerParams]
    signature_method: Literal["simple", "identity", "token"]
    channel: Literal["email", "whatsapp", "link"]
    language: Literal["ar", "en"]
    expires_in: int
    """Days, 1 to 30."""
    require_id_attachment: bool
    cc: Sequence[CcParams | str]
    return_url: str
    vendor_data: str | int
    title: str
    fields: Mapping[str, Any]
    metadata: Mapping[str, Any]


class SessionListParams(ListParams, total=False):
    workflow_id: str
    vendor_data: str
    status: SignatureRequestStatus


class SigningSessionCreateParams(TypedDict, total=False):
    mode: Literal["iframe", "redirect"]
    return_url: str
    success_url: str
    cancel_url: str


class IdentityMatchDecisionParams(TypedDict, total=False):
    decision: Literal["approve", "reject"]
    """Required. ``approve`` lets the signer finish signing; ``reject`` stops this signer."""
    note: str
    """Optional internal note stored with the decision (up to 200 characters)."""


class WebhookEndpointCreateParams(TypedDict, total=False):
    url: str
    enabled_events: Sequence[EventType | Literal["*"]]


class WebhookEndpointUpdateParams(TypedDict, total=False):
    enabled_events: Sequence[EventType | Literal["*"]]
    status: Literal["enabled", "disabled"]


class WebhookEndpointListParams(ListParams, total=False): ...


class EventListParams(ListParams, total=False):
    type: EventType


class EventRedeliverParams(TypedDict, total=False):
    endpoint: str
    """Only this endpoint (``we_…``); default: every enabled endpoint subscribed to the type."""


# Keyword-argument types: API parameters plus request options.


class SignatureRequestCreateKwargs(SignatureRequestCreateParams, RequestOptions, total=False): ...


class BulkCreateKwargs(BulkCreateParams, RequestOptions, total=False): ...


class SignatureRequestListKwargs(SignatureRequestListParams, RequestOptions, total=False): ...


class TemplateListKwargs(TemplateListParams, RequestOptions, total=False): ...


class TemplateRetrieveKwargs(TemplateRetrieveParams, RequestOptions, total=False): ...


class TemplateCreateKwargs(TemplateCreateParams, RequestOptions, total=False): ...


class SessionCreateKwargs(SessionCreateParams, RequestOptions, total=False): ...


class SessionListKwargs(SessionListParams, RequestOptions, total=False): ...


class SigningSessionCreateKwargs(SigningSessionCreateParams, RequestOptions, total=False): ...


class IdentityMatchDecisionKwargs(IdentityMatchDecisionParams, RequestOptions, total=False): ...


class WebhookEndpointCreateKwargs(WebhookEndpointCreateParams, RequestOptions, total=False): ...


class WebhookEndpointUpdateKwargs(WebhookEndpointUpdateParams, RequestOptions, total=False): ...


class WebhookEndpointListKwargs(WebhookEndpointListParams, RequestOptions, total=False): ...


class EventListKwargs(EventListParams, RequestOptions, total=False): ...


class EventRedeliverKwargs(EventRedeliverParams, RequestOptions, total=False): ...


class ListKwargs(ListParams, RequestOptions, total=False): ...

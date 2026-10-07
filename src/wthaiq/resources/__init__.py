"""Resource services, reached as attributes of :class:`~wthaiq.Client` / ``AsyncClient``."""

from .account import (
    AccountResource,
    AsyncAccountResource,
    AsyncBalanceResource,
    AsyncUsageResource,
    BalanceResource,
    UsageResource,
)
from .documents import (
    AsyncDocuments,
    AsyncIdentityVerifications,
    AsyncVerifications,
    Documents,
    IdentityVerifications,
    Verifications,
)
from .sessions import AsyncSessions, AsyncSigners, Sessions, Signers
from .signature_requests import AsyncSignatureRequests, SignatureRequests
from .templates import AsyncTemplates, Templates
from .webhooks import (
    AsyncEvents,
    AsyncFlows,
    AsyncWebhookEndpoints,
    Events,
    Flows,
    WebhookEndpoints,
)

__all__ = [
    "AccountResource",
    "AsyncAccountResource",
    "AsyncBalanceResource",
    "AsyncDocuments",
    "AsyncEvents",
    "AsyncFlows",
    "AsyncIdentityVerifications",
    "AsyncSessions",
    "AsyncSignatureRequests",
    "AsyncSigners",
    "AsyncTemplates",
    "AsyncUsageResource",
    "AsyncVerifications",
    "AsyncWebhookEndpoints",
    "BalanceResource",
    "Documents",
    "Events",
    "Flows",
    "IdentityVerifications",
    "Sessions",
    "SignatureRequests",
    "Signers",
    "Templates",
    "UsageResource",
    "Verifications",
    "WebhookEndpoints",
]

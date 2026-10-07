from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

import wthaiq
from wthaiq import objects

from .conftest import (
    SIGNATURE_REQUEST,
    AsyncFakeTransport,
    FakeTransport,
    body_of,
    error,
    make_async_client,
    make_client,
    path_of,
    query_of,
    response,
)

SIGNER = SIGNATURE_REQUEST["signers"][0]  # type: ignore[index]
SESSION = {
    "id": "sr_4f375a20cb1a4dda8f0f",
    "object": "session",
    "status": "sent",
    "workflow_id": "default",
    "channel": "link",
    "signers": [
        {"id": "sgr_1", "name": "Noha", "status": "sent", "sign_url": "https://x/s?token=1"}
    ],
    "sign_url": "https://x/s?token=1",
    "cost": {"amount": 0, "currency": "EGP", "source": None},
}
TEMPLATE = {
    "id": "tpl_998488",
    "object": "template",
    "name": "Service agreement",
    "languages": ["ar"],
    "fields": [{"key": "amount", "label": "Amount", "type": "number", "required": True}],
    "created_at": 1791353268,
}
ENDPOINT = {
    "id": "we_1",
    "object": "webhook_endpoint",
    "url": "https://example.com/hooks",
    "enabled_events": ["*"],
    "status": "enabled",
    "livemode": False,
    "created_at": 1,
}
EVENT = {
    "id": "evt_1",
    "object": "event",
    "type": "signature_request.completed",
    "created_at": 1,
    "livemode": False,
    "data": {"object": SIGNATURE_REQUEST},
}


def lst(*items: dict[str, Any]) -> dict[str, Any]:
    return {"object": "list", "data": list(items), "has_more": False, "next_cursor": None}


@dataclass
class Case:
    name: str
    call: Callable[[Any], Any]
    method: str
    path: str
    body: Any = None
    query: list[tuple[str, str]] = field(default_factory=list)
    reply: dict[str, Any] = field(default_factory=dict)
    status: int = 200
    result: type | None = None


CASES = [
    Case("account", lambda c: c.account.retrieve(), "GET", "/",
         reply={"object": "api_root", "account": {"id": "acct_1", "name": "Delta"},
                "plan": {"id": "ap_trial", "paid": False, "sends_left": 0}},
         result=objects.Account),
    Case("usage", lambda c: c.usage.retrieve(), "GET", "/usage",
         reply={"object": "usage", "balance": {"amount": 1.5, "amount_minor": 150, "currency": "EGP"},
                "pricing": {"min_topup": {"amount": 4700, "amount_minor": 470000, "currency": "EGP"}},
                "signature_requests": {"total": 3}},
         result=objects.Usage),
    Case("balance", lambda c: c.balance.retrieve(), "GET", "/balance",
         reply={"object": "balance", "balance": {"amount": 0, "amount_minor": 0, "currency": "USD"}},
         result=objects.Balance),
    Case("templates.list", lambda c: c.templates.list(scope="mine", search="عقد", limit=2),
         "GET", "/templates", query=[("scope", "mine"), ("search", "عقد"), ("limit", "2")],
         reply=lst(TEMPLATE), result=wthaiq.Page),
    Case("templates.retrieve", lambda c: c.templates.retrieve("tpl_998488", include="content"),
         "GET", "/templates/tpl_998488", query=[("include", "content")], reply=TEMPLATE,
         result=objects.Template),
    Case("templates.create",
         lambda c: c.templates.create(name="NDA", content="<p>{{name}}</p>",
                                      fields=[{"key": "name", "type": "text"}]),
         "POST", "/templates", status=201,
         body={"name": "NDA", "content": "<p>{{name}}</p>", "fields": [{"key": "name", "type": "text"}]},
         reply=TEMPLATE, result=objects.Template),
    Case("signature_requests.create",
         lambda c: c.signature_requests.create(
             source={"type": "template", "template_id": "tpl_1"},
             signers=[{"name": "Noha", "email": "noha@example.com", "require_identity": True}],
             send=False),
         "POST", "/signature_requests", status=201,
         body={"source": {"type": "template", "template_id": "tpl_1"},
               "signers": [{"name": "Noha", "email": "noha@example.com", "require_identity": True}],
               "send": False},
         reply=SIGNATURE_REQUEST, result=objects.SignatureRequest),
    Case("signature_requests.create_bulk",
         lambda c: c.signature_requests.create_bulk(
             source={"type": "template", "template_id": "tpl_1"},
             recipients=[{"name": "A", "email": "a@x.com"}]),
         "POST", "/signature_requests/bulk", status=201,
         body={"source": {"type": "template", "template_id": "tpl_1"},
               "recipients": [{"name": "A", "email": "a@x.com"}]},
         reply={"object": "bulk_send", "created": 1, "failed": 0,
                "requests": [{"signature_request": "sr_1", "email": "a@x.com", "status": "sent"}],
                "errors": []},
         result=objects.BulkSend),
    Case("signature_requests.list", lambda c: c.signature_requests.list(status="draft"),
         "GET", "/signature_requests", query=[("status", "draft")], reply=lst(SIGNATURE_REQUEST),
         result=wthaiq.Page),
    Case("signature_requests.retrieve", lambda c: c.signature_requests.retrieve("sr_1"),
         "GET", "/signature_requests/sr_1", reply=SIGNATURE_REQUEST, result=objects.SignatureRequest),
    Case("signature_requests.send", lambda c: c.signature_requests.send("sr_1"),
         "POST", "/signature_requests/sr_1/send", body={}, reply=SIGNATURE_REQUEST,
         result=objects.SignatureRequest),
    Case("signature_requests.remind", lambda c: c.signature_requests.remind("sr_1"),
         "POST", "/signature_requests/sr_1/reminders", body={},
         reply={"object": "reminder", "signature_request": "sr_1", "reminders_sent": 1},
         result=objects.Reminder),
    Case("signature_requests.cancel", lambda c: c.signature_requests.cancel("sr_1"),
         "POST", "/signature_requests/sr_1/cancel", body={},
         reply={**SIGNATURE_REQUEST, "status": "canceled"}, result=objects.SignatureRequest),
    Case("signature_requests.list_events", lambda c: c.signature_requests.list_events("sr_1"),
         "GET", "/signature_requests/sr_1/events",
         reply=lst({"id": "evt_13249", "object": "event", "type": "audit.created", "actor": "owner"}),
         result=wthaiq.Page),
    Case("signature_requests.certificate", lambda c: c.signature_requests.certificate("sr_1"),
         "GET", "/signature_requests/sr_1/certificate",
         reply={"object": "certificate", "signers": [{"name": "N", "status": "signed"}],
                "audit_trail": [{"event": "created", "at": 1}], "test": True},
         result=objects.Certificate),
    Case("signature_requests.download", lambda c: c.signature_requests.download("sr_1"),
         "GET", "/signature_requests/sr_1/download",
         reply={"object": "download", "pdf_status": "ready", "pdf_sha256": "ab"},
         result=objects.Download),
    Case("signature_requests.evidence", lambda c: c.signature_requests.evidence("sr_1"),
         "GET", "/signature_requests/sr_1/evidence",
         reply={"object": "evidence", "format": "wthaiq-evidence-test-v1", "seal": None,
                "record": {"title": "x"}},
         result=objects.Evidence),
    Case("sessions.create",
         lambda c: c.sessions.create(workflow_id="default", template_id="tpl_1", channel="link",
                                     signers=[{"name": "Noha", "email": "n@x.com"}],
                                     vendor_data="user-42"),
         "POST", "/sessions", status=201,
         body={"workflow_id": "default", "template_id": "tpl_1", "channel": "link",
               "signers": [{"name": "Noha", "email": "n@x.com"}], "vendor_data": "user-42"},
         reply=SESSION, result=objects.Session),
    Case("sessions.list", lambda c: c.sessions.list(vendor_data="user-42", workflow_id="default"),
         "GET", "/sessions", query=[("vendor_data", "user-42"), ("workflow_id", "default")],
         reply=lst(SESSION), result=wthaiq.Page),
    Case("sessions.retrieve", lambda c: c.sessions.retrieve("sr_4f"), "GET", "/sessions/sr_4f",
         reply=SESSION, result=objects.Session),
    Case("signers.retrieve", lambda c: c.signers.retrieve("sgr_1"), "GET", "/signers/sgr_1",
         reply=SIGNER, result=objects.Signer),
    Case("signers.create_signing_session",
         lambda c: c.signers.create_signing_session("sgr_1", mode="redirect",
                                                    success_url="https://acme.example/done"),
         "POST", "/signers/sgr_1/signing_session", status=201,
         body={"mode": "redirect", "success_url": "https://acme.example/done"},
         reply={"object": "signing_session", "signer": "sgr_1", "mode": "redirect",
                "signing_url": "https://wthaiq.com/embed/sign/x", "expires_at": 2},
         result=objects.SigningSession),
    Case("signers.create_signing_session (no params)",
         lambda c: c.signers.create_signing_session("sgr_1"),
         "POST", "/signers/sgr_1/signing_session", body={},
         reply={"object": "signing_session", "mode": "iframe"}, result=objects.SigningSession),
    Case("documents.retrieve", lambda c: c.documents.retrieve("doc_1"), "GET", "/documents/doc_1",
         reply={"id": "doc_1", "object": "document", "pages": 3}, result=objects.Document),
    Case("identity_verifications.retrieve", lambda c: c.identity_verifications.retrieve("idv_12"),
         "GET", "/identity_verifications/idv_12",
         reply={"id": "idv_12", "object": "identity_verification", "status": "approved"},
         result=objects.IdentityVerification),
    Case("verifications.retrieve", lambda c: c.verifications.retrieve("WTQ-1A2B"),
         "GET", "/verifications/WTQ-1A2B",
         reply={"object": "verification", "reference": "WTQ-1A2B", "found": True,
                "integrity": "intact"},
         result=objects.Verification),
    Case("webhook_endpoints.create",
         lambda c: c.webhook_endpoints.create(url="https://example.com/hooks",
                                              enabled_events=["signature_request.completed"]),
         "POST", "/webhook_endpoints", status=201,
         body={"url": "https://example.com/hooks", "enabled_events": ["signature_request.completed"]},
         reply={**ENDPOINT, "secret": "whsec_" + "1" * 48}, result=objects.WebhookEndpoint),
    Case("webhook_endpoints.retrieve", lambda c: c.webhook_endpoints.retrieve("we_1"),
         "GET", "/webhook_endpoints/we_1", reply=ENDPOINT, result=objects.WebhookEndpoint),
    Case("webhook_endpoints.update",
         lambda c: c.webhook_endpoints.update("we_1", status="disabled"),
         "POST", "/webhook_endpoints/we_1", body={"status": "disabled"},
         reply={**ENDPOINT, "status": "disabled"}, result=objects.WebhookEndpoint),
    Case("webhook_endpoints.delete", lambda c: c.webhook_endpoints.delete("we_1"),
         "DELETE", "/webhook_endpoints/we_1",
         reply={"id": "we_1", "object": "webhook_endpoint", "deleted": True},
         result=objects.DeletedWebhookEndpoint),
    Case("webhook_endpoints.list", lambda c: c.webhook_endpoints.list(limit=10),
         "GET", "/webhook_endpoints", query=[("limit", "10")], reply=lst(ENDPOINT),
         result=wthaiq.Page),
    Case("webhook_endpoints.deliveries", lambda c: c.webhook_endpoints.deliveries("we_1"),
         "GET", "/webhook_endpoints/we_1/deliveries",
         reply=lst({"object": "webhook_delivery", "event": "evt_1", "status": "succeeded"}),
         result=wthaiq.Page),
    Case("webhook_endpoints.test", lambda c: c.webhook_endpoints.test("we_1"),
         "POST", "/webhook_endpoints/we_1/test", body={},
         reply={"object": "webhook_test", "endpoint": "we_1", "response_code": 200, "ok": True},
         result=objects.WebhookTestResult),
    Case("webhook_endpoints.event_types", lambda c: c.webhook_endpoints.event_types(),
         "GET", "/webhook_endpoints/event_types",
         reply={"object": "list", "data": ["signature_request.created", 5, "signer.signed"]},
         result=list),
    Case("events.list", lambda c: c.events.list(type="signer.signed"), "GET", "/events",
         query=[("type", "signer.signed")], reply=lst(EVENT), result=wthaiq.Page),
    Case("events.retrieve", lambda c: c.events.retrieve("evt_1"), "GET", "/events/evt_1",
         reply=EVENT, result=objects.Event),
    Case("events.redeliver", lambda c: c.events.redeliver("evt_1", endpoint="we_1"),
         "POST", "/events/evt_1/redeliver", body={"endpoint": "we_1"},
         reply={"object": "event_redelivery", "event": "evt_1",
                "deliveries": [{"endpoint": "we_1", "status": "succeeded", "response_code": 200}]},
         result=objects.EventRedelivery),
    Case("flows.list", lambda c: c.flows.list(), "GET", "/flows",
         reply=lst({"id": "flow_1", "object": "flow", "name": "Onboarding"}), result=wthaiq.Page),
    Case("flows.retrieve", lambda c: c.flows.retrieve("flow_1"), "GET", "/flows/flow_1",
         reply={"id": "flow_1", "object": "flow", "name": "Onboarding"}, result=objects.Flow),
]  # fmt: skip


def check(case: Case, transport: FakeTransport, result: Any) -> None:
    request = transport.last
    assert request.method == case.method
    assert path_of(request) == case.path
    assert query_of(request) == case.query
    if case.body is None:
        assert request.body is None
        assert "Idempotency-Key" not in request.headers
    else:
        assert body_of(request) == case.body
        assert request.headers["Idempotency-Key"]
    if case.result is wthaiq.Page:
        assert isinstance(result, (wthaiq.Page, wthaiq.AsyncPage))
    elif case.result is not None:
        assert type(result) is case.result
    if isinstance(result, objects.WthaiqObject):
        assert result.last_response is not None
        assert result.last_response.status_code == case.status


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_sync_resource(case: Case) -> None:
    transport = FakeTransport(response(case.status, case.reply))
    result = case.call(make_client(transport))
    check(case, transport, result)


@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_async_resource(case: Case) -> None:
    transport = AsyncFakeTransport(response(case.status, case.reply))

    async def run() -> Any:
        pending = case.call(make_async_client(transport))
        assert inspect.isawaitable(pending)
        return await pending

    check(case, transport, asyncio.run(run()))


def test_every_public_method_is_covered() -> None:
    client = make_client(FakeTransport())
    covered = {case.name.split(" ")[0] for case in CASES}
    extra = {"templates.all", "signature_requests.all", "sessions.all", "webhook_endpoints.all",
             "events.all", "flows.all", "signature_requests.download_pdf",
             "signature_requests.download_pdf_to", "documents.create"}  # fmt: skip
    for name in vars(client):
        if name.startswith("_"):
            continue
        resource = getattr(client, name)
        for attr in dir(resource):
            if not attr.startswith("_") and callable(getattr(resource, attr)):
                key = f"{name}.{attr}" if name not in {"account", "usage", "balance"} else name
                assert key in covered | extra, f"{key} has no unit test"


def test_sync_and_async_surfaces_match() -> None:
    sync_client = make_client(FakeTransport())
    async_client = make_async_client(AsyncFakeTransport())
    for name, resource in vars(sync_client).items():
        if name.startswith("_"):
            continue
        twin = getattr(async_client, name)
        public = {a for a in dir(resource) if not a.startswith("_")}
        assert public == {a for a in dir(twin) if not a.startswith("_")}, name
        for attr in public:
            sync_sig = inspect.signature(getattr(resource, attr))
            async_sig = inspect.signature(getattr(twin, attr))
            assert list(sync_sig.parameters) == list(async_sig.parameters), f"{name}.{attr}"


def test_typed_hydration() -> None:
    transport = FakeTransport(response(200, SIGNATURE_REQUEST))
    sr = make_client(transport).signature_requests.retrieve("sr_1")
    assert isinstance(sr.signers[0], objects.Signer)
    assert sr.signers[0].fields["amount"] == "100"
    assert isinstance(sr.source, objects.Source)
    assert sr.source.template_id == "tpl_998488"
    assert sr.reminders.interval_hours == 48
    assert sr.cc[0].email == "legal@example.com"
    assert sr.metadata.order == "A1"
    assert sr.workflow_id is None, "documented but absent fields read as None"

    usage = make_client(FakeTransport(response(200, CASES[1].reply))).usage.retrieve()
    assert isinstance(usage.balance, objects.Money)
    assert usage.balance.amount_minor == 150
    assert usage.pricing.min_topup.amount_minor == 470000
    assert usage.signature_requests.total == 3

    session = make_client(FakeTransport(response(200, SESSION))).sessions.retrieve("sr_1")
    assert isinstance(session.signers[0], objects.SessionSigner)
    assert session.cost.currency == "EGP"

    events = make_client(FakeTransport(response(200, CASES[13].reply)))
    audit = events.signature_requests.list_events("sr_1")
    assert isinstance(audit.data[0], objects.AuditEvent)

    event = make_client(FakeTransport(response(200, EVENT))).events.retrieve("evt_1")
    assert isinstance(event.data.object, objects.SignatureRequest)
    assert event.data.object.signers[0].name == "Noha"


def test_event_types_filters_non_strings() -> None:
    transport = FakeTransport(response(200, CASES[-6].reply))
    assert make_client(transport).webhook_endpoints.event_types() == [
        "signature_request.created",
        "signer.signed",
    ]
    bad = make_client(FakeTransport(response(200, {"object": "list"})))
    with pytest.raises(wthaiq.UnexpectedResponseError):
        bad.webhook_endpoints.event_types()


def test_verification_not_found_is_a_result() -> None:
    body = {
        "object": "verification",
        "reference": "WTQ-NOPE",
        "found": False,
        "status": "not_found",
        "integrity": "unknown",
    }
    transport = FakeTransport(response(404, body))
    result = make_client(transport).verifications.retrieve("WTQ-NOPE")
    assert isinstance(result, objects.Verification)
    assert result.found is False
    assert result.status == "not_found"
    assert result.last_response is not None and result.last_response.status_code == 404
    assert len(transport.requests) == 1

    async def run() -> objects.Verification:
        return await make_async_client(
            AsyncFakeTransport(response(404, body))
        ).verifications.retrieve("WTQ-NOPE")

    assert asyncio.run(run()).found is False


def test_verification_real_404_still_raises() -> None:
    client = make_client(FakeTransport(error(404, "resource_missing")))
    with pytest.raises(wthaiq.NotFoundError):
        client.verifications.retrieve("WTQ-1")
    client = make_client(FakeTransport(response(404, raw=b"<html>404</html>")))
    with pytest.raises(wthaiq.NotFoundError):
        client.verifications.retrieve("WTQ-1")

    async def run() -> None:
        async_client = make_async_client(AsyncFakeTransport(error(404, "resource_missing")))
        await async_client.verifications.retrieve("WTQ-1")

    with pytest.raises(wthaiq.NotFoundError):
        asyncio.run(run())

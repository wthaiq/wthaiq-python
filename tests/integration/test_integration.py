"""Integration suite: runs against a real Wthaiq API with a TEST secret key only.

    WTHAIQ_API_KEY=sk_test_... WTHAIQ_API_BASE=https://wthaiq.com/api/v1 pytest -m integration

Optional: ``WTHAIQ_API_KEY_READONLY`` (a read-only test key), ``WTHAIQ_TEST_SIGNER_EMAIL`` (defaults to
the account email; test mode only accepts the account's own addresses), ``WTHAIQ_TEST_WEBHOOK_URL``.
Everything created is canceled or deleted at the end (the API has no template delete, so one template
named ``SDK integration (wthaiq-python)`` is reused across runs). Test mode sends no real messages.
Each run creates three test signature requests (draft, bulk draft, session).
"""

from __future__ import annotations

import asyncio
import itertools
import os
import re
import secrets
import time
from collections.abc import Iterator

import pytest

import wthaiq
from wthaiq import (
    AuthenticationError,
    ConflictError,
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from wthaiq.types import SourceParams

API_KEY = os.environ.get("WTHAIQ_API_KEY", "")
BASE_URL = os.environ.get("WTHAIQ_API_BASE", "")
TEMPLATE_NAME = "SDK integration (wthaiq-python)"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (API_KEY and BASE_URL), reason="set WTHAIQ_API_KEY (sk_test_...) and WTHAIQ_API_BASE"
    ),
]

if API_KEY and not API_KEY.startswith("sk_test_"):
    raise RuntimeError("The integration suite only runs with a test secret key (sk_test_...).")


class State:
    client: wthaiq.Client
    signer_email: str
    template: wthaiq.Template
    to_cancel: set[str]
    to_delete: set[str]


@pytest.fixture(scope="module")
def state() -> Iterator[State]:
    st = State()
    st.client = wthaiq.Client(
        API_KEY, base_url=BASE_URL, max_retries=1, app_info={"name": "wthaiq-python-integration"}
    )
    st.to_cancel = set()
    st.to_delete = set()
    account = st.client.account.retrieve()
    st.signer_email = os.environ.get("WTHAIQ_TEST_SIGNER_EMAIL") or account.account.email or ""
    assert st.signer_email, "the account email is needed as the test signer"
    yield st
    for request_id in st.to_cancel:
        try:
            st.client.signature_requests.cancel(request_id)
        except ConflictError:
            pass
    for endpoint_id in st.to_delete:
        try:
            st.client.webhook_endpoints.delete(endpoint_id)
        except NotFoundError:
            pass
    st.client.close()


def test_account_usage_balance(state: State) -> None:
    root = state.client.account.retrieve()
    assert root.object == "api_root"
    assert root.livemode is False
    assert root.version == wthaiq.API_VERSION
    assert re.fullmatch(r"acct_\d+", root.account.id)
    info = root.last_response
    assert info is not None
    assert info.status_code == 200
    assert info.api_version == wthaiq.API_VERSION
    assert re.fullmatch(r"req_[0-9a-f]{18}", info.request_id or "")
    assert info.rate_limit is not None, "rate limit headers are sent"
    usage = state.client.usage.retrieve()
    assert usage.object == "usage"
    assert usage.balance.currency in ("EGP", "USD")
    assert isinstance(usage.signature_requests.total, int)
    assert isinstance(usage.pricing.min_topup.amount_minor, int)
    balance = state.client.balance.retrieve()
    assert balance.object == "balance"
    assert isinstance(balance.balance.amount_minor, int)


def test_template(state: State) -> None:
    client = state.client
    found = next(
        (
            item
            for item in client.templates.all(scope="mine", search=TEMPLATE_NAME, limit=100)
            if item.name == TEMPLATE_NAME
        ),
        None,
    )
    if found is None:
        found = client.templates.create(
            name=TEMPLATE_NAME,
            content="<p>أقرّ أنا {{signer_name}} بقبول مبلغ {{amount}}.</p>",
            fields=[{"key": "amount", "label": "Amount", "type": "number", "required": True}],
        )
        assert found.last_response is not None and found.last_response.status_code == 201
    state.template = found
    assert re.fullmatch(r"tpl_\d+", found.id)
    with_content = client.templates.retrieve(found.id, include="content")
    assert with_content.id == found.id
    assert "{{amount}}" in (with_content.content or "")
    assert any(field.key == "amount" for field in with_content.fields)
    mine = client.templates.list(scope="mine", limit=100)
    assert any(item.id == found.id for item in mine)
    assert len(client.templates.list(limit=2)) <= 2


def test_draft_lifecycle(state: State) -> None:
    client = state.client
    params = {
        "title": "SDK integration draft (python)",
        "source": {"type": "template", "template_id": state.template.id},
        "signers": [
            {"name": "SDK Signer", "email": state.signer_email, "fields": {"amount": "100"}}
        ],
        "metadata": {"suite": "wthaiq-python", "path": "/a/b"},
        "reminders": {"enabled": True, "interval_hours": 48, "max": 3},
        "send": False,
    }
    key = f"sdk-python-it-{secrets.token_hex(8)}"
    draft = client.signature_requests.create(params, idempotency_key=key)
    state.to_cancel.add(draft.id)
    assert re.fullmatch(r"sr_[0-9a-f]{20}", draft.id)
    assert draft.status == "draft"
    assert draft.livemode is False
    assert isinstance(draft.signers[0], wthaiq.Signer)
    assert draft.signers[0].signing_url is None, "draft links stay hidden until sent"
    assert draft.metadata.path == "/a/b"
    assert draft.last_response is not None
    assert draft.last_response.idempotent_replayed is False

    replay = client.signature_requests.create(params, idempotency_key=key)
    assert replay.id == draft.id
    assert replay.last_response is not None and replay.last_response.idempotent_replayed is True
    with pytest.raises(ConflictError) as conflict:
        client.signature_requests.create({**params, "title": "changed"}, idempotency_key=key)
    assert conflict.value.code == "idempotency_key_reused"

    assert client.signature_requests.retrieve(draft.id).id == draft.id
    assert any(
        item.id == draft.id for item in client.signature_requests.list(status="draft", limit=5)
    )
    seen = 0
    for item in client.signature_requests.list(limit=1).auto_paging_iter():
        assert item.id.startswith("sr_")
        seen += 1
        if seen == 3:
            break
    assert seen >= 1
    some = list(itertools.islice(client.signature_requests.all(limit=2), 3))
    assert 1 <= len(some) <= 3

    events = client.signature_requests.list_events(draft.id)
    assert events.data[0].type == "audit.created"
    assert isinstance(events.data[0], wthaiq.AuditEvent)
    certificate = client.signature_requests.certificate(draft.id)
    assert certificate.object == "certificate"
    assert certificate.test is True
    assert certificate.legal_effect == "none"
    evidence = client.signature_requests.evidence(draft.id)
    assert evidence.format == "wthaiq-evidence-test-v1"
    assert evidence.seal is None
    assert isinstance(evidence.issued_at, str)

    for call in (
        client.signature_requests.download,
        client.signature_requests.download_pdf,
        client.signature_requests.remind,
    ):
        with pytest.raises(ValidationError) as info:
            call(draft.id)
        assert info.value.status_code == 400

    canceled = client.signature_requests.cancel(draft.id)
    assert canceled.status == "canceled"
    with pytest.raises(ConflictError) as again:
        client.signature_requests.cancel(draft.id)
    assert again.value.code == "request_not_cancelable"


def test_validation_errors(state: State) -> None:
    client = state.client
    source: SourceParams = {"type": "template", "template_id": state.template.id}
    with pytest.raises(ValidationError) as missing:
        client.signature_requests.create(source=source, send=False)
    assert missing.value.code == "parameter_missing"
    assert missing.value.param == "signers"
    assert "signers" in missing.value.field_errors
    assert (missing.value.request_id or "").startswith("req_")
    with pytest.raises(ValidationError) as email:
        client.signature_requests.create(
            source=source,
            signers=[{"name": "Someone", "email": "not-an-email"}],
            send=False,
        )
    assert email.value.param == "signers[0].email"
    with pytest.raises(ValidationError) as unsupported:
        client.signature_requests.create(
            {
                "source": source,
                "signers": [{"name": "Someone", "email": state.signer_email}],
                "channel": "link",
                "send": False,
            }
        )
    assert unsupported.value.code == "parameter_unsupported"
    assert unsupported.value.param == "channel"


def test_bulk_draft(state: State) -> None:
    try:
        bulk = state.client.signature_requests.create_bulk(
            source={"type": "template", "template_id": state.template.id},
            recipients=[{"name": "Bulk Signer", "email": state.signer_email}],
            fields={"amount": "1"},
            send=False,
        )
    except PermissionDeniedError as error:
        assert error.is_plan_feature_unavailable(), str(error)
        return
    assert bulk.object == "bulk_send"
    assert bulk.created == 1
    assert bulk.failed == 0
    request_id = bulk.requests[0].signature_request
    state.to_cancel.add(request_id)
    assert state.client.signature_requests.retrieve(request_id).status == "draft"


def test_session_signer_and_embedded_link(state: State) -> None:
    client = state.client
    vendor = f"sdk-python-{secrets.token_hex(4)}"
    session = client.sessions.create(
        workflow_id="default",
        template_id=state.template.id,
        channel="link",
        language="en",
        vendor_data=vendor,
        signers=[{"name": "Session Signer", "email": state.signer_email}],
        fields={"amount": "5"},
    )
    state.to_cancel.add(session.id)
    assert session.object == "session"
    assert session.workflow_id == "default"
    assert session.channel == "link"
    assert session.vendor_data == vendor
    assert "token=" in (session.sign_url or "")
    assert isinstance(session.signers[0], wthaiq.objects.SessionSigner)
    assert client.sessions.retrieve(session.id).id == session.id
    assert [item.id for item in client.sessions.list(vendor_data=vendor)] == [session.id]
    signer_id = session.signers[0].id
    signer = client.signers.retrieve(signer_id)
    assert signer.id == signer_id
    assert signer.status == "sent"
    try:
        embedded = client.signers.create_signing_session(signer_id)
    except PermissionDeniedError as error:
        assert error.is_plan_feature_unavailable(), str(error)
    else:
        assert embedded.mode == "iframe"
        assert "/embed/sign/" in embedded.signing_url
        assert embedded.expires_at > time.time()
    with pytest.raises(ValidationError) as no_messages:
        client.signature_requests.remind(session.id)
    assert no_messages.value.code == "channel_has_no_messages"
    with pytest.raises(ValidationError) as override:
        client.sessions.create(
            {
                "workflow_id": "default",
                "template_id": state.template.id,
                "ordered": True,
                "signers": [{"name": "X", "email": state.signer_email}],
            }
        )
    assert override.value.code == "invalid_override"
    assert override.value.param == "ordered"
    with pytest.raises(NotFoundError) as workflow:
        client.sessions.create(
            workflow_id="wf_doesnotexist", signers=[{"name": "X", "email": state.signer_email}]
        )
    assert workflow.value.code == "workflow_not_found"
    assert client.signature_requests.cancel(session.id).status == "canceled"


def test_webhook_endpoints_and_events(state: State) -> None:
    client = state.client
    assert client.webhook_endpoints.event_types() == list(wthaiq.EVENT_TYPES)
    url = os.environ.get(
        "WTHAIQ_TEST_WEBHOOK_URL", "https://example.com/wthaiq-sdk-python-integration"
    )
    try:
        endpoint = client.webhook_endpoints.create(url=url, enabled_events=["document.sealed"])
    except ValidationError as error:
        if error.param == "url":
            pytest.skip(f"the API could not accept the webhook URL (DNS lookup failed?): {error}")
        raise
    state.to_delete.add(endpoint.id)
    assert endpoint.id.startswith("we_")
    assert re.fullmatch(r"whsec_[0-9a-f]{48}", endpoint.secret or "")
    assert endpoint.enabled_events == ["document.sealed"]
    assert endpoint.livemode is False
    fetched = client.webhook_endpoints.retrieve(endpoint.id)
    assert fetched.secret is None, "the secret is only returned at creation"
    assert any(item.id == endpoint.id for item in client.webhook_endpoints.list())
    updated = client.webhook_endpoints.update(
        endpoint.id, status="disabled", enabled_events=["document.sealed", "verification.created"]
    )
    assert updated.status == "disabled"
    assert len(updated.enabled_events) == 2
    assert len(client.webhook_endpoints.deliveries(endpoint.id)) == 0
    with pytest.raises(ValidationError) as bad_type:
        client.webhook_endpoints.create(
            {"url": url, "enabled_events": ["not.a_type"]},
        )
    assert bad_type.value.param == "enabled_events"
    deleted = client.webhook_endpoints.delete(endpoint.id)
    assert deleted.deleted is True
    state.to_delete.discard(endpoint.id)
    with pytest.raises(NotFoundError) as gone:
        client.webhook_endpoints.retrieve(endpoint.id)
    assert gone.value.code == "resource_missing"

    events = client.events.list(limit=3)
    assert len(events) <= 3
    if events.data:
        first = events.data[0]
        assert client.events.retrieve(first.id).id == first.id
        with pytest.raises((InvalidRequestError, RateLimitError)):
            client.events.redeliver(first.id)


def test_lookups_and_authentication(state: State) -> None:
    client = state.client
    verification = client.verifications.retrieve("WTQ-SDKNOTFOUND")
    assert verification.found is False
    assert verification.status == "not_found"
    with pytest.raises(NotFoundError) as idv:
        client.identity_verifications.retrieve("idv_999999999")
    assert idv.value.code == "resource_missing"
    with pytest.raises(NotFoundError):
        client.documents.retrieve("doc_doesnotexist000000")
    assert client.flows.list().object == "list"
    bad = wthaiq.Client("sk_test_" + "0" * 40, base_url=BASE_URL, max_retries=0)
    with pytest.raises(AuthenticationError) as auth:
        bad.account.retrieve()
    assert auth.value.code == "invalid_api_key"
    read_only = os.environ.get("WTHAIQ_API_KEY_READONLY", "")
    if read_only:
        ro = wthaiq.Client(read_only, base_url=BASE_URL, max_retries=0)
        assert ro.account.retrieve().object == "api_root"
        with pytest.raises(PermissionDeniedError) as forbidden:
            ro.templates.create(name="x", content="<p>x</p>")
        assert forbidden.value.code == "forbidden"


def test_async_client(state: State) -> None:
    async def run() -> None:
        async with wthaiq.AsyncClient(API_KEY, base_url=BASE_URL, max_retries=1) as client:
            root, usage = await asyncio.gather(client.account.retrieve(), client.usage.retrieve())
            assert root.object == "api_root"
            assert usage.object == "usage"
            page = await client.signature_requests.list(limit=2)
            assert len(page) <= 2
            ids = []
            async for item in client.signature_requests.all(limit=2):
                ids.append(item.id)
                if len(ids) == 3:
                    break
            assert all(value.startswith("sr_") for value in ids)
            template = await client.templates.retrieve(state.template.id)
            assert template.id == state.template.id
            missing = await client.verifications.retrieve("WTQ-SDKNOTFOUND")
            assert missing.found is False
            with pytest.raises(NotFoundError):
                await client.signature_requests.retrieve("sr_00000000000000000000")

    asyncio.run(run())

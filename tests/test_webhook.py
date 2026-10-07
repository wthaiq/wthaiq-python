from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

import wthaiq
from wthaiq import Webhook, objects

FIXTURE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "webhook-server-signed.json").read_text(encoding="utf-8")
)
SECRET = "whsec_" + "0123456789abcdef" * 3
PAYLOAD = b'{"id":"evt_1","object":"event","type":"signer.signed","created_at":1,"livemode":false,"data":{"object":{"id":"sgr_1","object":"signer","name":"\xd9\x86\xd9\x87\xd9\x89","signature_request":"sr_1"}}}'


def test_server_signed_fixture_verifies() -> None:
    header = FIXTURE["headers"]["Wthaiq-Signature"]
    event = Webhook.construct_event(FIXTURE["payload"], header, FIXTURE["secret"], tolerance=0)
    assert isinstance(event, objects.Event)
    assert event.id == FIXTURE["event_id"]
    assert event.type == "signature_request.completed"
    assert event.livemode is False
    sr = event.data.object
    assert isinstance(sr, objects.SignatureRequest)
    assert sr.id == "sr_cd5a6eb8468344583538"
    assert sr.title == "عقد خدمات — SDK fixture"
    assert sr.metadata.note == 'slashes / and "quotes"'
    assert isinstance(sr.signers[0], objects.Signer)
    raw = FIXTURE["payload"].encode("utf-8")
    assert Webhook.construct_event(raw, header.encode(), FIXTURE["secret"], tolerance=0).id
    assert Webhook.is_valid(raw, header, FIXTURE["secret"], tolerance=0)


def test_fixture_fails_with_any_change() -> None:
    header = FIXTURE["headers"]["Wthaiq-Signature"]
    payload: str = FIXTURE["payload"]
    reencoded = json.dumps(json.loads(payload))
    for body, secret in [
        (payload.replace("draft", "sent"), FIXTURE["secret"]),
        (reencoded, FIXTURE["secret"]),
        (payload, FIXTURE["secret"] + "x"),
        (payload, FIXTURE["secret"].removeprefix("whsec_")),
    ]:
        with pytest.raises(wthaiq.SignatureVerificationError, match="does not match"):
            Webhook.construct_event(body, header, secret, tolerance=0)


def test_fixture_is_too_old_with_default_tolerance() -> None:
    header = FIXTURE["headers"]["Wthaiq-Signature"]
    with pytest.raises(wthaiq.SignatureVerificationError, match="tolerance") as info:
        Webhook.construct_event(FIXTURE["payload"], header, FIXTURE["secret"])
    assert info.value.header == header
    assert isinstance(info.value, wthaiq.error.SignatureVerificationError)


def test_test_header_round_trip() -> None:
    header = Webhook.generate_test_header(PAYLOAD, SECRET)
    event = Webhook.construct_event(PAYLOAD, header, SECRET)
    assert isinstance(event.data.object, objects.Signer)
    assert event.data.object.name == "نهى"
    assert event.data.object.signature_request == "sr_1"


def test_compute_signature_matches_scheme() -> None:
    import hashlib
    import hmac

    expected = hmac.new(SECRET.encode(), b"1700000000." + PAYLOAD, hashlib.sha256).hexdigest()
    assert Webhook.compute_signature(1700000000, PAYLOAD, SECRET) == expected
    assert Webhook.compute_signature("1700000000", PAYLOAD.decode("utf-8"), SECRET) == expected
    header = Webhook.generate_test_header(PAYLOAD, SECRET, timestamp=1700000000)
    assert header == f"t=1700000000,v1={expected}"


def test_timestamp_tolerance(monkeypatch: pytest.MonkeyPatch) -> None:
    header = Webhook.generate_test_header(PAYLOAD, SECRET, timestamp=1_000_000)
    monkeypatch.setattr(time, "time", lambda: 1_000_000 + 299.0)
    assert Webhook.is_valid(PAYLOAD, header, SECRET)
    monkeypatch.setattr(time, "time", lambda: 1_000_000 + 301.0)
    assert not Webhook.is_valid(PAYLOAD, header, SECRET)
    assert Webhook.is_valid(PAYLOAD, header, SECRET, tolerance=600)
    assert Webhook.is_valid(PAYLOAD, header, SECRET, tolerance=0)
    monkeypatch.setattr(time, "time", lambda: 1_000_000 - 301.0)
    assert not Webhook.is_valid(PAYLOAD, header, SECRET), "future timestamps are refused too"


def test_multiple_signatures_and_spacing() -> None:
    good = Webhook.compute_signature(int(time.time()), PAYLOAD, SECRET)
    t = int(time.time())
    good = Webhook.compute_signature(t, PAYLOAD, SECRET)
    header = f" t={t} , v1={'0' * 64}, v1={good.upper()}, v0=ignored "
    assert Webhook.construct_event(PAYLOAD, header, SECRET).id == "evt_1"
    assert Webhook.construct_event(PAYLOAD, [f"t={t}", f"v1={good}"], SECRET).id == "evt_1"


@pytest.mark.parametrize(
    ("header", "message"),
    [
        (None, "missing"),
        ("", "missing"),
        ("v1=abc", "timestamp"),
        ("t=abc,v1=abc", "timestamp"),
        ("t=-5,v1=abc", "timestamp"),
        ("t=" + "".join(map(chr, (0x661, 0x667, 0x660, 0x660))) + ",v1=abc", "timestamp"),
        ("t=1700000000", "No v1 signature"),
        ("t=1700000000,v1=", "No v1 signature"),
        ("garbage", "timestamp"),
        ("t=1700000000,v1=" + "0" * 64, "does not match"),
    ],
)
def test_bad_headers(header: str | None, message: str) -> None:
    with pytest.raises(wthaiq.SignatureVerificationError, match=message):
        Webhook.verify_header(PAYLOAD, header, SECRET)
    assert Webhook.is_valid(PAYLOAD, header, SECRET) is False


def test_invalid_json_with_valid_signature() -> None:
    for body in (b"not json", b"[1,2]"):
        header = Webhook.generate_test_header(body, SECRET)
        with pytest.raises(wthaiq.SignatureVerificationError, match="JSON"):
            Webhook.construct_event(body, header, SECRET)


@pytest.mark.parametrize(
    ("payload", "secret", "tolerance"),
    [
        (PAYLOAD, "", 300),
        (PAYLOAD, None, 300),
        (PAYLOAD, SECRET, -1),
        (PAYLOAD, SECRET, True),
        (123, SECRET, 300),
    ],
)
def test_misuse_raises_invalid_argument(payload: object, secret: object, tolerance: object) -> None:
    with pytest.raises(wthaiq.InvalidArgumentError):
        Webhook.verify_header(payload, "t=1,v1=a", secret, tolerance)  # type: ignore[arg-type]


def test_header_constants() -> None:
    assert Webhook.SIGNATURE_HEADER == "Wthaiq-Signature"
    assert Webhook.EVENT_ID_HEADER == "Wthaiq-Event-Id"
    assert Webhook.ENDPOINT_ID_HEADER == "Wthaiq-Endpoint-Id"
    assert Webhook.DEFAULT_TOLERANCE == 300
    with pytest.raises(wthaiq.InvalidArgumentError):
        Webhook.verify_header(PAYLOAD, 42, SECRET)  # type: ignore[arg-type]

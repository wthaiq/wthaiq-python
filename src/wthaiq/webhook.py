"""Webhook signature verification.

Wthaiq signs every delivery with the endpoint secret::

    Wthaiq-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, t + "." + raw_body)>

The key is the whole secret string (including ``whsec_``) and the message is the exact raw request
body. Always pass the raw bytes you received, never a re-encoded JSON document.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Sequence
from typing import Union

from .error import InvalidArgumentError, SignatureVerificationError
from .objects import Event

__all__ = ["Webhook"]

Payload = Union[bytes, bytearray, memoryview, str]
SignatureHeader = Union[str, bytes, Sequence[str], None]


def _payload_bytes(payload: object) -> bytes:
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)
    raise InvalidArgumentError("The webhook payload must be the raw request body (bytes or str).")


def _header_text(header: object) -> str:
    if header is None:
        return ""
    if isinstance(header, bytes):
        return header.decode("latin-1").strip()
    if isinstance(header, str):
        return header.strip()
    if isinstance(header, Sequence):
        return ",".join(str(part).strip() for part in header if str(part).strip())
    raise InvalidArgumentError("The signature header must be a string.")


def _sign(timestamp: str, payload: bytes, secret: str) -> str:
    message = timestamp.encode("ascii") + b"." + payload
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class Webhook:
    """Verifies and decodes webhook deliveries."""

    SIGNATURE_HEADER = "Wthaiq-Signature"
    EVENT_ID_HEADER = "Wthaiq-Event-Id"
    ENDPOINT_ID_HEADER = "Wthaiq-Endpoint-Id"
    DEFAULT_TOLERANCE = 300

    @staticmethod
    def construct_event(
        payload: Payload,
        sig_header: SignatureHeader,
        secret: str,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> Event:
        """Verifies the signature and returns the decoded :class:`~wthaiq.objects.Event`.

        :param payload: the raw request body.
        :param sig_header: the ``Wthaiq-Signature`` header.
        :param secret: the endpoint secret (``whsec_…``) returned when the endpoint was created.
        :param tolerance: maximum age of the signature in seconds; ``0`` disables the check.
        :raises SignatureVerificationError: invalid header, signature, timestamp or JSON.
        """
        data = _payload_bytes(payload)
        header = Webhook.verify_header(data, sig_header, secret, tolerance)
        try:
            decoded = json.loads(data.decode("utf-8"))
        except ValueError as exc:
            raise SignatureVerificationError(
                "The webhook payload is not valid JSON.", header=header
            ) from exc
        if not isinstance(decoded, dict):
            raise SignatureVerificationError(
                "The webhook payload is not a JSON object.", header=header
            )
        return Event(decoded)

    @staticmethod
    def verify_header(
        payload: Payload,
        sig_header: SignatureHeader,
        secret: str,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> str:
        """Verifies the signature without decoding the payload. Returns the checked header."""
        data = _payload_bytes(payload)
        if not isinstance(secret, str) or secret == "":
            raise InvalidArgumentError(
                "The webhook endpoint secret is empty. Use the whsec_... value returned when the "
                "endpoint was created."
            )
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance < 0:
            raise InvalidArgumentError("tolerance must be a non-negative number of seconds.")
        header = _header_text(sig_header)
        if header == "":
            raise SignatureVerificationError(
                "The Wthaiq-Signature header is missing.", header=header
            )
        timestamp: str | None = None
        signatures: list[str] = []
        for part in header.split(","):
            key, sep, value = part.strip().partition("=")
            if not sep:
                continue
            key, value = key.strip(), value.strip()
            if key == "t" and timestamp is None:
                timestamp = value
            elif key == "v1" and value:
                signatures.append(value.lower())
        if timestamp is None or not (timestamp.isascii() and timestamp.isdigit()):
            raise SignatureVerificationError(
                "Unable to read the timestamp from the Wthaiq-Signature header.", header=header
            )
        if not signatures:
            raise SignatureVerificationError(
                "No v1 signature found in the Wthaiq-Signature header.", header=header
            )
        expected = _sign(timestamp, data, secret).encode("ascii")
        matched = False
        for signature in signatures:
            if hmac.compare_digest(expected, signature.encode("utf-8", errors="replace")):
                matched = True
        if not matched:
            raise SignatureVerificationError(
                "The webhook signature does not match the payload. Check that you use the raw "
                "request body and the right endpoint secret.",
                header=header,
            )
        if tolerance > 0 and abs(time.time() - int(timestamp)) > tolerance:
            raise SignatureVerificationError(
                f"The webhook timestamp is outside the tolerance of {tolerance:g} seconds.",
                header=header,
            )
        return header

    @staticmethod
    def is_valid(
        payload: Payload,
        sig_header: SignatureHeader,
        secret: str,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> bool:
        """``True`` when the signature is valid and recent, ``False`` otherwise."""
        try:
            Webhook.verify_header(payload, sig_header, secret, tolerance)
        except SignatureVerificationError:
            return False
        return True

    @staticmethod
    def compute_signature(timestamp: int | str, payload: Payload, secret: str) -> str:
        """The ``v1`` value for a timestamp and payload."""
        return _sign(str(timestamp), _payload_bytes(payload), secret)

    @staticmethod
    def generate_test_header(payload: Payload, secret: str, timestamp: int | None = None) -> str:
        """A valid ``Wthaiq-Signature`` header, for your own tests."""
        t = str(int(time.time()) if timestamp is None else timestamp)
        return f"t={t},v1={Webhook.compute_signature(t, payload, secret)}"

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .. import objects
from .._requestor import ParsedOptions
from .._util import build_path
from ..error import NotFoundError
from ..objects import ResponseInfo
from ._base import AsyncResource, SyncResource, options_only

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from ..types import RequestOptions


class Documents(SyncResource):
    """Previously uploaded documents (``/documents``, secret key)."""

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Document:
        return self._request(
            "GET",
            build_path("/documents/{}", id),
            objects.Document,
            options_only("retrieve", options),
        )


class AsyncDocuments(AsyncResource):
    """Previously uploaded documents (``/documents``, secret key)."""

    async def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Document:
        return await self._request(
            "GET",
            build_path("/documents/{}", id),
            objects.Document,
            options_only("retrieve", options),
        )


class IdentityVerifications(SyncResource):
    """Identity verifications of signers (``/identity_verifications``, secret key)."""

    def retrieve(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.IdentityVerification:
        return self._request(
            "GET",
            build_path("/identity_verifications/{}", id),
            objects.IdentityVerification,
            options_only("retrieve", options),
        )


class AsyncIdentityVerifications(AsyncResource):
    """Identity verifications of signers (``/identity_verifications``, secret key)."""

    async def retrieve(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.IdentityVerification:
        return await self._request(
            "GET",
            build_path("/identity_verifications/{}", id),
            objects.IdentityVerification,
            options_only("retrieve", options),
        )


def _not_found_verification(error: NotFoundError, reference: str) -> objects.Verification | None:
    info = ResponseInfo(error.status_code, dict(error.headers))
    if error.code == "not_found":
        missing = {
            "object": "verification",
            "reference": reference,
            "found": False,
            "status": "not_found",
            "integrity": "unknown",
        }
        return objects.Verification(missing, last_response=info)
    try:
        decoded = json.loads(error.raw_body)
    except ValueError:
        return None
    if (
        isinstance(decoded, dict)
        and decoded.get("object") == "verification"
        and "error" not in decoded
    ):
        return objects.Verification(decoded, last_response=info)
    return None


class Verifications(SyncResource):
    """Public reference lookup (``/verifications``, secret key)."""

    def retrieve(
        self, reference: str, /, **options: Unpack[RequestOptions]
    ) -> objects.Verification:
        """Looks up a reference such as ``WTQ-1A2B3C4D5E6F``.

        An unknown reference returns a :class:`~wthaiq.objects.Verification` with
        ``found=False`` instead of raising, whether the API answers 404 with a verification body
        or with the error code ``not_found``.
        """
        parsed: ParsedOptions = options_only("retrieve", options)
        try:
            return self._request(
                "GET", build_path("/verifications/{}", reference), objects.Verification, parsed
            )
        except NotFoundError as error:
            result = _not_found_verification(error, reference)
            if result is None:
                raise
            return result


class AsyncVerifications(AsyncResource):
    """Public reference lookup (``/verifications``, secret key)."""

    async def retrieve(
        self, reference: str, /, **options: Unpack[RequestOptions]
    ) -> objects.Verification:
        """Looks up a reference such as ``WTQ-1A2B3C4D5E6F``.

        An unknown reference returns a :class:`~wthaiq.objects.Verification` with
        ``found=False`` instead of raising, whether the API answers 404 with a verification body
        or with the error code ``not_found``.
        """
        parsed: ParsedOptions = options_only("retrieve", options)
        try:
            return await self._request(
                "GET", build_path("/verifications/{}", reference), objects.Verification, parsed
            )
        except NotFoundError as error:
            result = _not_found_verification(error, reference)
            if result is None:
                raise
            return result

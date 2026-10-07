from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import TYPE_CHECKING, Any, Union

from .. import objects
from .._requestor import ParsedOptions, Spec
from .._util import build_path, equal_hex, filename_from_disposition, looks_like_pdf, sha256_hex
from ..error import UnexpectedResponseError, WthaiqError
from ..objects import PdfFile, ResponseInfo, SavedPdf
from ..pagination import AsyncPage, Page
from ..transport import HttpResponse
from ._base import AsyncResource, SyncResource, options_only, split_params

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from ..types import (
        BulkCreateKwargs,
        RequestOptions,
        SignatureRequestCreateKwargs,
        SignatureRequestListKwargs,
    )

StrPath = Union[str, "os.PathLike[str]"]


def _pdf_spec(id: str) -> Spec:
    return Spec(
        "GET", build_path("/signature_requests/{}/download/pdf", id), accept="application/pdf"
    )


def _to_pdf(response: HttpResponse) -> PdfFile:
    body = response.body
    if not looks_like_pdf(body):
        raise UnexpectedResponseError(
            "The Wthaiq API did not return a PDF file.",
            status_code=response.status_code,
            raw_body=body[:500].decode("utf-8", errors="replace"),
        )
    actual = sha256_hex(body)
    expected = response.headers.get("x-file-sha256", "")
    if expected and not equal_hex(expected, actual):
        raise UnexpectedResponseError(
            "The downloaded PDF does not match the X-File-Sha256 fingerprint sent by the API.",
            status_code=response.status_code,
        )
    return PdfFile(
        body,
        sha256=actual,
        filename=filename_from_disposition(response.headers.get("content-disposition")),
        last_response=ResponseInfo(response.status_code, dict(response.headers)),
    )


def _write_atomic(path: StrPath, pdf: PdfFile) -> SavedPdf:
    target = os.fspath(path)
    tmp = f"{target}.part-{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp, "xb") as handle:
            handle.write(pdf)
        os.replace(tmp, target)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise WthaiqError(f'Could not write the PDF to "{target}": {exc}') from exc
    return SavedPdf(path=target, bytes=len(pdf), sha256=pdf.sha256)


class SignatureRequests(SyncResource):
    """Signature requests (``/signature_requests``)."""

    def create(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SignatureRequestCreateKwargs],
    ) -> objects.SignatureRequest:
        """Creates a signature request and sends it (``send=False`` creates a draft)."""
        body, options = split_params(params, kwargs)
        return self._request("POST", "/signature_requests", objects.SignatureRequest, options, body)

    def create_bulk(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[BulkCreateKwargs]
    ) -> objects.BulkSend:
        """Creates one signature request per entry of ``recipients``."""
        body, options = split_params(params, kwargs)
        return self._request("POST", "/signature_requests/bulk", objects.BulkSend, options, body)

    def list(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SignatureRequestListKwargs],
    ) -> Page[objects.SignatureRequest]:
        """One page of signature requests, newest first (secret key)."""
        query, options = split_params(params, kwargs)
        return self._page("/signature_requests", objects.SignatureRequest, query, options)

    def all(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SignatureRequestListKwargs],
    ) -> Iterator[objects.SignatureRequest]:
        """Iterates over every signature request, requesting pages lazily."""
        query, options = split_params(params, kwargs)
        return self._iterate("/signature_requests", objects.SignatureRequest, query, options)

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.SignatureRequest:
        return self._request(
            "GET",
            build_path("/signature_requests/{}", id),
            objects.SignatureRequest,
            options_only("retrieve", options),
        )

    def send(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.SignatureRequest:
        """Sends a draft (or resends a sent request, with the reminder limits)."""
        return self._request(
            "POST",
            build_path("/signature_requests/{}/send", id),
            objects.SignatureRequest,
            options_only("send", options),
        )

    def remind(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Reminder:
        """Sends a reminder to the signers who have not signed yet."""
        return self._request(
            "POST",
            build_path("/signature_requests/{}/reminders", id),
            objects.Reminder,
            options_only("remind", options),
        )

    def cancel(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.SignatureRequest:
        """Cancels the request; pending signing links stop working. Nothing is refunded."""
        return self._request(
            "POST",
            build_path("/signature_requests/{}/cancel", id),
            objects.SignatureRequest,
            options_only("cancel", options),
        )

    def list_events(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> Page[objects.AuditEvent]:
        """The audit trail (single page, up to 200 events, oldest first)."""
        return self._page(
            build_path("/signature_requests/{}/events", id),
            objects.AuditEvent,
            None,
            options_only("list_events", options),
        )

    def certificate(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Certificate:
        return self._request(
            "GET",
            build_path("/signature_requests/{}/certificate", id),
            objects.Certificate,
            options_only("certificate", options),
        )

    def download(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Download:
        """Metadata of the final document (completed requests only)."""
        return self._request(
            "GET",
            build_path("/signature_requests/{}/download", id),
            objects.Download,
            options_only("download", options),
        )

    def download_pdf(self, id: str, /, **options: Unpack[RequestOptions]) -> PdfFile:
        """The final PDF as bytes, checked against the ``X-File-Sha256`` header (secret key)."""
        parsed = options_only("download_pdf", options)
        return _to_pdf(self._requestor.request(_pdf_spec(id), parsed))

    def download_pdf_to(
        self, id: str, path: StrPath, /, **options: Unpack[RequestOptions]
    ) -> SavedPdf:
        """Downloads the final PDF and writes it to ``path`` atomically."""
        return _write_atomic(path, self.download_pdf(id, **options))

    def evidence(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Evidence:
        """The sealed evidence record (live) or the unsealed test record (secret key)."""
        return self._request(
            "GET",
            build_path("/signature_requests/{}/evidence", id),
            objects.Evidence,
            options_only("evidence", options),
        )


class AsyncSignatureRequests(AsyncResource):
    """Signature requests (``/signature_requests``)."""

    async def create(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SignatureRequestCreateKwargs],
    ) -> objects.SignatureRequest:
        """Creates a signature request and sends it (``send=False`` creates a draft)."""
        body, options = split_params(params, kwargs)
        return await self._request(
            "POST", "/signature_requests", objects.SignatureRequest, options, body
        )

    async def create_bulk(
        self, params: Mapping[str, Any] | None = None, /, **kwargs: Unpack[BulkCreateKwargs]
    ) -> objects.BulkSend:
        """Creates one signature request per entry of ``recipients``."""
        body, options = split_params(params, kwargs)
        return await self._request(
            "POST", "/signature_requests/bulk", objects.BulkSend, options, body
        )

    async def list(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SignatureRequestListKwargs],
    ) -> AsyncPage[objects.SignatureRequest]:
        """One page of signature requests, newest first (secret key)."""
        query, options = split_params(params, kwargs)
        return await self._page("/signature_requests", objects.SignatureRequest, query, options)

    def all(
        self,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[SignatureRequestListKwargs],
    ) -> AsyncIterator[objects.SignatureRequest]:
        """Iterates (``async for``) over every signature request, requesting pages lazily."""
        query, options = split_params(params, kwargs)
        return self._iterate("/signature_requests", objects.SignatureRequest, query, options)

    async def retrieve(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.SignatureRequest:
        return await self._request(
            "GET",
            build_path("/signature_requests/{}", id),
            objects.SignatureRequest,
            options_only("retrieve", options),
        )

    async def send(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.SignatureRequest:
        """Sends a draft (or resends a sent request, with the reminder limits)."""
        return await self._request(
            "POST",
            build_path("/signature_requests/{}/send", id),
            objects.SignatureRequest,
            options_only("send", options),
        )

    async def remind(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Reminder:
        """Sends a reminder to the signers who have not signed yet."""
        return await self._request(
            "POST",
            build_path("/signature_requests/{}/reminders", id),
            objects.Reminder,
            options_only("remind", options),
        )

    async def cancel(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.SignatureRequest:
        """Cancels the request; pending signing links stop working. Nothing is refunded."""
        return await self._request(
            "POST",
            build_path("/signature_requests/{}/cancel", id),
            objects.SignatureRequest,
            options_only("cancel", options),
        )

    async def list_events(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> AsyncPage[objects.AuditEvent]:
        """The audit trail (single page, up to 200 events, oldest first)."""
        return await self._page(
            build_path("/signature_requests/{}/events", id),
            objects.AuditEvent,
            None,
            options_only("list_events", options),
        )

    async def certificate(
        self, id: str, /, **options: Unpack[RequestOptions]
    ) -> objects.Certificate:
        return await self._request(
            "GET",
            build_path("/signature_requests/{}/certificate", id),
            objects.Certificate,
            options_only("certificate", options),
        )

    async def download(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Download:
        """Metadata of the final document (completed requests only)."""
        return await self._request(
            "GET",
            build_path("/signature_requests/{}/download", id),
            objects.Download,
            options_only("download", options),
        )

    async def download_pdf(self, id: str, /, **options: Unpack[RequestOptions]) -> PdfFile:
        """The final PDF as bytes, checked against the ``X-File-Sha256`` header (secret key)."""
        parsed: ParsedOptions = options_only("download_pdf", options)
        return _to_pdf(await self._requestor.request(_pdf_spec(id), parsed))

    async def download_pdf_to(
        self, id: str, path: StrPath, /, **options: Unpack[RequestOptions]
    ) -> SavedPdf:
        """Downloads the final PDF and writes it to ``path`` atomically."""
        pdf = await self.download_pdf(id, **options)
        return await asyncio.to_thread(_write_atomic, path, pdf)

    async def evidence(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Evidence:
        """The sealed evidence record (live) or the unsealed test record (secret key)."""
        return await self._request(
            "GET",
            build_path("/signature_requests/{}/evidence", id),
            objects.Evidence,
            options_only("evidence", options),
        )

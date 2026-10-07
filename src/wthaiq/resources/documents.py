from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from typing import IO, TYPE_CHECKING, Any, Union

from .. import objects
from .._requestor import ParsedOptions, Spec
from .._util import build_multipart, build_path, looks_like_pdf
from ..error import InvalidArgumentError, NotFoundError
from ..objects import ResponseInfo
from ._base import AsyncResource, SyncResource, options_only, split_params

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from ..types import DocumentCreateKwargs, RequestOptions

FileContent = Union[bytes, bytearray, memoryview, IO[bytes]]
FileInput = Union[str, "os.PathLike[str]", FileContent, "tuple[str, FileContent]"]
"""A path, raw bytes, a binary file object, or ``(filename, bytes_or_file)``."""

MAX_BYTES = 20 * 1024 * 1024
_DOCUMENT_KEYS = frozenset({"kind", "field_map", "filename"})


def _read_file(file: object) -> tuple[bytes, str]:
    if isinstance(file, tuple):
        if len(file) != 2 or not isinstance(file[0], str) or file[0] == "":
            raise InvalidArgumentError("A file tuple must be (filename, content).")
        content, _ = _read_file(file[1])
        return content, file[0]
    if isinstance(file, (bytes, bytearray, memoryview)):
        return bytes(file), "document.pdf"
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            raise InvalidArgumentError(
                f'The file "{path}" does not exist or is not readable.'
            ) from exc
        return data, os.path.basename(str(path)) or "document.pdf"
    read = getattr(file, "read", None)
    if callable(read):
        data = read()
        if not isinstance(data, (bytes, bytearray)):
            raise InvalidArgumentError("Open the file in binary mode ('rb').")
        name = getattr(file, "name", None)
        filename = os.path.basename(name) if isinstance(name, str) and name else "document.pdf"
        return bytes(data), filename
    raise InvalidArgumentError(
        "file must be a path, bytes, a binary file object, or a (filename, content) tuple."
    )


def _multipart(content: bytes, filename: str, params: Mapping[str, Any]) -> Spec:
    unknown = sorted(key for key in params if key not in _DOCUMENT_KEYS)
    if unknown:
        raise InvalidArgumentError(f"Unknown document parameter(s): {', '.join(unknown)}.")
    if len(content) > MAX_BYTES:
        raise InvalidArgumentError("The file is larger than the 20 MB limit.")
    if not looks_like_pdf(content):
        raise InvalidArgumentError("The file must be a PDF (it must start with %PDF-).")
    custom_name = params.get("filename")
    if custom_name is not None:
        if not isinstance(custom_name, str) or custom_name == "":
            raise InvalidArgumentError("filename must be a non-empty string.")
        filename = custom_name
    fields: dict[str, str] = {}
    kind = params.get("kind")
    if kind is not None:
        if not isinstance(kind, str):
            raise InvalidArgumentError("kind must be a string.")
        fields["kind"] = kind
    field_map = params.get("field_map")
    if field_map is not None:
        if isinstance(field_map, str):
            fields["field_map"] = field_map
        elif isinstance(field_map, (list, tuple)):
            fields["field_map"] = json.dumps(list(field_map), ensure_ascii=False)
        else:
            raise InvalidArgumentError("field_map must be a list or a JSON string.")
    body, content_type = build_multipart(fields, {"file": (filename, "application/pdf", content)})
    return Spec("POST", "/documents", body=body, content_type=content_type)


class Documents(SyncResource):
    """Uploaded PDF documents (``/documents``, secret key)."""

    def create(
        self,
        file: FileInput,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[DocumentCreateKwargs],
    ) -> objects.Document:
        """Uploads a PDF (at most 20 MB) as ``multipart/form-data``."""
        values, options = split_params(params, kwargs)
        content, filename = _read_file(file)
        body, info = self._raw(_multipart(content, filename, values), options)
        return objects.Document(body, last_response=info)

    def retrieve(self, id: str, /, **options: Unpack[RequestOptions]) -> objects.Document:
        return self._request(
            "GET",
            build_path("/documents/{}", id),
            objects.Document,
            options_only("retrieve", options),
        )


class AsyncDocuments(AsyncResource):
    """Uploaded PDF documents (``/documents``, secret key)."""

    async def create(
        self,
        file: FileInput,
        params: Mapping[str, Any] | None = None,
        /,
        **kwargs: Unpack[DocumentCreateKwargs],
    ) -> objects.Document:
        """Uploads a PDF (at most 20 MB) as ``multipart/form-data``."""
        values, options = split_params(params, kwargs)
        if isinstance(file, (str, os.PathLike)):
            content, filename = await asyncio.to_thread(_read_file, file)
        else:
            content, filename = _read_file(file)
        body, info = await self._raw(_multipart(content, filename, values), options)
        return objects.Document(body, last_response=info)

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


def _not_found_verification(error: NotFoundError) -> objects.Verification | None:
    try:
        decoded = json.loads(error.raw_body)
    except ValueError:
        return None
    if (
        isinstance(decoded, dict)
        and decoded.get("object") == "verification"
        and "error" not in decoded
    ):
        return objects.Verification(
            decoded, last_response=ResponseInfo(error.status_code, dict(error.headers))
        )
    return None


class Verifications(SyncResource):
    """Public reference lookup (``/verifications``, secret key)."""

    def retrieve(
        self, reference: str, /, **options: Unpack[RequestOptions]
    ) -> objects.Verification:
        """Looks up a reference such as ``WTQ-1A2B3C4D5E6F``.

        An unknown reference returns a :class:`~wthaiq.objects.Verification` with
        ``found=False`` instead of raising.
        """
        parsed: ParsedOptions = options_only("retrieve", options)
        try:
            return self._request(
                "GET", build_path("/verifications/{}", reference), objects.Verification, parsed
            )
        except NotFoundError as error:
            result = _not_found_verification(error)
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
        ``found=False`` instead of raising.
        """
        parsed: ParsedOptions = options_only("retrieve", options)
        try:
            return await self._request(
                "GET", build_path("/verifications/{}", reference), objects.Verification, parsed
            )
        except NotFoundError as error:
            result = _not_found_verification(error)
            if result is None:
                raise
            return result

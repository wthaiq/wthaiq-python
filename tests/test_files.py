from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

import wthaiq

from .conftest import (
    AsyncFakeTransport,
    FakeTransport,
    error,
    make_async_client,
    make_client,
    path_of,
)

PDF = b"%PDF-1.7\n1 0 obj << >> endobj\n%%EOF\n"
SHA = hashlib.sha256(PDF).hexdigest()


def pdf_response(sha: str | None = SHA, body: bytes = PDF) -> wthaiq.HttpResponse:
    headers = {
        "content-type": "application/pdf",
        "content-disposition": 'attachment; filename="WTQ-000123.pdf"',
    }
    if sha is not None:
        headers["x-file-sha256"] = sha
    return wthaiq.HttpResponse(200, headers, body)


def test_download_pdf() -> None:
    transport = FakeTransport(pdf_response(SHA.upper()))
    pdf = make_client(transport).signature_requests.download_pdf("sr_1")
    assert pdf == PDF
    assert isinstance(pdf, bytes)
    assert pdf.sha256 == SHA
    assert pdf.filename == "WTQ-000123.pdf"
    assert pdf.last_response is not None and pdf.last_response.status_code == 200
    request = transport.last
    assert path_of(request) == "/signature_requests/sr_1/download/pdf"
    assert request.headers["Accept"] == "application/pdf"


def test_download_pdf_without_fingerprint_header() -> None:
    pdf = make_client(FakeTransport(pdf_response(None))).signature_requests.download_pdf("sr_1")
    assert pdf.sha256 == SHA


def test_download_pdf_fingerprint_mismatch() -> None:
    client = make_client(FakeTransport(pdf_response("0" * 64)))
    with pytest.raises(wthaiq.UnexpectedResponseError, match="X-File-Sha256"):
        client.signature_requests.download_pdf("sr_1")


def test_download_pdf_not_a_pdf() -> None:
    client = make_client(FakeTransport(pdf_response(None, b'{"ok": true}')))
    with pytest.raises(wthaiq.UnexpectedResponseError, match="did not return a PDF"):
        client.signature_requests.download_pdf("sr_1")


def test_download_pdf_errors() -> None:
    client = make_client(FakeTransport(error(409, "pdf_not_ready")))
    with pytest.raises(wthaiq.ConflictError) as info:
        client.signature_requests.download_pdf("sr_1")
    assert info.value.code == "pdf_not_ready"


def test_download_pdf_to(tmp_path: Path) -> None:
    target = tmp_path / "signed.pdf"
    target.write_bytes(b"old")
    saved = make_client(FakeTransport(pdf_response())).signature_requests.download_pdf_to(
        "sr_1", target
    )
    assert saved == wthaiq.SavedPdf(path=str(target), bytes=len(PDF), sha256=SHA)
    assert target.read_bytes() == PDF
    assert [p.name for p in tmp_path.iterdir()] == ["signed.pdf"], "no temporary file is left"


def test_download_pdf_to_unwritable_path(tmp_path: Path) -> None:
    client = make_client(FakeTransport(pdf_response()))
    with pytest.raises(wthaiq.WthaiqError, match="Could not write the PDF"):
        client.signature_requests.download_pdf_to("sr_1", tmp_path / "missing" / "x.pdf")


def test_async_downloads(tmp_path: Path) -> None:
    async def run() -> None:
        client = make_async_client(AsyncFakeTransport(pdf_response()))
        pdf = await client.signature_requests.download_pdf("sr_1")
        assert pdf.sha256 == SHA
        saved = await client.signature_requests.download_pdf_to("sr_1", str(tmp_path / "a.pdf"))
        assert saved.bytes == len(PDF)
        assert (tmp_path / "a.pdf").read_bytes() == PDF

    asyncio.run(run())

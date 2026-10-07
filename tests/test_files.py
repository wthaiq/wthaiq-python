from __future__ import annotations

import asyncio
import hashlib
import io
import json
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
    response,
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


DOCUMENT = {"id": "doc_1", "object": "document", "kind": "pdf", "filename": "contract.pdf"}


def parts(request: wthaiq.HttpRequest) -> dict[str, tuple[str | None, bytes]]:
    content_type = request.headers["Content-Type"]
    assert content_type.startswith("multipart/form-data; boundary=")
    boundary = content_type.split("boundary=", 1)[1].encode()
    assert request.body is not None
    out: dict[str, tuple[str | None, bytes]] = {}
    for chunk in request.body.split(b"--" + boundary)[1:-1]:
        assert chunk.startswith(b"\r\n") and chunk.endswith(b"\r\n")
        head, _, body = chunk[2:-2].partition(b"\r\n\r\n")
        header = head.decode()
        name = header.split('name="', 1)[1].split('"', 1)[0]
        filename = (
            header.split('filename="', 1)[1].split('"', 1)[0] if "filename=" in header else None
        )
        out[name] = (filename, body)
    assert request.body.endswith(b"--" + boundary + b"--\r\n")
    return out


def test_upload_from_path(tmp_path: Path) -> None:
    path = tmp_path / "contract.pdf"
    path.write_bytes(PDF)
    transport = FakeTransport(response(201, DOCUMENT))
    document = make_client(transport).documents.create(
        path, kind="pdf", field_map=[{"key": "sig", "type": "signature", "page": 1, "x": 1, "y": 2}]
    )
    assert isinstance(document, wthaiq.Document)
    assert document.last_response is not None and document.last_response.status_code == 201
    request = transport.last
    assert request.method == "POST"
    assert path_of(request) == "/documents"
    assert request.headers["Idempotency-Key"]
    form = parts(request)
    assert form["file"] == ("contract.pdf", PDF)
    assert form["kind"] == (None, b"pdf")
    assert json.loads(form["field_map"][1]) == [
        {"key": "sig", "type": "signature", "page": 1, "x": 1, "y": 2}
    ]


@pytest.mark.parametrize(
    ("file", "name"),
    [
        (PDF, "document.pdf"),
        (bytearray(PDF), "document.pdf"),
        (("named.pdf", PDF), "named.pdf"),
        (("named.pdf", io.BytesIO(PDF)), "named.pdf"),
        (io.BytesIO(PDF), "document.pdf"),
    ],
)
def test_upload_inputs(file: object, name: str) -> None:
    transport = FakeTransport(response(201, DOCUMENT))
    make_client(transport).documents.create(file, field_map='[{"key":"a"}]')  # type: ignore[arg-type]
    form = parts(transport.last)
    assert form["file"] == (name, PDF)
    assert form["field_map"] == (None, b'[{"key":"a"}]')
    assert "kind" not in form


def test_upload_from_open_file(tmp_path: Path) -> None:
    path = tmp_path / "upload.pdf"
    path.write_bytes(PDF)
    transport = FakeTransport(response(201, DOCUMENT))
    with path.open("rb") as handle:
        make_client(transport).documents.create(handle, filename="custom.pdf")
    assert parts(transport.last)["file"] == ("custom.pdf", PDF)


@pytest.mark.parametrize(
    ("file", "params", "message"),
    [
        (b"not a pdf", {}, "must be a PDF"),
        ("BIG", {}, "20 MB"),
        (PDF, {"unknown": 1}, "Unknown document parameter"),
        (PDF, {"kind": 3}, "kind must be a string"),
        (PDF, {"field_map": {"a": 1}}, "field_map"),
        (PDF, {"filename": ""}, "filename"),
        ("/definitely/missing.pdf", {}, "does not exist"),
        (io.StringIO("text"), {}, "binary mode"),
        (42, {}, "file must be"),
        (("", PDF), {}, "tuple"),
    ],
)
def test_upload_validation(file: object, params: dict[str, object], message: str) -> None:
    if file == "BIG":
        file = b"%PDF-" + b"0" * (20 * 1024 * 1024)
    transport = FakeTransport(response(201, DOCUMENT))
    with pytest.raises(wthaiq.InvalidArgumentError, match=message):
        make_client(transport).documents.create(file, params)  # type: ignore[arg-type]
    assert transport.requests == []


def test_async_upload(tmp_path: Path) -> None:
    path = tmp_path / "async.pdf"
    path.write_bytes(PDF)

    async def run() -> None:
        transport = AsyncFakeTransport(response(201, DOCUMENT))
        client = make_async_client(transport)
        await client.documents.create(str(path), kind="contract")
        assert parts(transport.last)["file"] == ("async.pdf", PDF)
        await client.documents.create(PDF)
        assert parts(transport.last)["file"] == ("document.pdf", PDF)

    asyncio.run(run())

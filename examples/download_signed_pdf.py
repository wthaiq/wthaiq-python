"""Download the signed PDF and the evidence record of a completed request.

WTHAIQ_API_KEY=sk_... python examples/download_signed_pdf.py sr_... signed.pdf
"""

from __future__ import annotations

import sys

from _client import client

import wthaiq

request_id, target = sys.argv[1], sys.argv[2]
wt = client()

try:
    info = wt.signature_requests.download(request_id)
    print("pdf status:", info.pdf_status, info.pdf_sha256)
    saved = wt.signature_requests.download_pdf_to(request_id, target)
    print(f"saved {saved.bytes} bytes to {saved.path} (sha256 {saved.sha256})")
    evidence = wt.signature_requests.evidence(request_id)
    print("evidence format:", evidence.format, "verify ref:", evidence.verify_ref)
except wthaiq.ConflictError as e:
    if e.code != "pdf_not_ready":
        raise
    print("the PDF is not ready yet; try again shortly")
except wthaiq.ValidationError as e:
    print("not available yet (the request is not completed):", e.code, e.request_id)
except wthaiq.NotFoundError as e:
    print("no such request in this mode:", e.request_id)

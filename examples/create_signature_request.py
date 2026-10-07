"""Create a signature request from a template, as a draft, then cancel it.

    WTHAIQ_API_KEY=sk_test_... python examples/create_signature_request.py tpl_123 you@example.com

In test mode the signer must be the account owner (or a team member).
"""

from __future__ import annotations

import sys
import uuid

from _client import client

template_id, signer_email = sys.argv[1], sys.argv[2]
wt = client()

sr = wt.signature_requests.create(
    title="Service agreement",
    source={"type": "template", "template_id": template_id},
    signers=[{"name": "Noha Adel", "email": signer_email, "fields": {"amount": "1500"}}],
    reminders={"enabled": True, "interval_hours": 48, "max": 3},
    metadata={"order_id": "A-1024"},
    send=False,  # remove to send immediately
    idempotency_key=str(uuid.uuid4()),
)
request_id = sr.last_response.request_id if sr.last_response else None
print("created", sr.id, sr.status, "request id:", request_id)

# wt.signature_requests.send(sr.id)  # sends the draft
canceled = wt.signature_requests.cancel(sr.id)
print("canceled", canceled.id, canceled.status)

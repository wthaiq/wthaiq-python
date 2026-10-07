"""Receive webhooks with Flask.

pip install flask
WTHAIQ_WEBHOOK_SECRET=whsec_... flask --app examples/webhook_flask.py run
"""

from __future__ import annotations

import os

from flask import Flask, request

import wthaiq

app = Flask(__name__)
endpoint_secret = os.environ["WTHAIQ_WEBHOOK_SECRET"]
seen: set[str] = set()  # use your database in production


@app.post("/hooks/wthaiq")
def handle() -> tuple[str, int] | dict[str, bool]:
    try:
        event = wthaiq.Webhook.construct_event(
            request.get_data(), request.headers.get("Wthaiq-Signature"), endpoint_secret
        )
    except wthaiq.error.SignatureVerificationError:
        return "invalid signature", 400
    if event.id in seen:  # deliveries can repeat
        return {"received": True}
    seen.add(event.id)
    if event.type == "signature_request.completed":
        sr = event.data.object
        print("completed:", sr.id, sr.reference)
    elif event.type == "signer.signed":
        print("signed:", event.data.object.name, event.data.object.signature_request)
    return {"received": True}

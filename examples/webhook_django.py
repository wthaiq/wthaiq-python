"""Receive webhooks with Django: add the view to your urls.py.

path("hooks/wthaiq", webhook_django.wthaiq_webhook)
"""

from __future__ import annotations

import os

from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

import wthaiq

endpoint_secret = os.environ["WTHAIQ_WEBHOOK_SECRET"]


@csrf_exempt
@require_POST
def wthaiq_webhook(request: HttpRequest) -> HttpResponse:
    try:
        event = wthaiq.Webhook.construct_event(
            request.body, request.headers.get("Wthaiq-Signature"), endpoint_secret
        )
    except wthaiq.SignatureVerificationError:
        return HttpResponseBadRequest("invalid signature")
    if event.type == "signature_request.completed":
        print("completed:", event.data.object.id)
    return HttpResponse(status=200)

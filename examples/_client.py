"""Shared client for the examples.

Set ``WTHAIQ_API_KEY`` (use a test key, ``sk_test_...``) and optionally ``WTHAIQ_API_BASE``.
"""

from __future__ import annotations

import os

import wthaiq


def client() -> wthaiq.Client:
    return wthaiq.Client(
        os.environ.get("WTHAIQ_API_KEY"),
        base_url=os.environ.get("WTHAIQ_API_BASE", wthaiq.DEFAULT_BASE_URL),
        app_info={"name": "wthaiq-python-examples"},
    )

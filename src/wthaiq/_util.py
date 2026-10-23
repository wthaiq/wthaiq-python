from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import re
import uuid
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlencode

from .error import InvalidArgumentError


def new_idempotency_key() -> str:
    return str(uuid.uuid4())


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def equal_hex(a: str, b: str) -> bool:
    return hmac.compare_digest(a.strip().lower().encode(), b.strip().lower().encode())


def looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


def _scalar(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (_dt.datetime, _dt.date)):
        if not isinstance(value, _dt.datetime):
            value = _dt.datetime(value.year, value.month, value.day, tzinfo=_dt.timezone.utc)
        elif value.tzinfo is None:
            value = value.replace(tzinfo=_dt.timezone.utc)
        return str(int(value.timestamp()))
    if isinstance(value, (str, int, float)):
        return str(value)
    raise InvalidArgumentError(
        f'The query parameter "{key}" must be a string, number, boolean, date or datetime.'
    )


def encode_query(params: Mapping[str, Any]) -> str:
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            pairs.extend((f"{key}[]", _scalar(key, item)) for item in value)
        else:
            pairs.append((key, _scalar(key, value)))
    return urlencode(pairs)


def encode_json(params: Mapping[str, Any] | None) -> bytes:
    if params is None:
        return b"{}"
    if not isinstance(params, Mapping):
        raise InvalidArgumentError("The request parameters must be a mapping (dict).")
    try:
        text = json.dumps(dict(params), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidArgumentError(
            f"The request parameters cannot be encoded as JSON: {exc}"
        ) from exc
    return text.encode("utf-8")


def build_path(template: str, *ids: object) -> str:
    parts = template.split("{}")
    if len(parts) != len(ids) + 1:
        raise AssertionError("path template and ids do not match")
    out = parts[0]
    for value, rest in zip(ids, parts[1:], strict=True):
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise InvalidArgumentError("The object id must be a non-empty string.")
        text = str(value).strip()
        if text == "":
            raise InvalidArgumentError("The object id must be a non-empty string.")
        out += quote(text, safe="") + rest
    return out


_FILENAME_STAR = re.compile(r"filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)")
_FILENAME = re.compile(r'filename\s*=\s*"([^"]*)"|filename\s*=\s*([^;]+)')


def filename_from_disposition(header: str | None) -> str | None:
    if not header:
        return None
    from urllib.parse import unquote

    star = _FILENAME_STAR.search(header)
    if star:
        return unquote(star.group(1).strip())
    plain = _FILENAME.search(header)
    if plain:
        value = plain.group(1) if plain.group(1) is not None else plain.group(2)
        return value.strip() if value is not None else None
    return None

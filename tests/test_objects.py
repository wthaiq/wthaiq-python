from __future__ import annotations

import copy
import json
import pickle

import pytest

import wthaiq
from wthaiq import objects

from .conftest import SIGNATURE_REQUEST


def build() -> objects.SignatureRequest:
    return objects.SignatureRequest(SIGNATURE_REQUEST)


def test_attribute_and_item_access() -> None:
    sr = build()
    assert sr.id == "sr_cd5a6eb8468344583538"
    assert sr["status"] == "draft"
    assert sr.get("status") == "draft"
    assert sr.get("missing", "x") == "x"
    assert "title" in sr
    assert "missing" not in sr
    assert set(sr.keys()) == set(SIGNATURE_REQUEST)
    with pytest.raises(KeyError):
        sr["missing"]


def test_declared_absent_fields_are_none_and_unknown_fields_raise() -> None:
    sr = build()
    assert sr.vendor_data is None
    assert sr.channel is None
    with pytest.raises(AttributeError):
        sr.not_a_field  # noqa: B018
    assert not hasattr(sr, "not_a_field")


def test_new_api_fields_stay_readable() -> None:
    sr = objects.SignatureRequest({**SIGNATURE_REQUEST, "brand_new": {"nested": [1, {"a": 2}]}})
    assert sr.brand_new.nested[1].a == 2
    assert "brand_new" in dir(sr)


def test_objects_are_read_only() -> None:
    sr = build()
    with pytest.raises(AttributeError):
        sr.status = "sent"
    with pytest.raises(AttributeError):
        del sr.status
    with pytest.raises(TypeError):
        hash(sr)


def test_to_dict_round_trip() -> None:
    sr = build()
    assert sr.to_dict() == SIGNATURE_REQUEST
    assert json.loads(sr.to_json()) == SIGNATURE_REQUEST
    assert "عقد خدمات" in sr.to_json(indent=2)
    assert sr == SIGNATURE_REQUEST
    assert sr == build()
    assert sr != objects.WthaiqObject(SIGNATURE_REQUEST)
    assert sr != 3


def test_registry_and_generic_objects() -> None:
    converted = objects.convert({"object": "signer", "id": "sgr_1"})
    assert type(converted) is objects.Signer
    unknown = objects.convert({"object": "something_new", "id": "x_1"})
    assert type(unknown) is objects.WthaiqObject
    assert unknown.id == "x_1"
    assert objects.convert([{"object": "flow"}, 3, "s"])[1:] == [3, "s"]
    assert type(objects.convert({"object": {"not": "a name"}})) is objects.WthaiqObject


def test_pickle_and_copy() -> None:
    sr = build()
    for clone in (pickle.loads(pickle.dumps(sr)), copy.copy(sr), copy.deepcopy(sr)):
        assert type(clone) is objects.SignatureRequest
        assert clone == sr
        assert isinstance(clone.signers[0], objects.Signer)


def test_repr_masks_webhook_secret() -> None:
    endpoint = objects.WebhookEndpoint(
        {"id": "we_1", "object": "webhook_endpoint", "secret": "whsec_" + "f" * 48}
    )
    assert endpoint.secret == "whsec_" + "f" * 48
    assert "f" * 10 not in repr(endpoint)
    assert "f" * 10 not in str(endpoint)
    assert repr(endpoint).startswith("<WebhookEndpoint id='we_1'>")
    assert repr(objects.Money({"amount": 1})).startswith("<Money>")


def test_response_info_defaults() -> None:
    info = objects.ResponseInfo(200)
    assert info.request_id is None
    assert info.api_version is None
    assert info.rate_limit is None
    assert build().last_response is None


def test_pdf_file_is_bytes() -> None:
    pdf = objects.PdfFile(b"%PDF-1.7", sha256="ab", filename="a.pdf")
    assert pdf == b"%PDF-1.7"
    assert isinstance(pdf, bytes)
    assert pdf.filename == "a.pdf"
    assert pickle.loads(pickle.dumps(pdf)) == b"%PDF-1.7"


def test_top_level_exports() -> None:
    assert wthaiq.PermissionError is wthaiq.PermissionDeniedError
    assert "PermissionError" not in wthaiq.__all__
    for name in wthaiq.__all__:
        assert hasattr(wthaiq, name), name
    assert len(wthaiq.EVENT_TYPES) == 21
    assert "signer.identity_match_hold" in wthaiq.EVENT_TYPES
    assert "signer.identity_match_decided" in wthaiq.EVENT_TYPES

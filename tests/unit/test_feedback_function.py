from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock


class ConditionalCheckFailedException(Exception):
    pass


def _load_handler(monkeypatch):
    table = Mock()
    table.meta.client.exceptions.ConditionalCheckFailedException = ConditionalCheckFailedException
    ses = Mock()
    boto3 = Mock()
    boto3.resource.return_value.Table.return_value = table
    boto3.client.return_value = ses
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setenv("FEEDBACK_TABLE", "feedback-test")
    monkeypatch.setenv("FEEDBACK_EMAIL", "feedback@example.com")
    spec = importlib.util.spec_from_file_location(
        "feedback_function", Path("terraform/functions/feedback.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, table, ses


def test_feedback_handler_stores_valid_submission(monkeypatch) -> None:
    module, table, ses = _load_handler(monkeypatch)
    result = module.handler(
        {
            "headers": {"origin": "https://thedailysportspage.com"},
            "body": json.dumps(
                {"category": "correction", "message": "The score is reversed.", "page": "/"}
            ),
        },
        None,
    )

    assert result["statusCode"] == 201
    assert json.loads(result["body"])["ok"] is True
    item = table.put_item.call_args.kwargs["Item"]
    assert item["message"] == "The score is reversed."
    assert item["expires_at"] > item["submitted_at"]
    notification = ses.send_email.call_args.kwargs
    assert notification["Content"]["Simple"]["Subject"]["Data"] == "TDSP feedback: correction"
    assert "The score is reversed." in notification["Content"]["Simple"]["Body"]["Text"]["Data"]
    rate = table.update_item.call_args.kwargs
    assert rate["ExpressionAttributeValues"][":limit"] == 3
    assert rate["Key"]["id"].startswith("rate#")


def test_feedback_handler_rejects_wrong_origin_and_invalid_message(monkeypatch) -> None:
    module, table, ses = _load_handler(monkeypatch)
    wrong_origin = module.handler(
        {"headers": {"origin": "https://example.com"}, "body": '{"message":"hello"}'}, None
    )
    too_short = module.handler(
        {"headers": {"origin": "https://thedailysportspage.com"}, "body": '{"message":"x"}'},
        None,
    )

    assert wrong_origin["statusCode"] == 403
    assert too_short["statusCode"] == 400
    table.put_item.assert_not_called()
    ses.send_email.assert_not_called()


def test_feedback_handler_limits_source_to_three_per_day(monkeypatch) -> None:
    module, table, ses = _load_handler(monkeypatch)
    table.update_item.side_effect = ConditionalCheckFailedException

    result = module.handler(
        {
            "headers": {
                "origin": "https://thedailysportspage.com",
                "cloudfront-viewer-address": "203.0.113.7:44321",
            },
            "body": '{"message":"One too many submissions"}',
        },
        None,
    )

    assert result["statusCode"] == 429
    assert "tomorrow" in json.loads(result["body"])["error"]
    table.put_item.assert_not_called()
    ses.send_email.assert_not_called()

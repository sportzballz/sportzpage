from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import Mock


def _load_handler(monkeypatch):
    table = Mock()
    boto3 = Mock()
    boto3.resource.return_value.Table.return_value = table
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.setenv("FEEDBACK_TABLE", "feedback-test")
    spec = importlib.util.spec_from_file_location(
        "feedback_function", Path("terraform/functions/feedback.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, table


def test_feedback_handler_stores_valid_submission(monkeypatch) -> None:
    module, table = _load_handler(monkeypatch)
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


def test_feedback_handler_rejects_wrong_origin_and_invalid_message(monkeypatch) -> None:
    module, table = _load_handler(monkeypatch)
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

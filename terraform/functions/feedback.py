import json
import os
import time
import uuid

import boto3


TABLE = boto3.resource("dynamodb").Table(os.environ["FEEDBACK_TABLE"])
ALLOWED_ORIGINS = {
    "https://thedailysportspage.com",
    "https://www.thedailysportspage.com",
}


def response(status, payload):
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json", "cache-control": "no-store"},
        "body": json.dumps(payload),
    }


def handler(event, _context):
    headers = {key.lower(): value for key, value in (event.get("headers") or {}).items()}
    if headers.get("origin") not in ALLOWED_ORIGINS:
        return response(403, {"ok": False, "error": "Origin not allowed."})

    try:
        payload = json.loads(event.get("body") or "{}")
    except (TypeError, json.JSONDecodeError):
        return response(400, {"ok": False, "error": "Invalid feedback."})

    # Hidden field: bots commonly fill every available input.
    if payload.get("website"):
        return response(200, {"ok": True})

    message = str(payload.get("message") or "").strip()
    category = str(payload.get("category") or "general").strip()[:40]
    page = str(payload.get("page") or "/").strip()[:500]
    if len(message) < 3 or len(message) > 3000:
        return response(400, {"ok": False, "error": "Feedback must be 3 to 3,000 characters."})

    now = int(time.time())
    TABLE.put_item(
        Item={
            "id": str(uuid.uuid4()),
            "submitted_at": now,
            "expires_at": now + (180 * 24 * 60 * 60),
            "category": category,
            "message": message,
            "page": page,
        }
    )
    return response(201, {"ok": True, "message": "Thanks for helping improve the page."})

import json
import hashlib
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import boto3


TABLE = boto3.resource("dynamodb").Table(os.environ["FEEDBACK_TABLE"])
SNS = boto3.client("sns")
FEEDBACK_TOPIC_ARN = os.environ["FEEDBACK_TOPIC_ARN"]
LOGGER = logging.getLogger(__name__)
EASTERN = ZoneInfo("America/New_York")
DAILY_LIMIT = 3
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
    source_address = headers.get("cloudfront-viewer-address") or (
        event.get("requestContext", {}).get("http", {}).get("sourceIp", "unknown")
    )
    source_ip = source_address.rsplit(":", 1)[0].strip("[]")
    current_day = datetime.now(EASTERN).date()
    source_hash = hashlib.sha256(f"{current_day}:{source_ip}".encode()).hexdigest()
    tomorrow = datetime.combine(current_day + timedelta(days=2), datetime.min.time(), EASTERN)
    try:
        TABLE.update_item(
            Key={"id": f"rate#{current_day.isoformat()}#{source_hash}"},
            UpdateExpression="ADD submission_count :one SET expires_at = :expiry",
            ConditionExpression=(
                "attribute_not_exists(submission_count) OR submission_count < :limit"
            ),
            ExpressionAttributeValues={
                ":one": 1,
                ":limit": DAILY_LIMIT,
                ":expiry": int(tomorrow.timestamp()),
            },
        )
    except TABLE.meta.client.exceptions.ConditionalCheckFailedException:
        return response(
            429,
            {
                "ok": False,
                "error": "You’ve reached today’s feedback limit. Please try again tomorrow.",
            },
        )

    feedback_id = str(uuid.uuid4())
    TABLE.put_item(
        Item={
            "id": feedback_id,
            "submitted_at": now,
            "expires_at": now + (180 * 24 * 60 * 60),
            "category": category,
            "message": message,
            "page": page,
        }
    )
    try:
        SNS.publish(
            TopicArn=FEEDBACK_TOPIC_ARN,
            Subject=f"TDSP feedback: {category}",
            Message=(
                f"New feedback was submitted to The Daily Sports Page.\n\n"
                f"Category: {category}\n"
                f"Page: {page}\n"
                f"Feedback ID: {feedback_id}\n\n"
                f"{message}"
            ),
        )
    except Exception:
        # Notification delivery must never discard an otherwise valid submission.
        LOGGER.exception("feedback stored but notification publish failed")
    return response(201, {"ok": True, "message": "Thanks for helping improve the page."})

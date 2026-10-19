#!/usr/bin/env python3
"""Sends PayFlow webhook events from a JSON file to your service.

Behaves like PayFlow: signs every request and retries failed deliveries.

    python3 PayFlowEventsSender.py happy_path.json
    python3 PayFlowEventsSender.py happy_path.json --url http://localhost:8000/webhooks --retries 3

Standard library only.
"""

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request


def sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deliver(url: str, secret: str, event: dict) -> tuple[int, str]:
    body = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-PayFlow-Signature": sign(secret, body),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.read().decode(errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(errors="replace")
    except (urllib.error.URLError, TimeoutError) as error:
        return 0, str(error)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("events_file")
    parser.add_argument("--url", default="http://localhost:8000/webhooks")
    parser.add_argument("--secret", default="whsec_test_123")
    parser.add_argument("--retries", type=int, default=3, help="extra attempts after a failed delivery")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="seconds between attempts")
    args = parser.parse_args()

    with open(args.events_file, encoding="utf-8") as f:
        events = json.load(f)

    failed = 0
    for event in events:
        for attempt in range(1, args.retries + 2):
            status, body = deliver(args.url, args.secret, event)
            print(f"{event['id']:<12} {event['type']:<24} attempt {attempt}: {status} {body[:200]}")
            if 200 <= status < 300:
                break
            time.sleep(args.retry_delay)
        else:
            failed += 1

    print(f"\nDelivered {len(events) - failed}/{len(events)} events")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
alysis-login — get a gateway key (slk_...) from Alysis Code via device flow.

Standalone: stdlib Python only, the alysis-code CLI is NOT required.

Usage:
    python3 alysis-login.py            # login / refresh key
    python3 alysis-login.py --show     # print the stored key
    python3 alysis-login.py --revoke   # revoke the key server-side + delete locally

The key is stored at ~/.config/alysis-code/key.txt with mode 600.

Important notes (from reverse-engineering + live verification):
  - `slk_` keys are LONG-LIVED: there is no expiry date.
    Access only ends when the key is revoked (server-side logout).
  - What gets metered is the ACCOUNT CREDIT, not key lifetime:
      50 free credits, refilled every 30 days (from the last refill).
      Unused credits expire, no carry-over.
      Burst limits: max 10 credits / 5 hours, 25 credits / 7 days.
  - Remaining credit can ONLY be checked at https://alysiscode.com/account
    (the gateway has no status endpoint).
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

SUPABASE_URL = "https://vzigujbcjjmpntxhmyvr.supabase.co"
SITE_URL = "https://alysiscode.com"

# Public anon key — not a secret, it ships bundled with their website.
ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ6aWd1amJjamptcG50eGhteXZyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODA5Mzc0NTIsImV4cCI6MjA5NjUxMzQ1Mn0."
    "vLH9q-BNO8IWIZrVlvCw8pZWXdLgmKG4Tl9toTTD3pg"
)

DEVICE_CODE_URL = f"{SUPABASE_URL}/functions/v1/device-code"
DEVICE_TOKEN_URL = f"{SUPABASE_URL}/functions/v1/device-token"
GATEWAY_BASE = f"{SUPABASE_URL}/functions/v1/llm/v1"
REVOKE_URL = f"{GATEWAY_BASE}/logout"
ACCOUNT_URL = f"{SITE_URL}/account"

KEY_DIR = Path.home() / ".config" / "alysis-code"
KEY_FILE = KEY_DIR / "key.txt"

HTTP_TIMEOUT_S = 15.0


def post_json(url: str, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {ANON_KEY}",
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            parsed = json.loads(exc.read().decode())
            err = parsed.get("error", parsed)
            detail = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            pass
        raise RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connection failed: {exc.reason}") from exc
    if not isinstance(body, dict):
        raise RuntimeError("Response is not a JSON object")
    return body


def request_device_code() -> dict:
    client_name = f"alysis-login @ {platform.node() or 'unknown'}"[:80]
    body = post_json(DEVICE_CODE_URL, {"client_name": client_name})
    device_code = str(body.get("device_code") or "").strip()
    user_code = str(body.get("user_code") or "").strip()
    if not device_code or not user_code:
        raise RuntimeError(f"Incomplete response: {body}")
    return {
        "device_code": device_code,
        "user_code": user_code,
        # `or <default>` guards against the key being present but null.
        "interval": max(float(body.get("interval") or 5), 1.0),
        "expires_in": max(float(body.get("expires_in") or 900), 1.0),
    }


def poll_for_key(device_code: str, interval: float, expires_in: float) -> str:
    deadline = time.monotonic() + expires_in
    first = True
    while True:
        try:
            body = post_json(DEVICE_TOKEN_URL, {"device_code": device_code})
        except RuntimeError as exc:
            # Tolerate transient network errors while there is still time
            # left; a single WiFi/DNS blip should not kill a 15-min wait.
            remaining = deadline - time.monotonic()
            if remaining <= 1:
                raise
            print(f"    [polling] transient error, retrying: {exc}", file=sys.stderr)
            time.sleep(min(interval, remaining))
            continue

        status = str(body.get("status") or "").strip().lower()

        if status == "approved":
            key = str(body.get("key") or "").strip()
            if not key:
                raise RuntimeError("Approved but the key is empty")
            return key
        if status == "denied":
            raise RuntimeError("Login was denied on the website")
        if status in ("expired", "not_found", "already_claimed"):
            raise RuntimeError(f"Code expired / already used ({status})")
        if status == "slow_down":
            # Back off before the server starts blocking us.
            interval = min(interval + 5.0, 30.0)
            continue

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Timed out waiting for approval (15 minutes)")
        if first:
            print("    [polling] status=pending, waiting for approval in the browser...")
            first = False
        time.sleep(min(interval, remaining))


def save_key(key: str) -> Path:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    KEY_DIR.chmod(0o700)
    # Create the file with mode 600 atomically — no window where it is
    # world-readable between write_text() and chmod().
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(key + "\n")
    KEY_FILE.chmod(0o600)
    return KEY_FILE


def load_key() -> str | None:
    try:
        return KEY_FILE.read_text().strip() or None
    except OSError:
        return None


def cmd_show() -> int:
    key = load_key()
    if not key:
        print(f"No key stored at {KEY_FILE}")
        print("Run: python3 alysis-login.py")
        return 1
    print(key)
    print(f"\n(file: {KEY_FILE})")
    print("\nUsage:")
    print(f"  export ALYSIS_API_KEY={key}")
    print(f"  # base URL: {GATEWAY_BASE}")
    print(f"  # remaining credit: {ACCOUNT_URL}")
    return 0


def cmd_revoke() -> int:
    key = load_key()
    if not key:
        print("No stored key to revoke.")
        return 1
    try:
        req = urllib.request.Request(
            REVOKE_URL,
            data=b"{}",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S).close()
        print("Key revoked on the server.")
    except Exception as exc:
        print(f"Server-side revoke failed (best-effort): {exc}")
    KEY_FILE.unlink(missing_ok=True)
    print(f"Local key deleted: {KEY_FILE}")
    return 0


def cmd_login() -> int:
    print("=" * 62)
    print("  Alysis Code — device login (no alysis-code install needed)")
    print("=" * 62)

    grant = request_device_code()
    activate_url = f"{SITE_URL}/activate?code={grant['user_code']}"

    print(f"\n  Code : {grant['user_code']}")
    print(f"  Link : {activate_url}\n")
    print("  Open the link above, log in, then approve.\n")

    try:
        webbrowser.open(activate_url)
        print("  (your browser should open automatically)")
    except Exception:
        print("  (open the link manually)")

    print("\n[waiting] waiting for approval (15 minute timeout)...")
    key = poll_for_key(grant["device_code"], grant["interval"], grant["expires_in"])

    path = save_key(key)
    print("\n  Approved. Key saved.\n")
    print(f"  Preview : {key[:12]}...{key[-4:]}  ({len(key)} chars)")
    print(f"  File    : {path}  (mode 600)")
    print("\n" + "=" * 62)
    print("  Usage:")
    print(f"    export ALYSIS_API_KEY=$(cat {path})")
    print(f"    base_url: {GATEWAY_BASE}")
    print(f"  Remaining credit: {ACCOUNT_URL}")
    print("=" * 62)
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--show" in args:
        return cmd_show()
    if "--revoke" in args:
        return cmd_revoke()
    if args and args[0] not in ("--login", "-l"):
        print(__doc__)
        return 2
    try:
        return cmd_login()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except Exception as exc:
        print(f"\nERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

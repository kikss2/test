#!/usr/bin/env python3
"""
Crunchyroll Watchlist Importer
Reads a JSON produced by crunchyroll_export.py and re-adds each watchlist
title to a DIFFERENT (target) account.

Note: only the watchlist can be transferred. Watch-history playback
positions are read-only and cannot be written back via the API.
"""

import json
import sys
import glob
import getpass
import base64
import uuid
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("Missing dependency: requests\nInstall with: pip install requests")
    sys.exit(1)


# ── Crunchyroll API constants (same as the exporter) ───────────────────────────

CR_BASE     = "https://www.crunchyroll.com"
CR_AUTH_URL = f"{CR_BASE}/auth/v1/token"

CR_CLIENT_ID     = "noaihdevm_6iyg0a8l0q"
CR_CLIENT_SECRET = ""

DEVICE_ID = str(uuid.uuid4())
LOCALE    = "en-US"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}


# ── Auth (mirrors the exporter) ────────────────────────────────────────────────

def _basic_creds() -> str:
    return base64.b64encode(f"{CR_CLIENT_ID}:{CR_CLIENT_SECRET}".encode()).decode()


def get_token_from_etp_rt(etp_rt: str) -> dict:
    resp = requests.post(
        CR_AUTH_URL,
        headers={
            **HEADERS,
            "Authorization": f"Basic {_basic_creds()}",
            "Content-Type":  "application/x-www-form-urlencoded",
            "Cookie":        f"etp_rt={etp_rt}",
        },
        data={"grant_type": "etp_rt_cookie", "scope": "offline_access"},
        timeout=15,
    )
    if resp.status_code in (400, 401):
        print(f"\n[!] etp_rt token rejected ({resp.status_code}). Re-copy the full cookie value.")
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def get_token(username: str, password: str) -> dict:
    resp = requests.post(
        CR_AUTH_URL,
        headers={
            **HEADERS,
            "Authorization": f"Basic {_basic_creds()}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        data={
            "username":   username,
            "password":   password,
            "grant_type": "password",
            "scope":      "offline_access",
            "device_id":  DEVICE_ID,
        },
        timeout=15,
    )
    if resp.status_code == 401:
        print("\n[!] Login failed (401): wrong email/password, or social-login account.")
        print("    For Google/Facebook/Apple accounts, choose option 2 (etp_rt cookie).")
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


def print_etp_rt_instructions():
    print("""
──────────────────────────────────────────────────────────
Get the TARGET account's etp_rt cookie:

  1. Log in to crunchyroll.com in Chrome as the NEW account.
  2. Open DevTools (Ctrl+Shift+I) → "Application" tab.
  3. Left sidebar: Storage → Cookies → https://www.crunchyroll.com
  4. Find the row named  etp_rt  and copy its Value.
  5. Paste it below.
──────────────────────────────────────────────────────────
""")


def auth_headers_from(token_data: dict) -> dict:
    return {**HEADERS, "Authorization": f"Bearer {token_data['access_token']}"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def pick_export_file() -> str:
    files = sorted(glob.glob("crunchyroll_export_*.json"), reverse=True)
    if not files:
        path = input("Path to your export JSON file: ").strip().strip('"')
        return path
    print("Found export file(s):")
    for i, f in enumerate(files, 1):
        print(f"  {i}) {f}")
    sel = input(f"Use which? [1-{len(files)}, default 1]: ").strip()
    if not sel:
        return files[0]
    try:
        return files[int(sel) - 1]
    except (ValueError, IndexError):
        return files[0]


def extract_entries(watchlist: list) -> list:
    """
    Normalise watchlist items into (content_id, title) pairs.
    The export's watchlist items can carry the id in several shapes,
    so we try the common locations.
    """
    entries = []
    for item in watchlist:
        panel = item.get("panel") or {}
        cid = (
            item.get("content_id")
            or panel.get("id")
            or item.get("id")
            or ""
        )
        title = (
            panel.get("title")
            or item.get("title")
            or cid
        )
        if cid:
            entries.append((cid, title))
    return entries


def add_to_watchlist(auth_headers: dict, account_id: str, content_id: str) -> int:
    """Returns an HTTP-like status: 200 added, 409 already there, other = error."""
    url = f"{CR_BASE}/content/v2/{account_id}/watchlist"
    resp = requests.post(
        url,
        headers={**auth_headers, "Content-Type": "application/json"},
        params={"locale": LOCALE},
        json={"content_id": content_id},
        timeout=15,
    )
    return resp.status_code


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== Crunchyroll Watchlist Importer ===\n")
    print("This adds your exported watchlist titles to a DIFFERENT (target) account.\n")

    # 1. Load the export
    export_path = pick_export_file()
    try:
        with open(export_path, encoding="utf-8") as f:
            export = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Could not read export file: {e}")
        sys.exit(1)

    entries = extract_entries(export.get("watchlist", []))
    print(f"\nLoaded {len(entries)} watchlist title(s) from {export_path}\n")
    if not entries:
        print("Nothing to import.")
        sys.exit(0)

    # 2. Authenticate to the TARGET account
    print("Now log in to the TARGET account (the one to receive the data).")
    print("  1) Email + Password")
    print("  2) Google / Facebook / Apple, OR not sure (uses etp_rt cookie)")
    choice = input("\nEnter 1 or 2: ").strip()

    print("\nAuthenticating…")
    try:
        if choice == "2":
            print_etp_rt_instructions()
            etp_rt = input("Paste the TARGET account's etp_rt cookie value: ").strip()
            token_data = get_token_from_etp_rt(etp_rt)
        else:
            username = input("Target account email: ").strip()
            password = getpass.getpass("Target account password: ")
            token_data = get_token(username, password)
    except requests.HTTPError as e:
        print(f"Login failed: {e.response.status_code} – {e.response.text}")
        sys.exit(1)

    auth_headers = auth_headers_from(token_data)
    account_id   = token_data.get("account_id") or token_data.get("sub", "")
    print(f"Logged in to target. Account ID: {account_id}\n")

    # Safety check: don't import into the same account you exported from
    src_id = export.get("account_id", "")
    if src_id and src_id == account_id:
        print("[!] The target account is the SAME as the source account.")
        cont = input("    Continue anyway? [y/N]: ").strip().lower()
        if cont != "y":
            print("Aborted.")
            sys.exit(0)

    # 3. Add each title
    added = skipped = failed = 0
    fail_log = []
    print("Importing…")
    for i, (cid, title) in enumerate(entries, 1):
        try:
            status = add_to_watchlist(auth_headers, account_id, cid)
        except requests.RequestException as e:
            status = -1
            fail_log.append((title, cid, str(e)))

        if status in (200, 201):
            added += 1
            mark = "+ added"
        elif status == 409:
            skipped += 1
            mark = "= already there"
        else:
            failed += 1
            mark = f"! failed ({status})"
            if status != -1:
                fail_log.append((title, cid, f"HTTP {status}"))

        print(f"  [{i}/{len(entries)}] {mark}: {title}")
        time.sleep(0.4)   # be polite to the API

    # 4. Summary
    print("\n──────────── Import complete ────────────")
    print(f"  Added:        {added}")
    print(f"  Already there:{skipped}")
    print(f"  Failed:       {failed}")
    if fail_log:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = f"import_failures_{ts}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(
                [{"title": t, "content_id": c, "error": e} for t, c, e in fail_log],
                f, ensure_ascii=False, indent=2,
            )
        print(f"\n  Failure details written to: {log_path}")


if __name__ == "__main__":
    main()

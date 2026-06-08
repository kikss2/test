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
    """
    Exchange an etp_rt / refresh_token UUID for a fresh access token.
    Tries the cookie grant first, then the explicit refresh_token grant.
    """
    base = {
        **HEADERS,
        "Authorization": f"Basic {_basic_creds()}",
        "Content-Type":  "application/x-www-form-urlencoded",
    }

    # Attempt 1: etp_rt_cookie grant (how the web app refreshes)
    resp = requests.post(
        CR_AUTH_URL,
        headers={**base, "Cookie": f"etp_rt={etp_rt}"},
        data={"grant_type": "etp_rt_cookie", "scope": "offline_access"},
        timeout=15,
    )
    if resp.status_code == 200:
        return resp.json()

    # Attempt 2: explicit refresh_token grant
    resp2 = requests.post(
        CR_AUTH_URL,
        headers=base,
        data={
            "grant_type":    "refresh_token",
            "refresh_token": etp_rt,
            "scope":         "offline_access",
        },
        timeout=15,
    )
    if resp2.status_code == 200:
        return resp2.json()

    print(f"\n[!] Token rejected (cookie grant {resp.status_code}, "
          f"refresh grant {resp2.status_code}).")
    print("    Paste the 'refresh_token' UUID from the token response Preview,")
    print("    e.g. 2c4ce0f7-7567-41a3-9686-3d34e0b3a4d2 (NOT the long eyJ... token).")
    sys.exit(1)


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


def looks_like_jwt(value: str) -> bool:
    """A Bearer access token is a JWT: three base64 parts split by dots."""
    v = value.replace("Bearer ", "").strip()
    return v.startswith("eyJ") and v.count(".") == 2


def get_me(auth_headers: dict) -> dict:
    return get_json(f"{CR_BASE}/accounts/v1/me", auth_headers)


def get_json(url: str, auth_headers: dict, params: dict = None) -> dict:
    resp = requests.get(url, headers=auth_headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


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


def series_ref(item: dict):
    """
    Resolve a single export item (from watchlist or watch-history) down to the
    SERIES (or movie_listing) it belongs to, since that's what the watchlist
    endpoint accepts. Episodes/movies are mapped up to their parent.
    Returns (content_id, title) or (None, None) if it can't be resolved.
    """
    panel = item.get("panel") or item
    ptype = panel.get("type")
    ep    = panel.get("episode_metadata") or {}
    mv    = panel.get("movie_metadata")   or {}

    if ptype == "series":
        return panel.get("id"), panel.get("title")
    if ptype == "movie_listing":
        return panel.get("id"), panel.get("title")
    if ptype == "episode":
        return ep.get("series_id"), ep.get("series_title") or panel.get("title")
    if ptype == "movie":
        return mv.get("movie_listing_id"), mv.get("movie_listing_title") or panel.get("title")

    # Fallback: dig for a series id wherever it may be
    sid = (
        ep.get("series_id")
        or panel.get("series_id")
        or item.get("series_id")
        or item.get("content_id")
        or panel.get("id")
        or item.get("id")
    )
    title = ep.get("series_title") or panel.get("title") or item.get("title") or sid
    return sid, title


def collect_series(export: dict) -> list:
    """
    Build a de-duplicated list of (series_id, title) from BOTH the saved
    watchlist and the full watch history, so the target account ends up
    with every show the source account watched or bookmarked.
    """
    seen = {}
    order = []
    for source in ("watchlist", "watch_history"):
        for item in export.get(source, []):
            sid, title = series_ref(item)
            if sid and sid not in seen:
                seen[sid] = title
                order.append(sid)
    return [(sid, seen[sid]) for sid in order]


def add_to_watchlist(auth_headers: dict, account_id: str, content_id: str):
    """Returns (status_code, response_text)."""
    url = f"{CR_BASE}/content/v2/{account_id}/watchlist"
    resp = requests.post(
        url,
        headers={**auth_headers, "Content-Type": "application/json"},
        params={"locale": LOCALE},
        json={"content_id": content_id},
        timeout=15,
    )
    return resp.status_code, resp.text


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

    entries = collect_series(export)
    n_wl = len(export.get("watchlist", []))
    n_wh = len(export.get("watch_history", []))
    print(f"\nFrom {export_path}:")
    print(f"  Watchlist items:      {n_wl}")
    print(f"  Watch-history items:  {n_wh}")
    print(f"  → {len(entries)} unique series to add to the target account.\n")
    if not entries:
        print("Nothing to import.")
        sys.exit(0)

    # 2. Authenticate to the TARGET account
    print("Now log in to the TARGET account (the one to receive the data).")
    print("  1) Email + Password")
    print("  2) Google / Facebook / Apple, OR not sure (uses etp_rt cookie)")
    choice = input("\nEnter 1 or 2: ").strip()

    print("\nAuthenticating…")
    refresh_token = ""   # set when we can mint fresh access tokens later
    try:
        if choice == "2":
            print_etp_rt_instructions()
            pasted = input("Paste the TARGET account's etp_rt cookie (or Bearer token): ").strip()
            if looks_like_jwt(pasted):
                # User pasted a Bearer access-token JWT instead of the cookie.
                # Use it directly (note: these expire after ~5 minutes and
                # cannot be auto-refreshed).
                print("(Detected a Bearer access token — using it directly.)")
                print("  Tip: for many series, paste the 'refresh_token' UUID instead")
                print("  so the script can auto-refresh and won't expire mid-run.")
                token = pasted.replace("Bearer ", "").strip()
                auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"}
                me = get_me(auth_headers)
                account_id = me.get("account_id") or me.get("external_id", "")
            else:
                token_data    = get_token_from_etp_rt(pasted)
                auth_headers  = auth_headers_from(token_data)
                account_id    = token_data.get("account_id") or token_data.get("sub", "")
                refresh_token = token_data.get("refresh_token") or pasted
        else:
            username = input("Target account email: ").strip()
            password = getpass.getpass("Target account password: ")
            token_data    = get_token(username, password)
            auth_headers  = auth_headers_from(token_data)
            account_id    = token_data.get("account_id") or token_data.get("sub", "")
            refresh_token = token_data.get("refresh_token", "")
    except requests.HTTPError as e:
        code = e.response.status_code
        if code == 401:
            print("Login failed (401). If you pasted a Bearer token it has likely")
            print("expired — Bearer tokens last only a few minutes. Either paste a")
            print("fresh one, or better: copy the long-lived 'etp_rt' cookie value")
            print("(a short UUID, NOT the long eyJ... token).")
        else:
            print(f"Login failed: {code} – {e.response.text}")
        sys.exit(1)

    print(f"Logged in to target. Account ID: {account_id}\n")

    # Safety check: don't import into the same account you exported from
    src_id = export.get("account_id", "")
    if src_id and src_id == account_id:
        print("[!] The target account is the SAME as the source account.")
        cont = input("    Continue anyway? [y/N]: ").strip().lower()
        if cont != "y":
            print("Aborted.")
            sys.exit(0)

    # 3. Add each series
    added = skipped = failed = 0
    fail_log = []
    first_error_shown = False
    print("Importing…")
    for i, (cid, title) in enumerate(entries, 1):
        status, body = -1, ""
        try:
            status, body = add_to_watchlist(auth_headers, account_id, cid)

            # Access token expired mid-run → mint a fresh one and retry once.
            if status == 401 and refresh_token:
                token_data   = get_token_from_etp_rt(refresh_token)
                auth_headers = auth_headers_from(token_data)
                refresh_token = token_data.get("refresh_token") or refresh_token
                status, body = add_to_watchlist(auth_headers, account_id, cid)
        except requests.RequestException as e:
            body = str(e)

        if status in (200, 201, 204):
            # 204 No Content is Crunchyroll's success response for this endpoint.
            added += 1
            mark = "+ added"
        elif status == 409:
            skipped += 1
            mark = "= already in list"
        else:
            failed += 1
            mark = f"! failed ({status})"
            fail_log.append((title, cid, f"HTTP {status}: {body[:200]}"))
            if not first_error_shown:
                # Surface the first failure's body to aid debugging.
                print(f"      ↳ server said: {body[:300]}")
                first_error_shown = True

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

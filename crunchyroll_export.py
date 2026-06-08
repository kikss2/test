#!/usr/bin/env python3
"""
Crunchyroll Account Data Exporter
Exports your watch history, watchlist, profile, and favorites to JSON.
"""

import json
import sys
import getpass
import base64
import uuid
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("Missing dependency: requests\nInstall with: pip install requests")
    sys.exit(1)


# ── Crunchyroll API constants ──────────────────────────────────────────────────

CR_BASE     = "https://beta-api.crunchyroll.com"
CR_AUTH_URL = f"{CR_BASE}/auth/v1/token"

# Android app client credentials (public, from the official APK)
CR_CLIENT_ID     = "cr_android"
CR_CLIENT_SECRET = "ouMuaBdMOqPyjQkFT7MbIhH0N4OTBgFsrOFajFqmvTI="

DEVICE_ID = str(uuid.uuid4())

HEADERS = {
    "User-Agent":   "Crunchyroll/3.46.1 Android/13 okhttp/4.12.0",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept":       "application/json",
}


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_anon_token() -> str:
    """Get an anonymous ETP token first — required before password login."""
    creds = base64.b64encode(
        f"{CR_CLIENT_ID}:{CR_CLIENT_SECRET}".encode()
    ).decode()
    resp = requests.post(
        CR_AUTH_URL,
        headers={**HEADERS, "Authorization": f"Basic {creds}"},
        data={"grant_type": "client_id", "scope": "offline_access"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("access_token", "")


def get_token(username: str, password: str) -> dict:
    creds = base64.b64encode(
        f"{CR_CLIENT_ID}:{CR_CLIENT_SECRET}".encode()
    ).decode()

    # Step 1: anonymous token (needed as ETP-Anonymous header)
    anon_token = get_anon_token()

    # Step 2: exchange for a real user token
    resp = requests.post(
        CR_AUTH_URL,
        headers={
            **HEADERS,
            "Authorization":    f"Basic {creds}",
            "ETP-Anonymous-ID": DEVICE_ID,
        },
        data={
            "username":    username,
            "password":    password,
            "grant_type":  "password",
            "scope":       "offline_access",
            "device_id":   DEVICE_ID,
            "device_name": "Python exporter",
            "device_type": "com.crunchyroll.crunchyroid",
        },
        timeout=15,
    )

    if resp.status_code == 401:
        print("\n[!] Login failed (401).")
        print("    Possible reasons:")
        print("    - Wrong email or password")
        print("    - You signed up with Google/Facebook/Apple (social login)")
        print("      → In that case, see the instructions below to use a browser token instead.")
        print_browser_token_instructions()
        sys.exit(1)

    resp.raise_for_status()
    return resp.json()


def print_browser_token_instructions():
    print("""
──────────────────────────────────────────────────────────
If you use Google / Facebook / Apple login, do this instead:

  1. Open Chrome/Firefox and log in to crunchyroll.com
  2. Press F12 → go to the "Network" tab
  3. Refresh the page, then click any request to crunchyroll.com
  4. Look at the Request Headers for:  Authorization: Bearer <token>
  5. Copy that token and paste it when prompted below.
──────────────────────────────────────────────────────────
""")


def bearer(token_data: dict) -> dict:
    return {**HEADERS, "Authorization": f"Bearer {token_data['access_token']}"}


# ── API helpers ────────────────────────────────────────────────────────────────

def get_json(url: str, auth_headers: dict, params: dict = None) -> dict:
    resp = requests.get(url, headers=auth_headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def paginate(url: str, auth_headers: dict, extra_params: dict = None, page_size: int = 100) -> list:
    """Fetch all pages of a paginated endpoint."""
    results = []
    start = 0
    while True:
        params = {"n": page_size, "start": start, **(extra_params or {})}
        data = get_json(url, auth_headers, params)
        items = data.get("items") or data.get("data") or []
        results.extend(items)
        total = data.get("total", len(results))
        start += len(items)
        if start >= total or not items:
            break
        time.sleep(0.3)   # be polite to the API
    return results


# ── Data fetchers ──────────────────────────────────────────────────────────────

def fetch_profile(auth_headers: dict) -> dict:
    profile  = get_json(f"{CR_BASE}/accounts/v1/me/profile", auth_headers)
    me       = get_json(f"{CR_BASE}/accounts/v1/me",         auth_headers)
    return {"account": me, "profile": profile}


def fetch_watchlist(auth_headers: dict, account_id: str) -> list:
    url = f"{CR_BASE}/content/v2/discover/{account_id}/watchlist"
    return paginate(url, auth_headers)


def fetch_watch_history(auth_headers: dict, account_id: str) -> list:
    url = f"{CR_BASE}/content/v2/{account_id}/watch-history"
    return paginate(url, auth_headers)


def fetch_favorites(auth_headers: dict, account_id: str) -> list:
    url = f"{CR_BASE}/content/v2/{account_id}/favorites"
    try:
        return paginate(url, auth_headers)
    except requests.HTTPError:
        return []   # endpoint not available for all accounts


def fetch_ratings(auth_headers: dict, account_id: str) -> list:
    url = f"{CR_BASE}/content/v2/{account_id}/rating"
    try:
        return paginate(url, auth_headers)
    except requests.HTTPError:
        return []


# ── Profile-level data (if the account has multiple profiles) ──────────────────

def fetch_profiles_list(auth_headers: dict, account_id: str) -> list:
    url = f"{CR_BASE}/accounts/v1/{account_id}/profiles"
    try:
        data = get_json(url, auth_headers)
        return data.get("items") or data.get("data") or []
    except requests.HTTPError:
        return []


def fetch_profile_watchlist(auth_headers: dict, account_id: str, profile_id: str) -> list:
    url = f"{CR_BASE}/content/v2/discover/{account_id}/watchlist"
    return paginate(url, auth_headers, extra_params={"profile_id": profile_id})


def fetch_profile_history(auth_headers: dict, account_id: str, profile_id: str) -> list:
    url = f"{CR_BASE}/content/v2/{account_id}/watch-history"
    return paginate(url, auth_headers, extra_params={"profile_id": profile_id})


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== Crunchyroll Account Exporter ===\n")
    print("How do you log in to Crunchyroll?")
    print("  1) Email + Password")
    print("  2) Google / Facebook / Apple (social login) → needs browser token")
    choice = input("\nEnter 1 or 2: ").strip()

    auth_headers = {}
    account_id   = ""

    if choice == "2":
        print_browser_token_instructions()
        raw_token = input("Paste your Bearer token here: ").strip()
        raw_token = raw_token.replace("Bearer ", "").strip()
        auth_headers = {**HEADERS, "Authorization": f"Bearer {raw_token}"}
        # Fetch account_id from the token itself
        try:
            me = get_json(f"{CR_BASE}/accounts/v1/me", auth_headers)
            account_id = me.get("account_id") or me.get("external_id", "")
        except requests.HTTPError as e:
            print(f"Token rejected: {e.response.status_code}. Make sure you copied the full token.")
            sys.exit(1)
    else:
        print("\nYour credentials are used ONLY for authentication and are never stored.\n")
        username = input("Crunchyroll email: ").strip()
        password = getpass.getpass("Password: ")

        print("\nAuthenticating…")
        try:
            token_data   = get_token(username, password)
            auth_headers = bearer(token_data)
            account_id   = token_data.get("account_id") or token_data.get("sub", "")
        except requests.HTTPError as e:
            print(f"Login failed: {e.response.status_code} – {e.response.text}")
            sys.exit(1)
    print(f"Logged in. Account ID: {account_id}\n")

    export = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "account_id":  account_id,
    }

    print("Fetching account/profile info…")
    export["account_info"] = fetch_profile(auth_headers)

    print("Fetching watchlist…")
    export["watchlist"] = fetch_watchlist(auth_headers, account_id)
    print(f"  {len(export['watchlist'])} items")

    print("Fetching watch history…")
    export["watch_history"] = fetch_watch_history(auth_headers, account_id)
    print(f"  {len(export['watch_history'])} items")

    print("Fetching favorites…")
    export["favorites"] = fetch_favorites(auth_headers, account_id)
    print(f"  {len(export['favorites'])} items")

    print("Fetching ratings…")
    export["ratings"] = fetch_ratings(auth_headers, account_id)
    print(f"  {len(export['ratings'])} items")

    # Per-profile data (multi-profile accounts)
    print("Checking for sub-profiles…")
    profiles = fetch_profiles_list(auth_headers, account_id)
    if profiles:
        print(f"  Found {len(profiles)} sub-profile(s)")
        export["profiles"] = []
        for prof in profiles:
            pid  = prof.get("profile_id") or prof.get("id", "")
            name = prof.get("profile_name") or prof.get("username", pid)
            print(f"  Fetching data for profile '{name}'…")
            export["profiles"].append({
                "profile_meta":    prof,
                "watchlist":       fetch_profile_watchlist(auth_headers, account_id, pid),
                "watch_history":   fetch_profile_history(auth_headers, account_id, pid),
            })
    else:
        export["profiles"] = []

    # Write output
    timestamp   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_file = f"crunchyroll_export_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)

    print(f"\nExport saved to: {output_file}")
    print(f"Total size: {len(json.dumps(export)) / 1024:.1f} KB")
    print("\nWhat's included:")
    print(f"  - Account & profile info")
    print(f"  - {len(export['watchlist'])} watchlist entries")
    print(f"  - {len(export['watch_history'])} watch history entries")
    print(f"  - {len(export['favorites'])} favorites")
    print(f"  - {len(export['ratings'])} ratings")
    if export["profiles"]:
        print(f"  - {len(export['profiles'])} sub-profile(s) with their own data")


if __name__ == "__main__":
    main()

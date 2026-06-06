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

# Public client credentials used by the official web/mobile app
CR_CLIENT_ID     = "cr_web"
CR_CLIENT_SECRET = "wo/n3pBHPFXdxDRdyHFRaQ=="   # public, bundled in the app

DEVICE_ID = str(uuid.uuid4())

HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Linux; Android 13) CrunchyrollApp/3.46.1",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept":       "application/json",
}


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_token(username: str, password: str) -> dict:
    creds = base64.b64encode(
        f"{CR_CLIENT_ID}:{CR_CLIENT_SECRET}".encode()
    ).decode()

    resp = requests.post(
        CR_AUTH_URL,
        headers={**HEADERS, "Authorization": f"Basic {creds}"},
        data={
            "username":   username,
            "password":   password,
            "grant_type": "password",
            "scope":      "offline_access",
            "device_id":  DEVICE_ID,
            "device_name": "Python exporter",
            "device_type": "com.crunchyroll.crunchyroid",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


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
    print("Your credentials are used ONLY for authentication and are never stored.\n")

    username = input("Crunchyroll email: ").strip()
    password = getpass.getpass("Password: ")

    print("\nAuthenticating…")
    try:
        token_data = get_token(username, password)
    except requests.HTTPError as e:
        print(f"Login failed: {e.response.status_code} – {e.response.text}")
        sys.exit(1)

    auth_headers = bearer(token_data)
    account_id   = token_data.get("account_id") or token_data.get("sub", "")
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

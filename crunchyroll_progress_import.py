#!/usr/bin/env python3
"""
Crunchyroll Watch-Progress Importer
Replays episode-level watch progress (playhead positions + watched state)
from a crunchyroll_export_*.json onto a DIFFERENT (target) account, using the
same /playheads write endpoint the official player uses.

Partially-watched episodes are restored to the exact second you left off.
Fully-watched episodes are pushed past the completion threshold so they show
as watched. Re-running is safe (idempotent) — each playhead is simply re-set.
"""

import json
import sys
import glob
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("Missing dependency: requests\nInstall with: pip install requests")
    sys.exit(1)


# ── Crunchyroll API constants ──────────────────────────────────────────────────

CR_BASE = "https://www.crunchyroll.com"
LOCALE  = "en-US"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}


# ── Auth ───────────────────────────────────────────────────────────────────────

def get_json(url: str, auth_headers: dict, params: dict = None) -> dict:
    resp = requests.get(url, headers=auth_headers, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def account_id_from_token(auth_headers: dict) -> str:
    me = get_json(f"{CR_BASE}/accounts/v1/me", auth_headers)
    return me.get("account_id") or me.get("external_id", "")


class Session:
    def __init__(self):
        self.headers    = {}
        self.account_id = ""

    def login_interactive(self):
        print("""
Get your Bearer token:
  1. In Chrome (logged into the NEW account), open DevTools → Network tab.
  2. Refresh the crunchyroll.com page.
  3. In the filter box type: token
  4. Click the 'token' request → Preview tab.
  5. Copy the full value of  access_token  (starts with eyJ...).
""")
        token = input("Paste the access_token here: ").strip()
        token = token.replace("Bearer ", "").strip()
        if not token.startswith("eyJ"):
            print("[!] That doesn't look like a Bearer token (should start with eyJ).")
            sys.exit(1)
        self.headers    = {**HEADERS, "Authorization": f"Bearer {token}"}
        self.account_id = account_id_from_token(self.headers)


# ── Playhead write ─────────────────────────────────────────────────────────────

def set_playhead(sess: Session, content_id: str, playhead: int):
    """POST a playhead; returns (status, text). Auto-refreshes once on 401."""
    url = f"{CR_BASE}/content/v2/{sess.account_id}/playheads"

    def _post():
        return requests.post(
            url,
            headers={**sess.headers, "Content-Type": "application/json"},
            params={"locale": LOCALE},
            json={"content_id": content_id, "playhead": int(playhead)},
            timeout=15,
        )

    resp = _post()
    return resp.status_code, resp.text


# ── History extraction ─────────────────────────────────────────────────────────

def extract_history(watch_history: list) -> list:
    """
    Turn watch-history items into (episode_id, target_playhead, label) records.
    target_playhead = recorded position, but for fully-watched episodes we push
    it to (duration - 2s) so the server marks them complete.
    """
    out = []
    for item in watch_history:
        panel = item.get("panel") or {}
        ep_id = item.get("content_id") or item.get("id") or panel.get("id")
        if not ep_id:
            continue

        playhead = int(item.get("playhead") or 0)
        fully    = bool(item.get("fully_watched"))
        meta     = panel.get("episode_metadata") or {}
        dur      = int((meta.get("duration_ms") or 0) // 1000)

        target = playhead
        if fully and dur > 5:
            target = max(target, dur - 2)     # ensure past the ~90% completion mark
        if dur > 0:
            target = min(target, dur)         # never exceed the episode length

        series = meta.get("series_title") or ""
        epno   = meta.get("episode_number")
        eptit  = panel.get("title") or ""
        label  = f"{series} — E{epno}: {eptit}" if series else eptit or ep_id

        out.append((ep_id, target, label, fully))
    return out


# ── Main ───────────────────────────────────────────────────────────────────────

def pick_export_file() -> str:
    files = sorted(glob.glob("crunchyroll_export_*.json"), reverse=True)
    if not files:
        return input("Path to your export JSON file: ").strip().strip('"')
    print("Found export file(s):")
    for i, f in enumerate(files, 1):
        print(f"  {i}) {f}")
    sel = input(f"Use which? [1-{len(files)}, default 1]: ").strip() or "1"
    try:
        return files[int(sel) - 1]
    except (ValueError, IndexError):
        return files[0]


def main():
    print("=== Crunchyroll Watch-Progress Importer ===\n")

    path = pick_export_file()
    try:
        with open(path, encoding="utf-8") as f:
            export = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Could not read export file: {e}")
        sys.exit(1)

    records = extract_history(export.get("watch_history", []))
    print(f"\nLoaded {len(records)} watched-episode record(s) from {path}\n")
    if not records:
        print("No watch history to import.")
        sys.exit(0)

    sess = Session()
    print("Authenticating…")
    try:
        sess.login_interactive()
    except requests.HTTPError as e:
        print(f"Login failed: {e.response.status_code} – {e.response.text}")
        sys.exit(1)
    print(f"Logged in to target. Account ID: {sess.account_id}\n")

    src_id = export.get("account_id", "")
    if src_id and src_id == sess.account_id:
        if input("[!] Target == source account. Continue anyway? [y/N]: ").strip().lower() != "y":
            print("Aborted.")
            sys.exit(0)

    ok = failed = 0
    fail_log = []
    first_error_shown = False
    print("Writing watch progress…")
    for i, (ep_id, target, label, fully) in enumerate(records, 1):
        try:
            status, body = set_playhead(sess, ep_id, target)
        except requests.RequestException as e:
            status, body = -1, str(e)

        if status in (200, 201, 204):
            ok += 1
            tag = "✓ watched" if fully else f"✓ @{target}s"
        else:
            failed += 1
            tag = f"✗ ({status})"
            fail_log.append({"episode": label, "content_id": ep_id,
                             "playhead": target, "error": f"HTTP {status}: {body[:150]}"})
            if not first_error_shown:
                print(f"      ↳ server said: {body[:300]}")
                first_error_shown = True

        if i % 25 == 0 or i == len(records):
            print(f"  [{i}/{len(records)}] {tag}: {label}")
        time.sleep(0.2)

    print("\n──────────── Progress import complete ────────────")
    print(f"  Restored: {ok}")
    print(f"  Failed:   {failed}")
    if fail_log:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        log_path = f"progress_failures_{ts}.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(fail_log, f, ensure_ascii=False, indent=2)
        print(f"  Failure details: {log_path}")
    print("\nOpen the new account → Home/Continue Watching to see your progress.")


if __name__ == "__main__":
    main()

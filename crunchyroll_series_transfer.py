#!/usr/bin/env python3
"""
Crunchyroll Per-Series Watch-Progress Transfer
================================================

Why this exists
---------------
Crunchyroll's bulk watch-history endpoint only returns roughly the last ~575
episodes you watched. Anything older than that window (e.g. a show you started
months ago like "Kill Blue") is NOT in the history feed, so the bulk
export/import can never see it.

This script bypasses that limit. For each show you name, it:
  1. searches for the series,
  2. lists EVERY episode of EVERY season,
  3. asks the API for the playhead (your exact position) of those specific
     episode IDs on the SOURCE account — a direct lookup with no depth limit,
  4. writes those same playheads onto the TARGET account.

So progress transfers correctly even for shows that fell out of the history
window.

Usage
-----
  python crunchyroll_series_transfer.py

You'll be asked for:
  • which shows to transfer (type names, or "all" to use the export watchlist),
  • the SOURCE account's access_token (to read progress),
  • the TARGET account's access_token (to write progress).

Both tokens are the long  eyJ...  value from Chrome DevTools:
  DevTools → Network → filter "token" → click it → Preview → copy access_token
Tokens last only ~5 minutes, so you'll grab the target token right before the
write phase. The script refreshes mid-run if a token expires.
"""

import json
import sys
import glob
import time

try:
    import requests
except ImportError:
    print("Missing dependency: requests\nInstall with: pip install requests")
    sys.exit(1)


# ── Constants ──────────────────────────────────────────────────────────────────

CR_BASE = "https://www.crunchyroll.com"
LOCALE  = "en-US"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

# How many content_ids to request per playheads GET (keep URLs sane).
PLAYHEAD_BATCH = 80


# ── Auth ───────────────────────────────────────────────────────────────────────

class Session:
    """One authenticated account (source or target)."""

    def __init__(self, role: str):
        self.role       = role          # "SOURCE" or "TARGET"
        self.headers    = {}
        self.account_id = ""

    def login_interactive(self):
        print(f"""
─────────────────────────────────────────────────────────────
Get the {self.role} account's access_token:
  1. In Chrome, logged into the {self.role} account, open DevTools (Ctrl+Shift+I).
  2. Go to the Network tab and refresh the crunchyroll.com page.
  3. In the filter box, type:  token
  4. Click the 'token' request → Preview tab.
  5. Copy the full value of  access_token  (starts with  eyJ... ).
─────────────────────────────────────────────────────────────""")
        token = input(f"Paste the {self.role} access_token: ").strip().replace("Bearer ", "").strip()
        if not token.startswith("eyJ"):
            print("[!] That doesn't look like an access token (should start with eyJ).")
            sys.exit(1)
        self.headers = {**HEADERS, "Authorization": f"Bearer {token}"}
        me = self._get("/accounts/v1/me")
        self.account_id = me.get("account_id") or me.get("external_id", "")
        print(f"    ↳ {self.role} logged in. Account ID: {self.account_id}")

    def refresh_token(self) -> bool:
        """Prompt for a fresh token mid-run (tokens expire after ~5 min)."""
        print(f"\n[!] {self.role} token expired. Grab a fresh one:")
        print("    Refresh crunchyroll.com → Network → 'token' → Preview → access_token")
        print("    (Press Enter alone to stop.)")
        token = input(f"Fresh {self.role} access_token: ").strip().replace("Bearer ", "").strip()
        if not token.startswith("eyJ"):
            return False
        self.headers = {**HEADERS, "Authorization": f"Bearer {token}"}
        print("    ↳ resuming…")
        return True

    # -- low level helpers, with one automatic token-refresh on 401 -------------

    def _get(self, path: str, params: dict = None, _retry=True):
        url = path if path.startswith("http") else CR_BASE + path
        resp = requests.get(url, headers=self.headers, params=params, timeout=20)
        if resp.status_code == 401 and _retry and self.refresh_token():
            return self._get(path, params, _retry=False)
        resp.raise_for_status()
        return resp.json()

    def get_optional(self, path: str, params: dict = None):
        """GET that returns None instead of raising on 4xx (for endpoints that
        don't exist for every title)."""
        try:
            return self._get(path, params)
        except requests.HTTPError:
            return None


# ── Source: resolve series → episodes → playheads ──────────────────────────────

def search_series(sess: Session, query: str) -> list:
    """Return candidate (id, title, type) tuples for a search query."""
    data = sess.get_optional(
        "/content/v2/discover/search",
        {"q": query, "n": 6, "type": "series,movie_listing", "locale": LOCALE},
    ) or {}
    out = []
    for group in data.get("data", []):
        for item in group.get("items", []):
            cid  = item.get("id")
            ttl  = item.get("title")
            typ  = item.get("type")
            if cid and typ in ("series", "movie_listing"):
                out.append((cid, ttl, typ))
    return out


def pick_series(candidates: list, query: str):
    """Prefer an exact (case-insensitive) title match, else the first result."""
    if not candidates:
        return None
    for cid, ttl, typ in candidates:
        if (ttl or "").strip().lower() == query.strip().lower():
            return cid, ttl, typ
    return candidates[0]


def list_episode_ids(sess: Session, series_id: str) -> list:
    """
    Return [(episode_id, label, duration_s), ...] for every episode of a series,
    across all seasons. Handles the content/v2 cms season/episode endpoints.
    """
    episodes = []

    seasons = sess.get_optional(f"/content/v2/cms/series/{series_id}/seasons",
                                {"locale": LOCALE}) or {}
    season_items = seasons.get("data") or seasons.get("items") or []

    # Some series expose episodes directly; most go season → episodes.
    if not season_items:
        direct = sess.get_optional(f"/content/v2/cms/series/{series_id}/episodes",
                                   {"locale": LOCALE}) or {}
        season_items = [{"id": None, "_episodes": direct.get("data", [])}]

    for season in season_items:
        sid = season.get("id")
        if sid:
            eps = sess.get_optional(f"/content/v2/cms/seasons/{sid}/episodes",
                                    {"locale": LOCALE}) or {}
            ep_items = eps.get("data") or eps.get("items") or []
        else:
            ep_items = season.get("_episodes", [])

        for ep in ep_items:
            ep_id = ep.get("id")
            if not ep_id:
                continue
            dur   = int((ep.get("duration_ms") or 0) // 1000)
            stitle = ep.get("series_title") or ""
            epno   = ep.get("episode_number")
            etitle = ep.get("title") or ""
            label  = f"{stitle} — E{epno}: {etitle}".strip(" —")
            episodes.append((ep_id, label, dur))
    return episodes


def read_playheads(sess: Session, episode_ids: list) -> dict:
    """
    Direct lookup of playhead positions for specific episode IDs on this account.
    NOT subject to the history depth limit. Returns
    {episode_id: {"playhead": int, "fully_watched": bool}}.
    """
    result = {}
    for i in range(0, len(episode_ids), PLAYHEAD_BATCH):
        batch = episode_ids[i:i + PLAYHEAD_BATCH]
        data = sess.get_optional(
            f"/content/v2/{sess.account_id}/playheads",
            {"content_ids": ",".join(batch), "locale": LOCALE},
        ) or {}
        for entry in data.get("data", []):
            cid = entry.get("content_id") or entry.get("id")
            if cid:
                result[cid] = {
                    "playhead":      int(entry.get("playhead") or 0),
                    "fully_watched": bool(entry.get("fully_watched")),
                }
        time.sleep(0.2)
    return result


# ── Target: write playheads ────────────────────────────────────────────────────

def write_playhead(sess: Session, content_id: str, playhead: int):
    """POST a playhead to the target account. Returns (status, text)."""
    url = f"{CR_BASE}/content/v2/{sess.account_id}/playheads"

    def _post():
        return requests.post(
            url,
            headers={**sess.headers, "Content-Type": "application/json"},
            params={"locale": LOCALE},
            json={"content_id": content_id, "playhead": int(playhead)},
            timeout=20,
        )

    resp = _post()
    if resp.status_code == 401 and sess.refresh_token():
        resp = _post()
    return resp.status_code, resp.text


# ── Show selection ─────────────────────────────────────────────────────────────

def watchlist_titles_from_export() -> list:
    """Pull series titles from the most recent export's watchlist, if present."""
    files = sorted(glob.glob("crunchyroll_export_*.json"), reverse=True)
    if not files:
        return []
    try:
        with open(files[0], encoding="utf-8") as f:
            export = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    titles = []
    for item in export.get("watchlist", []):
        panel = item.get("panel") or item
        ep    = panel.get("episode_metadata") or {}
        ttl   = (ep.get("series_title") or panel.get("title") or "").strip()
        if ttl and ttl not in titles:
            titles.append(ttl)
    return titles


def choose_shows() -> list:
    print("Which show(s) do you want to transfer progress for?")
    print("  • Type one or more names separated by commas, e.g.:  Kill Blue, One Piece")
    print("  • Or type  all   to use every show in your latest export's watchlist.")
    raw = input("\nShows: ").strip()
    if raw.lower() == "all":
        titles = watchlist_titles_from_export()
        if not titles:
            print("[!] No export watchlist found. Type show names instead.")
            return choose_shows()
        print(f"    ↳ {len(titles)} shows from watchlist: {', '.join(titles[:6])}"
              + (" …" if len(titles) > 6 else ""))
        return titles
    return [s.strip() for s in raw.split(",") if s.strip()]


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=== Crunchyroll Per-Series Watch-Progress Transfer ===\n")

    shows = choose_shows()
    if not shows:
        print("No shows given. Nothing to do.")
        sys.exit(0)

    # ---- PHASE A: read progress from the SOURCE (old) account ----------------
    print("\n── PHASE A: read progress from your OLD account ─────────────")
    src = Session("SOURCE")
    src.login_interactive()

    to_write = []   # (episode_id, target_playhead, label, fully)
    for show in shows:
        print(f"\n• {show}")
        cands = search_series(src, show)
        chosen = pick_series(cands, show)
        if not chosen:
            print("    ✗ not found in search — check spelling.")
            continue
        sid, stitle, stype = chosen
        print(f"    ↳ matched: {stitle} ({stype}) [{sid}]")

        eps = list_episode_ids(src, sid)
        if not eps:
            print("    ✗ could not list episodes for this title.")
            continue
        ep_ids = [e[0] for e in eps]
        dur_by = {e[0]: e[2] for e in eps}
        lbl_by = {e[0]: e[1] for e in eps}
        print(f"    ↳ {len(ep_ids)} episodes; looking up your progress…")

        heads = read_playheads(src, ep_ids)
        watched = 0
        for ep_id, info in heads.items():
            ph    = info["playhead"]
            fully = info["fully_watched"]
            if ph <= 0 and not fully:
                continue   # never started this episode
            dur    = dur_by.get(ep_id, 0)
            target = ph
            if fully and dur > 5:
                target = max(target, dur - 2)   # push past completion threshold
            if dur > 0:
                target = min(target, dur)
            to_write.append((ep_id, target, lbl_by.get(ep_id, ep_id), fully))
            watched += 1
        print(f"    ↳ {watched} episode(s) with progress found.")

    if not to_write:
        print("\nNo in-progress/watched episodes found for those shows on the old account.")
        sys.exit(0)

    # Save a record so the read work isn't lost if the write phase hiccups.
    snapshot = [{"content_id": c, "playhead": p, "label": l, "fully_watched": f}
                for c, p, l, f in to_write]
    with open("series_progress_snapshot.json", "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Collected {len(to_write)} episodes of progress "
          f"(saved to series_progress_snapshot.json).")
    print("  Sample:")
    for _, target, label, fully in to_write[:10]:
        tag = "watched" if fully else f"@{target}s"
        print(f"    - [{tag}] {label}")

    # ---- PHASE B: write progress to the TARGET (new) account -----------------
    print("\n── PHASE B: write progress to your NEW account ──────────────")
    print("Now grab the NEW account's token (this is the write phase).")
    tgt = Session("TARGET")
    tgt.login_interactive()

    if tgt.account_id == src.account_id:
        if input("[!] Target == source account. Continue anyway? [y/N]: ").strip().lower() != "y":
            print("Aborted.")
            sys.exit(0)

    ok = failed = 0
    fails = []
    print("\nWriting progress…")
    for i, (ep_id, target, label, fully) in enumerate(to_write, 1):
        try:
            status, body = write_playhead(tgt, ep_id, target)
        except requests.RequestException as e:
            status, body = -1, str(e)

        if status in (200, 201, 204):
            ok += 1
            tag = "✓ watched" if fully else f"✓ @{target}s"
        else:
            failed += 1
            tag = f"✗ ({status})"
            fails.append({"label": label, "content_id": ep_id,
                          "playhead": target, "error": f"HTTP {status}: {body[:150]}"})

        if i % 10 == 0 or i == len(to_write):
            print(f"  [{i}/{len(to_write)}] {tag}: {label}")
        time.sleep(0.1)

    print("\n──────────── Transfer complete ────────────")
    print(f"  Restored: {ok}")
    print(f"  Failed:   {failed}")
    if fails:
        with open("series_transfer_failures.json", "w", encoding="utf-8") as f:
            json.dump(fails, f, ensure_ascii=False, indent=2)
        print("  Failure details: series_transfer_failures.json")
    print("\nOpen the NEW account → the show's page / Continue Watching to verify.")


if __name__ == "__main__":
    main()

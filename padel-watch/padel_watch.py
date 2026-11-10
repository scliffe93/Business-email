#!/usr/bin/env python3
"""
Padel court watcher for Bristol.

Checks every padel club on Playtomic near Bristol for open slots in your
preferred time windows and pushes a notification to your phone (via ntfy)
the moment a new one appears. Only shows what a non-member can see/book
publicly on Playtomic.

Usage:
  python padel_watch.py            # check once (good for GitHub Actions / cron)
  python padel_watch.py --loop     # keep checking every CHECK_EVERY_MIN minutes
  python padel_watch.py --list     # just list the clubs it found, then exit
  python padel_watch.py --dry-run  # print matches, don't send notifications

Settings are at the top of the file, or override via environment variables.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# ---------------------------------------------------------------- settings ---
# Centre of Bristol and how far out to look (metres)
LAT, LON = 51.4545, -2.5879
RADIUS_M = int(os.getenv("RADIUS_M", "25000"))

# Slot start times you'd take (24h, local time), as (earliest, latest)
WINDOWS = [
    ("06:30", "07:30"),  # mornings
    ("18:30", "19:30"),  # evenings
]

DAYS_AHEAD = int(os.getenv("DAYS_AHEAD", "7"))       # how far ahead to look
MIN_DURATION = int(os.getenv("MIN_DURATION", "60"))  # minutes
CHECK_EVERY_MIN = int(os.getenv("CHECK_EVERY_MIN", "10"))

# Your private ntfy topic. Install the ntfy app and subscribe to this name.
# Make it long and random so nobody else can read it.
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")

# Clubs to skip (part of the name, case-insensitive)
EXCLUDE = [s for s in os.getenv("EXCLUDE", "").split(",") if s.strip()]

STATE_FILE = Path(os.getenv("STATE_FILE", "seen_slots.json"))
TZ = ZoneInfo("Europe/London")
API = os.getenv("PLAYTOMIC_API", "https://api.playtomic.io/v1")
HEADERS = {"User-Agent": "padel-watch personal script (low frequency)"}
# -----------------------------------------------------------------------------


def get_clubs():
    r = requests.get(
        f"{API}/tenants",
        params={
            "sport_id": "PADEL",
            "coordinate": f"{LAT},{LON}",
            "radius": RADIUS_M,
            "size": 50,
        },
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    clubs = []
    for t in r.json():
        name = t.get("tenant_name", "?")
        if any(x.strip().lower() in name.lower() for x in EXCLUDE):
            continue
        courts = {
            c["resource_id"]: c.get("name", "Court")
            for c in t.get("resources", [])
            if (c.get("sport_id") or "PADEL").upper() == "PADEL"
        }
        clubs.append({"id": t["tenant_id"], "name": name, "courts": courts})
    return clubs


def get_availability(club_id, day_utc):
    start = day_utc.strftime("%Y-%m-%dT00:00:00")
    end = day_utc.strftime("%Y-%m-%dT23:59:59")
    r = requests.get(
        f"{API}/availability",
        params={
            "sport_id": "PADEL",
            "tenant_id": club_id,
            "start_min": start,
            "start_max": end,
        },
        headers=HEADERS,
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def in_window(local_dt):
    hm = local_dt.strftime("%H:%M")
    return any(a <= hm <= b for a, b in WINDOWS)


def find_slots(clubs):
    """Return (slots, failed_club_ids)."""
    found = []
    failed = set()
    today = datetime.now(timezone.utc).date()
    now_local = datetime.now(TZ)
    # Query one extra UTC day so late-evening London times are never missed
    for club in clubs:
        for d in range(DAYS_AHEAD + 1):
            day = datetime.combine(today + timedelta(days=d), datetime.min.time())
            try:
                data = get_availability(club["id"], day)
            except requests.RequestException as e:
                print(f"  ! {club['name']} {day:%a %d}: {e}", file=sys.stderr)
                failed.add(club["id"])
                continue
            for court in data:
                court_name = club["courts"].get(court.get("resource_id"), "Court")
                date_str = court.get("start_date")
                for s in court.get("slots", []):
                    if int(s.get("duration", 0)) < MIN_DURATION:
                        continue
                    utc_dt = datetime.fromisoformat(
                        f"{date_str}T{s['start_time']}"
                    ).replace(tzinfo=timezone.utc)
                    local = utc_dt.astimezone(TZ)
                    if local < now_local or not in_window(local):
                        continue
                    found.append({
                        "key": f"{club['id']}|{court.get('resource_id')}|{utc_dt.isoformat()}|{s['duration']}",
                        "club": club["name"],
                        "club_id": club["id"],
                        "court": court_name,
                        "when": local,
                        "duration": int(s["duration"]),
                        "price": s.get("price", ""),
                    })
            time.sleep(0.5)  # be gentle
    return found, failed


def load_seen():
    try:
        return set(json.loads(STATE_FILE.read_text()))
    except (FileNotFoundError, ValueError):
        return set()


def save_seen(keys):
    STATE_FILE.write_text(json.dumps(sorted(keys)))


def notify(slots, dry_run=False):
    # Group by club + time so 3 free courts at 19:00 is one line, not three
    groups = {}
    for s in sorted(slots, key=lambda x: (x["when"], x["club"])):
        k = (s["club"], s["when"], s["duration"])
        groups.setdefault(k, []).append(s)
    lines = []
    for (club, when, dur), items in groups.items():
        price = items[0]["price"]
        n = len(items)
        courts = f"{n} courts" if n > 1 else items[0]["court"]
        lines.append(f"{when:%a %d %b %H:%M} · {dur}min · {club} · {courts}" + (f" · {price}" if price else ""))

    title = f"🎾 {len(groups)} new padel slot{'s' if len(groups) != 1 else ''} in Bristol"
    body = "\n".join(lines[:15]) + (f"\n…and {len(lines) - 15} more" if len(lines) > 15 else "")
    print(title)
    print(body)
    if dry_run or not NTFY_TOPIC:
        if not NTFY_TOPIC and not dry_run:
            print("(No NTFY_TOPIC set, so nothing was sent.)")
        return
    # JSON publishing keeps the emoji/accents in the title intact
    # (non-ASCII in HTTP headers is unreliable).
    r = requests.post(
        "https://ntfy.sh/",
        json={
            "topic": NTFY_TOPIC,
            "title": title,
            "message": body,
            "priority": 4,
            "click": "https://playtomic.io",
            "tags": ["tennis"],
        },
        timeout=20,
    )
    r.raise_for_status()  # so a failed alert isn't marked as "seen"


def run_once(dry_run=False):
    clubs = get_clubs()
    print(f"{datetime.now(TZ):%H:%M} checking {len(clubs)} clubs: "
          + ", ".join(c["name"] for c in clubs))
    if not clubs:
        raise RuntimeError("Playtomic returned no clubs, so nothing can be checked")
    slots, failed = find_slots(clubs)
    current = {s["key"] for s in slots}
    seen = load_seen()
    # If a club couldn't be fetched this time, keep remembering its slots so
    # a temporary error doesn't make every one of them re-alert next run.
    if failed:
        current |= {k for k in seen if k.split("|", 1)[0] in failed}
    new = [s for s in slots if s["key"] not in seen]
    if new:
        notify(new, dry_run)
    else:
        print("No new slots.")
    # Remember only what's still open, so a slot that frees up again re-alerts
    save_seen(current)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--loop", action="store_true")
    p.add_argument("--list", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.list:
        for c in get_clubs():
            print(f"{c['name']}  ({len(c['courts'])} courts)  id={c['id']}")
        return

    while True:
        try:
            run_once(a.dry_run)
        except (requests.RequestException, RuntimeError, ValueError) as e:
            print(f"Check failed: {e}", file=sys.stderr)
            if not a.loop:
                sys.exit(1)  # mark the GitHub run as failed so you notice
        if not a.loop:
            break
        time.sleep(CHECK_EVERY_MIN * 60)


if __name__ == "__main__":
    main()

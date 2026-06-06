"""
Diagnostic script: find the nearest upcoming fixtures in our tracked leagues.
Read-only — makes API calls and prints output only. Does not modify any source files.
"""

import sys
import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

API_KEY = os.getenv("SPORTMONKS_API_KEY", "").strip()
if not API_KEY:
    print("ERROR: SPORTMONKS_API_KEY is missing or blank in .env")
    sys.exit(1)

BASE_URL = "https://api.sportmonks.com/v3/football"
LEAGUES = {8: "Premier League", 301: "Ligue 1", 384: "Serie A", 564: "La Liga", 779: "MLS"}

api_call_count = 0


def fetch(endpoint: str) -> list:
    global api_call_count
    url = f"{BASE_URL}{endpoint}"
    params = {
        "api_token": API_KEY,
        "include": "participants;league;state",
        "per_page": 500,
    }
    api_call_count += 1
    resp = requests.get(url, params=params, timeout=20)
    if resp.status_code != 200:
        print(f"  [WARN] {endpoint} → HTTP {resp.status_code}")
        return []
    data = resp.json()
    return data.get("data", [])


def participant_names(fixture: dict) -> tuple[str, str]:
    home, away = "?", "?"
    participants = fixture.get("participants") or []
    for p in participants:
        meta = p.get("meta", {})
        loc = meta.get("location", "")
        name = p.get("name", "?")
        if loc == "home":
            home = name
        elif loc == "away":
            away = name
    return home, away


def fixture_date(fixture: dict) -> str:
    return (fixture.get("starting_at") or "")[:10]


def is_upcoming(fixture: dict, today: date) -> bool:
    d = fixture_date(fixture)
    if not d:
        return False
    try:
        return date.fromisoformat(d) >= today
    except ValueError:
        return False


def probe_window(start: date, end: date, today: date) -> dict:
    endpoint = f"/fixtures/between/{start}/{end}"
    fixtures = fetch(endpoint)

    in_leagues = [f for f in fixtures if f.get("league_id") in LEAGUES]
    upcoming = [f for f in in_leagues if is_upcoming(f, today)]
    upcoming_sorted = sorted(upcoming, key=fixture_date)

    earliest_date = fixture_date(upcoming_sorted[0]) if upcoming_sorted else None
    sample = upcoming_sorted[:3]

    return {
        "total": len(fixtures),
        "in_leagues": len(in_leagues),
        "upcoming": len(upcoming),
        "earliest_date": earliest_date,
        "sample": sample,
        "upcoming_sorted": upcoming_sorted,
    }


def main():
    today = date.today()
    windows = [7, 14, 30, 60]

    all_upcoming: list[dict] = []

    for n in windows:
        end = today + timedelta(days=n)
        print(f"\n=== Window: today → today+{n}d ===")
        result = probe_window(today, end, today)

        earliest = result["earliest_date"] or "none found"
        print(f"  Total fixtures returned:    {result['total']}")
        print(f"  In our leagues:             {result['in_leagues']}")
        print(f"  Upcoming (future only):     {result['upcoming']}")
        print(f"  Earliest upcoming date:     {earliest}")
        print(f"  Sample (up to 3):")
        if result["sample"]:
            for fx in result["sample"]:
                home, away = participant_names(fx)
                league_name = LEAGUES.get(fx.get("league_id"), "Unknown")
                d = fixture_date(fx)
                print(f"    - {home} vs {away}  |  {d}  |  {league_name}")
        else:
            print("    (none)")

        all_upcoming.extend(result["upcoming_sorted"])

    print("\n=== DEMO RECOMMENDATION ===")
    if all_upcoming:
        all_upcoming_sorted = sorted(all_upcoming, key=fixture_date)
        # Deduplicate by fixture id
        seen = set()
        deduped = []
        for fx in all_upcoming_sorted:
            fid = fx.get("id")
            if fid not in seen:
                seen.add(fid)
                deduped.append(fx)

        nearest = deduped[0]
        home, away = participant_names(nearest)
        league_name = LEAGUES.get(nearest.get("league_id"), "Unknown")
        d = fixture_date(nearest)

        # Determine which window is the minimum needed
        nearest_date = date.fromisoformat(d)
        delta = (nearest_date - today).days
        suggested_n = next((n for n in [7, 14, 30, 60] if n >= delta), 60)

        print(f"  Nearest game found:   {d} — {home} vs {away} ({league_name})")
        print(f"  Suggested fix:        Expand fetch window to {suggested_n} days in sportmonks_client.py")
    else:
        print("  No upcoming fixtures found in any window. All 5 leagues may be in off-season.")

    print(f"  API calls used:       {api_call_count} / 15 budget")


if __name__ == "__main__":
    main()

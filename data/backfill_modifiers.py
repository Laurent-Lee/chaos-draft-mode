"""
backfill_modifiers.py — One-off script to populate modifier columns for
existing output.csv rows that were recorded before modifier tracking was added.
Also regenerates modifiers_data.csv from the updated output.csv.

Run from the repo root:
    python3 data/backfill_modifiers.py
"""

import csv
import json
import os
import sys
import urllib.request
from dotenv import load_dotenv

load_dotenv()

_ROOT            = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
CSV_FILE         = os.path.join(_ROOT, "data", "output.csv")
PLAYER_TAGS_FILE = os.path.join(_ROOT, "data", "player_tags.json")
CR_API_TOKEN     = os.getenv("CR_API_TOKEN", "")
CHAOS_GAME_MODE  = "Crazy_Arena"
CR_API_BASE      = "https://api.clashroyale.com/v1"
MODIFIER_COLS    = [f"Modifier_{i}_W" for i in range(1, 6)] + [f"Modifier_{i}_L" for i in range(1, 6)]


def load_player_tags():
    with open(PLAYER_TAGS_FILE, encoding="utf-8") as f:
        return json.load(f)


def fetch_battles(player_tag):
    encoded = player_tag.replace("#", "%23")
    url = f"{CR_API_BASE}/players/{encoded}/battlelog"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CR_API_TOKEN}"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


def check_battle(battle, winner_tag, loser_tag, winner_cards, loser_cards, winner_is_team):
    """
    Returns (winner_mods, loser_mods) if the battle matches, else None.
    winner_is_team=True  → fetched from winner's log (team = winner)
    winner_is_team=False → fetched from loser's log  (team = loser)
    """
    if battle.get("gameMode", {}).get("name") != CHAOS_GAME_MODE:
        return None
    team_list = battle.get("team", [])
    opp_list  = battle.get("opponent", [])
    if not team_list or not opp_list:
        return None

    if winner_is_team:
        if opp_list[0].get("tag") != loser_tag:
            return None
        if team_list[0].get("crowns", 0) == 0:
            return None
        api_w = {c["name"] for c in team_list[0].get("cards", [])}
        api_l = {c["name"] for c in opp_list[0].get("cards", [])}
    else:
        if opp_list[0].get("tag") != winner_tag:
            return None
        if opp_list[0].get("crowns", 0) == 0:
            return None
        api_w = {c["name"] for c in opp_list[0].get("cards", [])}
        api_l = {c["name"] for c in team_list[0].get("cards", [])}

    if api_w != winner_cards or api_l != loser_cards:
        return None

    winner_mods, loser_mods = [], []
    for md in battle.get("modifiers", []):
        t = md.get("tag")
        if t == winner_tag:
            winner_mods = md.get("modifiers", [])
        elif t == loser_tag:
            loser_mods  = md.get("modifiers", [])
    return winner_mods[:5], loser_mods[:5]


def find_modifiers(winner_tag, loser_tag, winner_cards, loser_cards, battle_cache):
    """Try winner's log first; fall back to loser's log if no match found."""
    for tag, is_team in [(winner_tag, True), (loser_tag, False)]:
        if tag not in battle_cache:
            print(f"  Fetching battles for {tag}...")
            try:
                battle_cache[tag] = fetch_battles(tag)
            except Exception as e:
                print(f"  ERROR fetching {tag}: {e}")
                battle_cache[tag] = []
        for battle in battle_cache[tag]:
            result = check_battle(battle, winner_tag, loser_tag,
                                  winner_cards, loser_cards, winner_is_team=is_team)
            if result is not None:
                return result
    return None


def pad(mods):
    if not mods:
        return [""] * 5
    return [mods[i] if i < len(mods) else "" for i in range(5)]


def main():
    tags = load_player_tags()

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Ensure modifier columns exist in the header
    for col in MODIFIER_COLS:
        if col not in fieldnames:
            fieldnames.append(col)

    # Cache battle logs so we don't re-fetch the same player multiple times
    battle_cache = {}

    updated = 0
    for i, row in enumerate(rows):
        # Skip rows that already have modifier data
        if any(row.get(col, "").strip() for col in MODIFIER_COLS):
            print(f"[row {i+1}] already has modifiers, skipping")
            continue

        winner = row.get("winner", "").strip()
        loser  = row.get("loser",  "").strip()
        winner_tag = tags.get(winner)
        loser_tag  = tags.get(loser)

        if not winner_tag or not loser_tag:
            print(f"[row {i+1}] unknown player ({winner} or {loser}), skipping")
            continue

        # Build card sets from CSV columns
        winner_cards = {c[:-2] for c in fieldnames if c.endswith("_W") and not c.startswith("Modifier") and row.get(c, "0").strip() == "1"}
        loser_cards  = {c[:-2] for c in fieldnames if c.endswith("_L") and not c.startswith("Modifier") and row.get(c, "0").strip() == "1"}

        result = find_modifiers(winner_tag, loser_tag, winner_cards, loser_cards, battle_cache)
        w_mods, l_mods = result if result else (None, None)

        if w_mods is None:
            print(f"[row {i+1}] {winner} vs {loser} — no matching battle found")
        else:
            print(f"[row {i+1}] {winner} vs {loser} — MATCHED  W:{w_mods}  L:{l_mods}")
            for j, col in enumerate(MODIFIER_COLS):
                combined = pad(w_mods) + pad(l_mods)
                row[col] = combined[j]
            updated += 1

    # Write back
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. {updated}/{len(rows)} rows updated.")

    # Regenerate modifiers_data.csv from the updated output.csv
    print("\nRegenerating modifiers_data.csv...")
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from backend.modifiers import write_modifiers_csv
    write_modifiers_csv()
    print(f"modifiers_data.csv written to {os.path.join(os.path.dirname(CSV_FILE), 'modifiers_data.csv')}")


if __name__ == "__main__":
    main()

"""
stats.py -- CSV recording, match history, card stats, player stats, and ELO.

Routes:
  POST /api/record_winner
  GET  /api/match_history
  GET  /api/card_stats
  GET  /api/player_stats
  GET  /api/player_stats/<player_name>
  GET  /api/elo
"""

import os
import csv
import json
import urllib.request
from datetime import datetime, timezone
from itertools import product as iproduct
from flask import Blueprint, jsonify, request
from config import CSV_FILE, CHAOS_CARD_LIST, PLAYERS, ELO_STARTING, _ROOT, CR_API_TOKEN, PLAYER_TAGS_FILE, ELO_NORMAL_CSV, ELO_AI_CSV
from backend.draft import state
from backend.modifiers import refresh_modifiers

# Import ELO calculator -- elo.py lives in backend/
try:
    from backend.elo import calculate_elo, OUTPUT_CSV as ELO_CSV, INPUT_CSV as ELO_INPUT
except ImportError:
    calculate_elo = None
    ELO_CSV       = os.path.join(_ROOT, "data", "elo.csv")
    ELO_INPUT     = os.path.join(_ROOT, "data", "output.csv")

stats_bp = Blueprint("stats", __name__)

MODIFIER_COLS = [f"Modifier_{i}_W" for i in range(1, 6)] + [f"Modifier_{i}_L" for i in range(1, 6)]
CHAOS_GAME_MODE = "Crazy_Arena"
CR_API_BASE     = "https://api.clashroyale.com/v1"


# -- Internal helpers ---------------------------------------------------------

def _refresh_elo():
    """Re-run the ELO calculator after every recorded match — all games plus per-mode."""
    if not calculate_elo:
        return
    for output, mode_filter in [
        (ELO_CSV,        None),
        (ELO_NORMAL_CSV, "Normal Draft"),
        (ELO_AI_CSV,     "AI Draft"),
    ]:
        try:
            calculate_elo(ELO_INPUT, output, game_mode_filter=mode_filter)
        except Exception as e:
            print(f"ELO refresh failed ({mode_filter or 'all'}): {e}")


def _csv_headers():
    win_cols    = [f"{c}_W"      for c in CHAOS_CARD_LIST]
    loss_cols   = [f"{c}_L"      for c in CHAOS_CARD_LIST]
    banned_cols = [f"{c}_BANNED" for c in CHAOS_CARD_LIST]
    return ["game_mode", "timestamp", "1st_pick", "2nd_pick", "winner", "loser"] + win_cols + loss_cols + banned_cols + MODIFIER_COLS


def _ensure_csv_headers():
    """Create the data/ directory and write the header row if needed. Migrates existing CSV to add new columns."""
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    expected = _csv_headers()
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(expected)
        return
    # File exists — check if header needs migration
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing_fields = list(reader.fieldnames or [])
        rows = list(reader)
    missing = [col for col in expected if col not in existing_fields]
    if not missing:
        return
    # Rewrite with updated header, preserving all existing data
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=expected, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _load_player_tags():
    """Return {name: "#TAG"} mapping from data/player_tags.json."""
    if not os.path.exists(PLAYER_TAGS_FILE):
        return {}
    with open(PLAYER_TAGS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _fetch_player_battles(player_tag):
    """Fetch the battle log for a player tag from the CR API. Returns a list or []."""
    if not CR_API_TOKEN:
        return []
    encoded = player_tag.replace("#", "%23")
    url = f"{CR_API_BASE}/players/{encoded}/battlelog"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CR_API_TOKEN}"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[modifier] Battle log fetch failed for {player_tag}: {e}")
        return []


def _extract_modifiers_from_battle(battle, winner_tag, loser_tag,
                                   winner_cards, loser_cards, winner_is_team):
    """
    Try to extract modifier data from a single battle dict.
    winner_is_team=True  → battle fetched from winner's log (team = winner)
    winner_is_team=False → battle fetched from loser's log  (team = loser)
    Returns (winner_mods, loser_mods) or None if the battle doesn't match.
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
        # Fetched from loser's perspective: team = loser, opponent = winner
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


def _fetch_battle_modifiers(winner_name, loser_name, winner_cards, loser_cards):
    """
    Find the most recent Crazy_Arena battle between winner and loser whose card sets
    match the draft and whose result matches.

    First tries the winner's battle log; if that yields no match (e.g. privacy is on),
    falls back to the loser's log.

    Returns (winner_mods, loser_mods) as lists of up to 5 modifier strings,
    or (None, None) if no match is found.
    """
    tags = _load_player_tags()
    winner_tag = tags.get(winner_name)
    loser_tag  = tags.get(loser_name)
    if not winner_tag or not loser_tag:
        return None, None

    # Try winner's log first
    for battle in _fetch_player_battles(winner_tag):
        result = _extract_modifiers_from_battle(
            battle, winner_tag, loser_tag, winner_cards, loser_cards,
            winner_is_team=True
        )
        if result is not None:
            return result

    # Fallback: try loser's log (handles winner having battle log privacy on)
    for battle in _fetch_player_battles(loser_tag):
        result = _extract_modifiers_from_battle(
            battle, winner_tag, loser_tag, winner_cards, loser_cards,
            winner_is_team=False
        )
        if result is not None:
            return result

    return None, None


def _pad_mods(mods):
    """Pad or truncate a modifier list to exactly 5 entries (empty string for missing)."""
    if not mods:
        return [""] * 5
    return [mods[i] if i < len(mods) else "" for i in range(5)]


def _read_elo_for(name, game_mode_filter=""):
    """Return the current ELO for a single player name, optionally filtered by game mode."""
    if game_mode_filter == "Normal Draft":
        elo_file = ELO_NORMAL_CSV
    elif game_mode_filter == "AI Draft":
        elo_file = ELO_AI_CSV
    else:
        elo_file = ELO_CSV
    elo = ELO_STARTING
    if os.path.exists(elo_file):
        try:
            with open(elo_file, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows and name in rows[-1]:
                elo = round(float(rows[-1][name]))
        except Exception:
            pass
    return elo


# -- Routes -------------------------------------------------------------------

@stats_bp.route("/api/record_winner", methods=["POST"])
def record_winner():
    body          = request.json or {}
    winner_player = body.get("winner")  # 1 or 2

    if winner_player not in (1, 2):
        return jsonify({"error": "winner must be 1 or 2"}), 400
    if state["phase"] != "done":
        return jsonify({"error": "Draft is not finished yet"}), 400

    if winner_player == 1:
        winner_name  = state["p1_name"]
        loser_name   = state["p2_name"]
        winner_picks = state["p1_picks"]
        loser_picks  = state["p2_picks"]
    else:
        winner_name  = state["p2_name"]
        loser_name   = state["p1_name"]
        winner_picks = state["p2_picks"]
        loser_picks  = state["p1_picks"]

    winner_card_names = {c["name"] for c in winner_picks}
    loser_card_names  = {c["name"] for c in loser_picks}

    winner_banned = {b["card"]["name"] for b in state["banned"] if b["by"] == winner_player}
    loser_player  = 2 if winner_player == 1 else 1
    loser_banned  = {b["card"]["name"] for b in state["banned"] if b["by"] == loser_player}
    random_banned = {b["card"]["name"] for b in state["banned"] if b["by"] == "random"}

    win_cols    = [1 if c in winner_card_names else 0 for c in CHAOS_CARD_LIST]
    loss_cols   = [1 if c in loser_card_names  else 0 for c in CHAOS_CARD_LIST]
    banned_cols = [
        "R" if c in random_banned else
        1   if c in winner_banned else
        -1  if c in loser_banned  else
        0
        for c in CHAOS_CARD_LIST
    ]

    # Fetch modifier data from CR API before writing (best-effort)
    try:
        w_mods, l_mods = _fetch_battle_modifiers(
            winner_name, loser_name, winner_card_names, loser_card_names
        )
    except Exception as e:
        print(f"[modifier] Unexpected error: {e}")
        w_mods, l_mods = None, None

    modifier_vals = _pad_mods(w_mods) + _pad_mods(l_mods)

    _ensure_csv_headers()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        game_mode = "AI Draft" if state["ai_mode"] else "Normal Draft"
        csv.writer(f).writerow(
            [game_mode, timestamp, state["1st_pick"], state["2nd_pick"], winner_name, loser_name]
            + win_cols + loss_cols + banned_cols + modifier_vals
        )

    _refresh_elo()
    _refresh_matchups()
    refresh_modifiers()
    return jsonify({"status": "saved", "winner": winner_name, "loser": loser_name})


@stats_bp.route("/api/match_history", methods=["GET"])
def match_history():
    """Return recent games enriched with per-player card lists and ban lists."""
    limit = int(request.args.get("limit", 10))
    gm    = request.args.get("game_mode", "").strip()
    rows  = []
    if not os.path.exists(CSV_FILE):
        return jsonify(rows)

    card_lookup = {c["name"]: c for c in state.get("cards", [])}

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if gm and row.get("game_mode", "").strip() != gm:
                continue
            rows.append(row)

    rows.sort(key=lambda r: r.get("timestamp", ""))
    rows = list(reversed(rows))  # newest first
    if limit > 0:
        rows = rows[:limit]

    result = []
    for row in rows:
        first  = row.get("1st_pick", "").strip()
        second = row.get("2nd_pick", "").strip()
        winner = row.get("winner",   "").strip()
        loser  = row.get("loser",    "").strip()

        def cards_for(player):
            if player not in (first, second):
                return [], []
            col_suffix = "_W" if player == winner else "_L"
            ban_val    = "1" if player == winner else "-1"
            picks = [
                card_lookup.get(c, {"name": c, "iconUrl": "", "elixir": 0})
                for c in CHAOS_CARD_LIST
                if row.get(f"{c}{col_suffix}", "0").strip() == "1"
            ]
            bans = [
                card_lookup.get(c, {"name": c, "iconUrl": "", "elixir": 0})
                for c in CHAOS_CARD_LIST
                if row.get(f"{c}_BANNED", "0").strip() == ban_val
            ]
            return picks, bans

        random_bans = [
            card_lookup.get(c, {"name": c, "iconUrl": "", "elixir": 0})
            for c in CHAOS_CARD_LIST
            if row.get(f"{c}_BANNED", "0").strip() == "R"
        ]

        first_picks,  first_bans  = cards_for(first)
        second_picks, second_bans = cards_for(second)

        result.append({
            "1st_pick":     first,
            "2nd_pick":     second,
            "winner":       winner,
            "loser":        loser,
            "game_mode":    row.get("game_mode", "").strip(),
            "first_picks":  first_picks,
            "first_bans":   first_bans,
            "second_picks": second_picks,
            "second_bans":  second_bans,
            "random_bans":  random_bans,
        })

    return jsonify(result)


@stats_bp.route("/api/match_history/<player_name>", methods=["GET"])
def match_history_player(player_name):
    """Return recent games for a specific player (limit=10)."""
    limit = int(request.args.get("limit", 10))
    gm    = request.args.get("game_mode", "").strip()
    rows  = []
    if not os.path.exists(CSV_FILE):
        return jsonify(rows)

    card_lookup = {c["name"]: c for c in state.get("cards", [])}

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if gm and row.get("game_mode", "").strip() != gm:
                continue
            winner = row.get("winner", "").strip()
            loser  = row.get("loser",  "").strip()
            if player_name in (winner, loser):
                rows.append(row)

    rows.sort(key=lambda r: r.get("timestamp", ""))
    rows = list(reversed(rows))
    if limit > 0:
        rows = rows[:limit]

    result = []
    for row in rows:
        first  = row.get("1st_pick", "").strip()
        second = row.get("2nd_pick", "").strip()
        winner = row.get("winner",   "").strip()
        loser  = row.get("loser",    "").strip()

        def cards_for(player):
            if player not in (first, second):
                return [], []
            col_suffix = "_W" if player == winner else "_L"
            ban_val    = "1" if player == winner else "-1"
            picks = [
                card_lookup.get(c, {"name": c, "iconUrl": "", "elixir": 0})
                for c in CHAOS_CARD_LIST
                if row.get(f"{c}{col_suffix}", "0").strip() == "1"
            ]
            bans = [
                card_lookup.get(c, {"name": c, "iconUrl": "", "elixir": 0})
                for c in CHAOS_CARD_LIST
                if row.get(f"{c}_BANNED", "0").strip() == ban_val
            ]
            return picks, bans

        random_bans = [
            card_lookup.get(c, {"name": c, "iconUrl": "", "elixir": 0})
            for c in CHAOS_CARD_LIST
            if row.get(f"{c}_BANNED", "0").strip() == "R"
        ]

        first_picks,  first_bans  = cards_for(first)
        second_picks, second_bans = cards_for(second)

        result.append({
            "1st_pick":     first,
            "2nd_pick":     second,
            "winner":       winner,
            "loser":        loser,
            "game_mode":    row.get("game_mode", "").strip(),
            "first_picks":  first_picks,
            "first_bans":   first_bans,
            "second_picks": second_picks,
            "second_bans":  second_bans,
            "random_bans":  random_bans,
        })

    return jsonify(result)


@stats_bp.route("/api/card_stats", methods=["GET"])
def card_stats():
    """Return per-card stats computed from output.csv (all games, no player filter)."""
    if not os.path.exists(CSV_FILE):
        return jsonify([])

    gm          = request.args.get("game_mode", "").strip()
    stats       = {c: {"wins": 0, "losses": 0, "player_bans": 0, "random_bans": 0}
                   for c in CHAOS_CARD_LIST}
    total_games = 0

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if gm and row.get("game_mode", "").strip() != gm:
                continue
            total_games += 1
            for c in CHAOS_CARD_LIST:
                w = row.get(f"{c}_W",      "0").strip()
                l = row.get(f"{c}_L",      "0").strip()
                b = row.get(f"{c}_BANNED", "0").strip()
                if w == "1":         stats[c]["wins"]        += 1
                if l == "1":         stats[c]["losses"]       += 1
                if b in ("1", "-1"): stats[c]["player_bans"] += 1
                if b == "R":         stats[c]["random_bans"]  += 1

    card_lookup = {c["name"]: c for c in state.get("cards", [])}
    result = []
    for c in CHAOS_CARD_LIST:
        s            = stats[c]
        games_played = s["wins"] + s["losses"]
        play_rate    = round(games_played / total_games * 100, 1) if total_games  else 0
        win_rate     = round(s["wins"] / games_played * 100, 1)  if games_played else 0
        ban_rate     = round(s["player_bans"] / total_games * 100, 1) if total_games else 0
        meta         = card_lookup.get(c, {})
        result.append({
            "name":         c,
            "iconUrl":      meta.get("iconUrl", ""),
            "elixir":       meta.get("elixir", 0),
            "rarity":       meta.get("rarity", ""),
            "games_played": games_played,
            "wins":         s["wins"],
            "losses":       s["losses"],
            "player_bans":  s["player_bans"],
            "random_bans":  s["random_bans"],
            "total_games":  total_games,
            "play_rate":    play_rate,
            "win_rate":     win_rate,
            "ban_rate":     ban_rate,
        })

    return jsonify(result)



def _refresh_matchups():
    """Recompute card_data.csv after every recorded match."""
    try:
        _write_matchups_csv()
    except Exception as e:
        print(f"Matchup refresh failed: {e}")


def _write_matchups_csv():
    """Compute all 2500 ordered card-pair rows and write data/card_data.csv."""
    CARD_DATA_CSV = os.path.join(_ROOT, "data", "card_data.csv")
    os.makedirs(os.path.dirname(CARD_DATA_CSV), exist_ok=True)
    agg = {
        (c1, c2): {"card_1_W": 0, "card_1_L": 0, "games_played": 0}
        for c1 in CHAOS_CARD_LIST for c2 in CHAOS_CARD_LIST if c1 != c2
    }
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                wcs = [c for c in CHAOS_CARD_LIST if row.get(f"{c}_W", "0").strip() == "1"]
                lcs = [c for c in CHAOS_CARD_LIST if row.get(f"{c}_L", "0").strip() == "1"]
                for wc, lc in iproduct(wcs, lcs):
                    agg[(wc, lc)]["card_1_W"]    += 1
                    agg[(wc, lc)]["games_played"] += 1
                    agg[(lc, wc)]["card_1_L"]    += 1
                    agg[(lc, wc)]["games_played"] += 1
    with open(CARD_DATA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["card_1","card_2","card_1_W","card_1_L","Games Played"])
        writer.writeheader()
        for (c1, c2), counts in agg.items():
            writer.writerow({"card_1": c1, "card_2": c2,
                             "card_1_W": counts["card_1_W"], "card_1_L": counts["card_1_L"],
                             "Games Played": counts["games_played"]})
    try:
        from backend.tier_calculator import calculate_ratings
        calculate_ratings(CARD_DATA_CSV, CSV_FILE)
    except Exception as e:
        print(f"Rating calculation failed: {e}")


@stats_bp.route("/api/card_matchups", methods=["GET"])
def card_matchups():
    """Return all 2500 card-vs-card matchup rows."""
    agg = {
        (c1, c2): {"card_1_W": 0, "card_1_L": 0, "games_played": 0}
        for c1 in CHAOS_CARD_LIST for c2 in CHAOS_CARD_LIST if c1 != c2
    }
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                wcs = [c for c in CHAOS_CARD_LIST if row.get(f"{c}_W", "0").strip() == "1"]
                lcs = [c for c in CHAOS_CARD_LIST if row.get(f"{c}_L", "0").strip() == "1"]
                for wc, lc in iproduct(wcs, lcs):
                    agg[(wc, lc)]["card_1_W"]    += 1
                    agg[(wc, lc)]["games_played"] += 1
                    agg[(lc, wc)]["card_1_L"]    += 1
                    agg[(lc, wc)]["games_played"] += 1
    card_lookup = {c["name"]: c for c in state.get("cards", [])}
    result = []
    for (c1, c2), counts in agg.items():
        gp = counts["games_played"]; w = counts["card_1_W"]
        m1 = card_lookup.get(c1, {}); m2 = card_lookup.get(c2, {})
        result.append({"card_1": c1, "card_2": c2,
            "card_1_W": w, "card_1_L": counts["card_1_L"], "games_played": gp,
            "win_rate": round(w/gp*100,1) if gp else 0,
            "card_1_iconUrl": m1.get("iconUrl",""), "card_2_iconUrl": m2.get("iconUrl","")})
    return jsonify(result)


@stats_bp.route("/api/card_matchups/export", methods=["POST"])
def export_card_matchups():
    """Trigger rewrite of data/card_data.csv."""
    try:
        _write_matchups_csv()
        CARD_DATA_CSV = os.path.join(_ROOT, "data", "card_data.csv")
        with open(CARD_DATA_CSV, newline="", encoding="utf-8") as f:
            rows = sum(1 for _ in csv.reader(f)) - 1
        return jsonify({"status": "exported", "path": CARD_DATA_CSV, "rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@stats_bp.route("/api/card_detail/<card_name>", methods=["GET"])
def card_detail(card_name):
    """Return overall stats + all 49 matchup rows for a single card."""
    CARD_DATA_CSV = os.path.join(_ROOT, "data", "card_data.csv")
    card_lookup   = {c["name"]: c for c in state.get("cards", [])}

    # Overall stats from output.csv
    wins = losses = player_bans = random_bans = total_games = 0
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                total_games += 1
                w = row.get(f"{card_name}_W",      "0").strip()
                l = row.get(f"{card_name}_L",      "0").strip()
                b = row.get(f"{card_name}_BANNED", "0").strip()
                if w == "1":         wins        += 1
                if l == "1":         losses      += 1
                if b in ("1", "-1"): player_bans += 1
                if b == "R":         random_bans  += 1

    games_played = wins + losses
    meta         = card_lookup.get(card_name, {})
    overall = {
        "name": card_name, "iconUrl": meta.get("iconUrl",""),
        "elixir": meta.get("elixir",0), "rarity": meta.get("rarity",""),
        "total_games": total_games, "games_played": games_played,
        "wins": wins, "losses": losses,
        "player_bans": player_bans, "random_bans": random_bans,
        "play_rate": round(games_played/total_games*100,1) if total_games else 0,
        "win_rate":  round(wins/games_played*100,1)        if games_played else 0,
        "ban_rate":  round(player_bans/total_games*100,1)  if total_games else 0,
    }

    # Matchup rows — prefer card_data.csv, fall back to live computation
    matchups = []
    if os.path.exists(CARD_DATA_CSV):
        with open(CARD_DATA_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("card_1","").strip() != card_name:
                    continue
                c2 = row["card_2"].strip()
                gp = int(row.get("Games Played",0) or 0)
                w  = int(row.get("card_1_W",0)     or 0)
                l  = int(row.get("card_1_L",0)     or 0)
                m2 = card_lookup.get(c2, {})
                matchups.append({"card_2": c2, "card_2_iconUrl": m2.get("iconUrl",""),
                    "card_2_elixir": m2.get("elixir",0),
                    "card_1_W": w, "card_1_L": l, "games_played": gp,
                    "win_rate": round(w/gp*100,1) if gp else None})
    else:
        agg2 = {c2: {"W":0,"L":0,"GP":0} for c2 in CHAOS_CARD_LIST if c2 != card_name}
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    wcs = [c for c in CHAOS_CARD_LIST if row.get(f"{c}_W","0").strip()=="1"]
                    lcs = [c for c in CHAOS_CARD_LIST if row.get(f"{c}_L","0").strip()=="1"]
                    for wc,lc in iproduct(wcs,lcs):
                        if wc==card_name and lc in agg2: agg2[lc]["W"]+=1; agg2[lc]["GP"]+=1
                        if lc==card_name and wc in agg2: agg2[wc]["L"]+=1; agg2[wc]["GP"]+=1
        for c2,d in agg2.items():
            gp=d["GP"]; w=d["W"]; m2=card_lookup.get(c2,{})
            matchups.append({"card_2":c2,"card_2_iconUrl":m2.get("iconUrl",""),
                "card_2_elixir":m2.get("elixir",0),
                "card_1_W":w,"card_1_L":d["L"],"games_played":gp,
                "win_rate":round(w/gp*100,1) if gp else None})

    return jsonify({"overall": overall, "matchups": matchups})


@stats_bp.route("/api/player_stats", methods=["GET"])
def player_stats():
    """Return win/loss counts for each known player from output.csv."""
    gm    = request.args.get("game_mode", "").strip()
    stats = {p: {"wins": 0, "losses": 0} for p in PLAYERS}
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if gm and row.get("game_mode", "").strip() != gm:
                    continue
                w = row.get("winner", "").strip()
                l = row.get("loser",  "").strip()
                if w in stats:
                    stats[w]["wins"]   += 1
                if l in stats:
                    stats[l]["losses"] += 1
    return jsonify(stats)


@stats_bp.route("/api/player_stats/<player_name>", methods=["GET"])
def player_stats_detail(player_name):
    """Return full stats for a single player: record, win%, ELO, and per-card stats."""
    card_lookup  = {c["name"]: c for c in state.get("cards", [])}

    # Return a valid empty payload when there is no data yet
    if not os.path.exists(CSV_FILE):
        cards_result = []
        for c in CHAOS_CARD_LIST:
            meta = card_lookup.get(c, {})
            cards_result.append({
                "name": c, "iconUrl": meta.get("iconUrl",""),
                "elixir": meta.get("elixir",0), "rarity": meta.get("rarity",""),
                "games_played":0,"wins":0,"losses":0,
                "player_bans":0,"random_bans":0,
                "play_rate":0,"win_rate":0,"ban_rate":0,
            })
        return jsonify({
            "name": player_name, "elo": _read_elo_for(player_name, gm),
            "wins":0,"losses":0,"total_games":0,"win_pct":0,"loss_pct":0,
            "cards": cards_result,
        })

    gm          = request.args.get("game_mode", "").strip()
    record      = {"wins": 0, "losses": 0}
    card_stats_ = {c: {"wins": 0, "losses": 0, "player_bans": 0, "random_bans": 0}
                   for c in CHAOS_CARD_LIST}
    total_games = 0

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if gm and row.get("game_mode", "").strip() != gm:
                continue
            winner = row.get("winner", "").strip()
            loser  = row.get("loser",  "").strip()
            if player_name not in (winner, loser):
                continue
            total_games += 1
            is_winner = (player_name == winner)
            if is_winner:
                record["wins"] += 1
            else:
                record["losses"] += 1

            for c in CHAOS_CARD_LIST:
                w = row.get(f"{c}_W",      "0").strip()
                l = row.get(f"{c}_L",      "0").strip()
                b = row.get(f"{c}_BANNED", "0").strip()
                if is_winner:
                    if w == "1":  card_stats_[c]["wins"]        += 1
                    if b == "1":  card_stats_[c]["player_bans"] += 1
                else:
                    if l == "1":  card_stats_[c]["losses"]       += 1
                    if b == "-1": card_stats_[c]["player_bans"]  += 1
                if b == "R":      card_stats_[c]["random_bans"]  += 1

    games_played = record["wins"] + record["losses"]
    win_pct      = round(record["wins"]   / games_played * 100, 1) if games_played else 0
    loss_pct     = round(record["losses"] / games_played * 100, 1) if games_played else 0

    card_lookup  = {c["name"]: c for c in state.get("cards", [])}
    cards_result = []
    for c in CHAOS_CARD_LIST:
        s         = card_stats_[c]
        cp        = s["wins"] + s["losses"]
        play_rate = round(cp / total_games * 100, 1)              if total_games else 0
        win_rate  = round(s["wins"] / cp * 100, 1)                if cp          else 0
        ban_rate  = round(s["player_bans"] / total_games * 100, 1) if total_games else 0
        meta      = card_lookup.get(c, {})
        cards_result.append({
            "name":         c,
            "iconUrl":      meta.get("iconUrl", ""),
            "elixir":       meta.get("elixir", 0),
            "rarity":       meta.get("rarity", ""),
            "games_played": cp,
            "wins":         s["wins"],
            "losses":       s["losses"],
            "player_bans":  s["player_bans"],
            "random_bans":  s["random_bans"],
            "play_rate":    play_rate,
            "win_rate":     win_rate,
            "ban_rate":     ban_rate,
        })

    return jsonify({
        "name":        player_name,
        "elo":         _read_elo_for(player_name, gm),
        "wins":        record["wins"],
        "losses":      record["losses"],
        "total_games": total_games,
        "win_pct":     win_pct,
        "loss_pct":    loss_pct,
        "cards":       cards_result,
    })


@stats_bp.route("/api/elo", methods=["GET"])
def get_elo():
    """Return the latest ELO for every known player. Accepts ?game_mode= to filter by mode."""
    gm = request.args.get("game_mode", "").strip()
    if gm == "Normal Draft":
        elo_file = ELO_NORMAL_CSV
    elif gm == "AI Draft":
        elo_file = ELO_AI_CSV
    else:
        elo_file = ELO_CSV
    ratings = {p: ELO_STARTING for p in PLAYERS}
    if os.path.exists(elo_file):
        try:
            with open(elo_file, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                for p in PLAYERS:
                    if p in last:
                        try:
                            ratings[p] = round(float(last[p]))
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
    return jsonify(ratings)
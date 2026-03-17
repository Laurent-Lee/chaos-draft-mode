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
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request
from config import CSV_FILE, CHAOS_CARD_LIST, PLAYERS, ELO_STARTING, _ROOT
from backend.draft import state

# Import ELO calculator -- elo.py lives in backend/
try:
    from backend.elo import calculate_elo, OUTPUT_CSV as ELO_CSV, INPUT_CSV as ELO_INPUT
except ImportError:
    calculate_elo = None
    ELO_CSV       = os.path.join(_ROOT, "data", "elo.csv")
    ELO_INPUT     = os.path.join(_ROOT, "data", "output.csv")

stats_bp = Blueprint("stats", __name__)


# -- Internal helpers ---------------------------------------------------------

def _refresh_elo():
    """Re-run the ELO calculator after every recorded match."""
    if calculate_elo:
        try:
            calculate_elo(ELO_INPUT, ELO_CSV)
        except Exception as e:
            print(f"ELO refresh failed: {e}")


def _csv_headers():
    win_cols    = [f"{c}_W"      for c in CHAOS_CARD_LIST]
    loss_cols   = [f"{c}_L"      for c in CHAOS_CARD_LIST]
    banned_cols = [f"{c}_BANNED" for c in CHAOS_CARD_LIST]
    return ["timestamp", "1st_pick", "2nd_pick", "winner", "loser"] + win_cols + loss_cols + banned_cols


def _ensure_csv_headers():
    """Create the data/ directory and write the header row if the file does not exist yet."""
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_csv_headers())


def _read_elo_for(name):
    """Return the current ELO for a single player name."""
    elo = ELO_STARTING
    if os.path.exists(ELO_CSV):
        try:
            with open(ELO_CSV, newline="", encoding="utf-8") as f:
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

    _ensure_csv_headers()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(
            [timestamp, state["1st_pick"], state["2nd_pick"], winner_name, loser_name]
            + win_cols + loss_cols + banned_cols
        )

    _refresh_elo()
    return jsonify({"status": "saved", "winner": winner_name, "loser": loser_name})


@stats_bp.route("/api/match_history", methods=["GET"])
def match_history():
    """Return recent games enriched with per-player card lists and ban lists."""
    limit = int(request.args.get("limit", 10))
    rows  = []
    if not os.path.exists(CSV_FILE):
        return jsonify(rows)

    card_lookup = {c["name"]: c for c in state.get("cards", [])}

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=False)
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
    rows  = []
    if not os.path.exists(CSV_FILE):
        return jsonify(rows)

    card_lookup = {c["name"]: c for c in state.get("cards", [])}

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            winner = row.get("winner", "").strip()
            loser  = row.get("loser",  "").strip()
            if player_name in (winner, loser):
                rows.append(row)

    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=False)
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

    stats       = {c: {"wins": 0, "losses": 0, "player_bans": 0, "random_bans": 0}
                   for c in CHAOS_CARD_LIST}
    total_games = 0

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
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


@stats_bp.route("/api/player_stats", methods=["GET"])
def player_stats():
    """Return win/loss counts for each known player from output.csv."""
    stats = {p: {"wins": 0, "losses": 0} for p in PLAYERS}
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
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
            "name": player_name, "elo": _read_elo_for(player_name),
            "wins":0,"losses":0,"total_games":0,"win_pct":0,"loss_pct":0,
            "cards": cards_result,
        })

    record      = {"wins": 0, "losses": 0}
    card_stats_ = {c: {"wins": 0, "losses": 0, "player_bans": 0, "random_bans": 0}
                   for c in CHAOS_CARD_LIST}
    total_games = 0

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
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
        "elo":         _read_elo_for(player_name),
        "wins":        record["wins"],
        "losses":      record["losses"],
        "total_games": total_games,
        "win_pct":     win_pct,
        "loss_pct":    loss_pct,
        "cards":       cards_result,
    })


@stats_bp.route("/api/elo", methods=["GET"])
def get_elo():
    """Return the latest ELO for every known player from elo.csv."""
    ratings = {p: ELO_STARTING for p in PLAYERS}
    if os.path.exists(ELO_CSV):
        try:
            with open(ELO_CSV, newline="", encoding="utf-8") as f:
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
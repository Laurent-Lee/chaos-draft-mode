"""
get_card_data.py — Card data access functions for the AI draft pipeline.

Public API:
    get_card_win_rates(csv_path)              -> dict
    get_matchup_win_rates(card_data_csv)      -> dict
    get_card_type_relative_win_rates(csv_path) -> dict
    get_overall_ratings(card_data_csv)        -> dict

NOTE: Modifier columns (Modifier_1_W … Modifier_5_W) are intentionally
excluded from all functions. Modifier data is incomplete and unreliable —
see CLAUDE.md "Known Issue: Modifier Data Not Reliable".
"""

import csv

from config import CHAOS_CARD_LIST, TYPING_OF_CHAOS_CARD


def get_card_win_rates(csv_path):
    """
    Read output.csv and return per-card win statistics.

    Returns a dict keyed by card name:
      {
        "Poison": {"win_rate": 0.72, "games_played": 11, "ban_rate": 0.25},
        ...
      }
    Cards with no games played have win_rate=None.

    Modifier_N_W columns are excluded via CHAOS_CARD_LIST filter — they must
    never appear in the AI pipeline as they contain incomplete data.
    """
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = sorted(
                list(reader),
                key=lambda r: r.get('timestamp', '') or ''
            )
    except FileNotFoundError:
        return {}

    total_games = len(rows)
    if total_games == 0 or not rows:
        return {}

    # Filter against CHAOS_CARD_LIST to exclude Modifier_N_W columns.
    # output.csv has Modifier_1_W … Modifier_5_W which would otherwise pass
    # the endswith('_W') check and corrupt the card stats.
    chaos_card_set = set(CHAOS_CARD_LIST)
    card_names = [
        col[:-2] for col in rows[0].keys()
        if col.endswith('_W') and col[:-2] in chaos_card_set
    ]

    stats = {}
    for name in card_names:
        w_col   = f"{name}_W"
        l_col   = f"{name}_L"
        ban_col = f"{name}_BANNED"
        wins    = 0
        losses  = 0
        bans    = 0

        for row in rows:
            try:
                if int(row.get(w_col, 0)) == 1:
                    wins += 1
                if int(row.get(l_col, 0)) == 1:
                    losses += 1
                ban_val = row.get(ban_col, '0')
                if str(ban_val) in ('1', '-1'):
                    bans += 1
            except (ValueError, TypeError):
                pass

        games_played = wins + losses
        stats[name] = {
            "win_rate":     round(wins / games_played, 3) if games_played > 0 else None,
            "games_played": games_played,
            "ban_rate":     round(bans / total_games, 3)  if total_games  > 0 else 0.0,
        }

    return stats


def get_matchup_win_rates(card_data_csv):
    """
    Read card_data.csv and return head-to-head win rates for every card pair.

    Returns a nested dict:
      {
        "Poison": {
          "Fireball": {"win_rate": 0.65, "matchup_rating": 0.61},
          ...
        },
        ...
      }
    Only includes pairs with at least 1 game of head-to-head data.
    matchup_rating is None if the column is not yet present in the CSV.
    """
    stats = {}
    try:
        with open(card_data_csv, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                c1 = row.get("card_1", "").strip()
                c2 = row.get("card_2", "").strip()
                try:
                    gp = int(row.get("Games Played", 0) or 0)
                    w  = int(row.get("card_1_W", 0)     or 0)
                except (ValueError, TypeError):
                    continue
                if not c1 or not c2 or gp == 0:
                    continue
                win_rate       = round(w / gp, 3)
                matchup_rating = None
                raw = row.get("card_1_matchup_rating", None)
                if raw not in (None, ""):
                    try:
                        matchup_rating = float(raw)
                    except (ValueError, TypeError):
                        pass
                stats.setdefault(c1, {})[c2] = {
                    "win_rate":       win_rate,
                    "matchup_rating": matchup_rating,
                }
    except FileNotFoundError:
        pass
    return stats


def get_card_type_relative_win_rates(csv_path):
    """
    Compute each card's win rate delta vs the average win rate of all cards
    sharing its type (from TYPING_OF_CHAOS_CARD in config.py).

    Returns:
      {"Goblin Hut": +0.102, "Mortar": -0.033, ...}  # delta as decimal
      None for a card if it has no win rate data.
    """
    card_stats = get_card_win_rates(csv_path)

    # Build card -> type lookup
    card_type = {}
    for type_name, cards in TYPING_OF_CHAOS_CARD.items():
        for card in cards:
            card_type[card] = type_name

    # Compute average win rate per type (skip cards with no data)
    type_win_rates = {}
    for type_name, cards in TYPING_OF_CHAOS_CARD.items():
        wrs = [
            card_stats[c]["win_rate"] for c in cards
            if c in card_stats and card_stats[c]["win_rate"] is not None
        ]
        type_win_rates[type_name] = sum(wrs) / len(wrs) if wrs else None

    result = {}
    for card in CHAOS_CARD_LIST:
        ctype  = card_type.get(card)
        cstats = card_stats.get(card)
        if cstats is None or cstats["win_rate"] is None or ctype is None:
            result[card] = None
            continue
        type_avg = type_win_rates.get(ctype)
        if type_avg is None:
            result[card] = None
            continue
        result[card] = round(cstats["win_rate"] - type_avg, 4)

    return result


def get_overall_ratings(card_data_csv):
    """
    Read card_1_overall_rating from card_data.csv.
    Returns only the first occurrence per card_1 (value is identical across
    all rows sharing the same card_1).

    Returns:
      {"Goblin Hut": 0.61, "Baby Dragon": 0.55, ...}
    """
    ratings = {}
    try:
        with open(card_data_csv, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                c1 = row.get("card_1", "").strip()
                if not c1 or c1 in ratings:
                    continue
                raw = row.get("card_1_overall_rating", None)
                if raw not in (None, ""):
                    try:
                        ratings[c1] = float(raw)
                    except (ValueError, TypeError):
                        pass
    except FileNotFoundError:
        pass
    return ratings

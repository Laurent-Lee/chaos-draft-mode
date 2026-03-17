"""
tier_calculator.py — Compute Bayesian-adjusted ratings for card_data.csv.

Public API:
    calculate_ratings(card_data_csv, output_csv)

Called at the end of _write_matchups_csv() in stats.py to append
card_1_overall_rating and card_1_matchup_rating columns to card_data.csv.
"""

import csv
import os

from backend.get_card_data import get_card_win_rates


def _bayesian_rating(n, win_rate):
    """
    Bayesian-adjusted rating:
        rating = ((n + 3) / (n + 4))^2 * win_rate

    When n == 0 (no games): win_rate is forced to 1.0, giving an optimistic
    prior of 0.5625. As game count grows the weight of the actual win_rate
    increases.
    """
    if n == 0:
        win_rate = 1.0
    return round(((n + 3) / (n + 4)) ** 2 * win_rate, 4)


def calculate_ratings(card_data_csv, output_csv):
    """
    Compute card_1_overall_rating and card_1_matchup_rating for every row in
    card_data.csv and rewrite the file with these two columns appended.

    card_1_overall_rating : Bayesian rating using card_1's overall win rate
                            and total game count from output.csv.
    card_1_matchup_rating : Bayesian rating using the (card_1, card_2) matchup
                            win rate and game count from card_data.csv itself.
    """
    card_stats = get_card_win_rates(output_csv)

    if not os.path.exists(card_data_csv):
        return

    with open(card_data_csv, newline='', encoding='utf-8') as f:
        reader         = csv.DictReader(f)
        original_fields = list(reader.fieldnames or [])
        rows            = list(reader)

    if not rows:
        return

    new_fields = list(original_fields)
    for col in ("card_1_overall_rating", "card_1_matchup_rating"):
        if col not in new_fields:
            new_fields.append(col)

    updated_rows = []
    for row in rows:
        c1     = row.get("card_1", "").strip()
        cstats = card_stats.get(c1)

        # Overall rating — use actual win rate if available, else n=0 prior
        if cstats and cstats["win_rate"] is not None:
            overall_n  = cstats["games_played"]
            overall_wr = cstats["win_rate"]
        else:
            overall_n  = 0
            overall_wr = 1.0  # triggers n==0 branch in _bayesian_rating
        row["card_1_overall_rating"] = _bayesian_rating(overall_n, overall_wr)

        # Matchup rating — use actual matchup win rate if games exist
        try:
            gp = int(row.get("Games Played", 0) or 0)
            w  = int(row.get("card_1_W",     0) or 0)
        except (ValueError, TypeError):
            gp, w = 0, 0
        matchup_wr = (w / gp) if gp > 0 else 1.0
        row["card_1_matchup_rating"] = _bayesian_rating(gp, matchup_wr)

        updated_rows.append(row)

    with open(card_data_csv, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=new_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(updated_rows)

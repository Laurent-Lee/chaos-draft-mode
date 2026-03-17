"""
Clash Royale Draft — ELO Calculator
=====================================
Reads output.csv (oldest → newest) and calculates each player's ELO
using the standard chess ELO formula after every game.

Usage:
    python elo.py                  # reads output.csv, writes elo.csv
    python elo.py --input  path/to/output.csv
    python elo.py --output path/to/elo.csv

ELO rules:
  - All players start at 1000
  - K-factor: 32  (standard for players under 2100)
  - Expected score:  E = 1 / (1 + 10 ^ ((opponent_elo - player_elo) / 400))
  - New ELO:         R' = R + K * (actual - expected)
    where actual = 1 for a win, 0 for a loss
"""

import argparse
import csv
import json
import os
import sys

# ── Config ────────────────────────────────────────────────────────────────────
_ROOT              = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PLAYER_TAGS_FILE  = os.path.join(_ROOT, "data", "player_tags.json")

def _load_players():
    try:
        with open(_PLAYER_TAGS_FILE, "r", encoding="utf-8") as f:
            return list(json.load(f).keys())
    except (FileNotFoundError, json.JSONDecodeError):
        return []

PLAYERS        = _load_players()
STARTING_ELO   = 1000
K_FACTOR       = 32
INPUT_CSV      = os.path.join(_ROOT, "data", "output.csv")
OUTPUT_CSV     = os.path.join(_ROOT, "data", "elo.csv")


# ── ELO math ──────────────────────────────────────────────────────────────────
def expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that player A beats player B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_elo(winner_elo: float, loser_elo: float, k: int = K_FACTOR):
    """Return (new_winner_elo, new_loser_elo)."""
    e_win  = expected_score(winner_elo, loser_elo)
    e_lose = expected_score(loser_elo,  winner_elo)
    new_winner = round(winner_elo + k * (1 - e_win),  2)
    new_loser  = round(loser_elo  + k * (0 - e_lose), 2)
    return new_winner, new_loser


# ── Main ──────────────────────────────────────────────────────────────────────
def calculate_elo(input_path: str, output_path: str, game_mode_filter: str = None) -> None:
    if not os.path.exists(input_path):
        print(f"❌  Input file not found: {input_path}")
        sys.exit(1)

    # Initialise every known player at the starting ELO
    elo = {p: float(STARTING_ELO) for p in PLAYERS}

    # Rows written to elo.csv: one row per game, showing ELO after that game
    snapshot_rows = []  # list of dicts

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "winner" not in (reader.fieldnames or []):
            print("❌  output.csv is missing the 'winner' column — is it empty?")
            sys.exit(1)

        rows = list(reader)
        rows.sort(key=lambda r: r.get("timestamp", ""))
        if game_mode_filter:
            rows = [r for r in rows if r.get("game_mode", "").strip() == game_mode_filter]

        for game_num, row in enumerate(rows, start=1):
            winner = row["winner"].strip()
            loser  = row["loser"].strip()

            if not winner or not loser:
                print(f"⚠️   Skipping row {game_num}: missing winner or loser.")
                continue

            # Auto-register any player not in the starting list
            for p in (winner, loser):
                if p not in elo:
                    print(f"ℹ️   New player '{p}' added at ELO {STARTING_ELO}.")
                    elo[p] = float(STARTING_ELO)

            # Calculate new ELOs
            new_winner_elo, new_loser_elo = update_elo(elo[winner], elo[loser])
            delta_winner = round(new_winner_elo - elo[winner], 2)
            delta_loser  = round(new_loser_elo  - elo[loser],  2)

            elo[winner] = new_winner_elo
            elo[loser]  = new_loser_elo

            # Snapshot: ELO for every player after this game
            snap = {
                "game":         game_num,
                "timestamp":    row.get("timestamp", ""),
                "winner":       winner,
                "loser":        loser,
                "winner_delta": f"+{delta_winner}" if delta_winner >= 0 else str(delta_winner),
                "loser_delta":  f"+{delta_loser}"  if delta_loser  >= 0 else str(delta_loser),
            }
            for p in sorted(elo):
                snap[p] = elo[p]
            snapshot_rows.append(snap)

    if not snapshot_rows:
        print("⚠️   No games found in output.csv — elo.csv will show starting ratings only.")
        snapshot_rows.append({
            "game": 0, "winner": "—", "loser": "—",
            "winner_delta": "—", "loser_delta": "—",
            **{p: float(STARTING_ELO) for p in sorted(elo)},
        })

    # Build column order: metadata first, then players sorted by final ELO desc
    player_cols = sorted(elo, key=lambda p: elo[p], reverse=True)
    fieldnames  = ["game", "timestamp", "winner", "loser", "winner_delta", "loser_delta"] + player_cols

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in snapshot_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    # ── Final leaderboard printed to terminal ─────────────────────────────────
    print(f"\n✅  Processed {len(snapshot_rows)} game(s).  Results written to: {output_path}\n")
    print("── Final ELO Leaderboard ──────────────────────────────")
    ranked = sorted(elo.items(), key=lambda x: x[1], reverse=True)
    for rank, (player, rating) in enumerate(ranked, start=1):
        bar   = "█" * int((rating - 800) / 20)   # visual bar scaled to range
        print(f"  {rank}.  {player:<12}  {rating:>7.1f}  {bar}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate ELO ratings from CR draft results.")
    parser.add_argument("--input",  default=INPUT_CSV,  help=f"Path to input CSV  (default: {INPUT_CSV})")
    parser.add_argument("--output", default=OUTPUT_CSV, help=f"Path to output CSV (default: {OUTPUT_CSV})")
    args = parser.parse_args()

    calculate_elo(args.input, args.output)
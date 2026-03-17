"""
ai_draft.py — AI draft logic using Ollama for local LLM inference.

Public API:
    get_card_stats(csv_path) -> dict
    ai_decide(phase, pool, my_picks, opp_picks, card_stats, model) -> card_id | None
"""

import csv
import json
import random
import re


# ── Card stats from output.csv ─────────────────────────────────────────────────

def get_card_stats(csv_path):
    """
    Read output.csv and return per-card win statistics.

    Returns a dict keyed by card name:
      {
        "Poison": {"win_rate": 0.72, "games_played": 11, "ban_rate": 0.25},
        ...
      }
    Cards with no games played have win_rate=None.
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

    # Identify card names from _W columns
    card_names = [col[:-2] for col in rows[0].keys() if col.endswith('_W')]

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
            "ban_rate":     round(bans / total_games, 3) if total_games > 0 else 0.0,
        }

    return stats


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _format_card_list(pool_names, card_stats):
    """Format pool cards with their stats, sorted by win rate descending."""
    rows = []
    for name in pool_names:
        s = card_stats.get(name)
        if s and s["win_rate"] is not None:
            rows.append((name, s["win_rate"], s["games_played"]))
        else:
            rows.append((name, -1.0, 0))

    rows.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for name, wr, gp in rows:
        if wr >= 0:
            lines.append(f"  {name}: {wr * 100:.0f}% WR ({gp} games)")
        else:
            lines.append(f"  {name}: no data")
    return "\n".join(lines)


def build_prompt(phase, pool_names, my_picks, opp_picks, card_stats):
    """
    Build the LLM prompt for a ban or pick decision.

    Args:
        phase:       "ban" or "pick"
        pool_names:  list of card names still in the pool
        my_picks:    list of card names already in the AI's deck
        opp_picks:   list of card names already in the opponent's deck
        card_stats:  dict from get_card_stats()

    Returns:
        str prompt
    """
    card_list = _format_card_list(pool_names, card_stats)
    my_str    = ", ".join(my_picks) if my_picks else "none yet"
    opp_str   = ", ".join(opp_picks) if opp_picks else "none yet"

    if phase == "ban":
        task = (
            "Your task: choose ONE card to BAN from the available pool.\n"
            "Strategy: ban the highest win-rate card the opponent could use against you.\n"
            "Do NOT attempt to ban a card not listed in the pool.\n"
            f"Your current picks so far: {my_str}\n"
            f"Opponent's current picks so far: {opp_str}"
        )
    else:
        task = (
            "Your task: choose ONE card to PICK for your deck.\n"
            "Strategy: pick the card with the best win rate that fits your current deck.\n"
            "Do NOT attempt to pick a card not listed in the pool.\n"
            f"Your current picks so far: {my_str}\n"
            f"Opponent's current picks so far: {opp_str}"
        )

    prompt = f"""You are drafting a deck in Clash Royale CHAOS mode.
Context: 50-card pool, players take turns banning (2 each) then picking cards in a snake draft (8 picks each). Higher win-rate cards win more games historically.

Available cards in the pool (sorted by win rate, highest first):
{card_list}

{task}

Respond with ONLY valid JSON in exactly this format (no other text, no markdown):
{{"card": "Exact Card Name", "reason": "brief one-line reason"}}

The card name MUST exactly match one of the names listed above."""

    return prompt


# ── Ollama caller ──────────────────────────────────────────────────────────────

def _fuzzy_match(name, pool_names):
    """Case-insensitive / punctuation-insensitive match against pool names."""
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', s.lower())

    name_norm = norm(name)
    for p in pool_names:
        if norm(p) == name_norm:
            return p
    # partial match fallback
    for p in pool_names:
        if name_norm in norm(p) or norm(p) in name_norm:
            return p
    return None


def _best_card_by_winrate(pool, card_stats):
    """Return (card_id, reason) for the highest win-rate card in the pool."""
    best    = None
    best_wr = -1.0
    for c in pool:
        s  = card_stats.get(c["name"])
        wr = s["win_rate"] if (s and s["win_rate"] is not None) else 0.0
        if wr > best_wr:
            best_wr = wr
            best    = c
    if best:
        wr_str = f"{best_wr * 100:.0f}% WR" if best_wr >= 0 else "no data"
        return best["id"], f"fallback: highest win-rate card available ({wr_str})"
    if pool:
        c = random.choice(pool)
        return c["id"], "fallback: random pick (no win-rate data)"
    return None, ""


def ai_decide(phase, pool, my_picks, opp_picks, card_stats, model):
    """
    Ask Ollama to choose the next ban or pick card.

    Args:
        phase:       "ban" or "pick"
        pool:        list of card dicts (id, name, elixir, ...)
        my_picks:    list of card dicts already in the current player's deck
        opp_picks:   list of card dicts in the opponent's deck so far
        card_stats:  dict from get_card_stats()
        model:       Ollama model name string (e.g. "llama3.2")

    Returns:
        (card_id, reason) tuple. card_id is None if pool is empty.
        Falls back to the highest win-rate card on any Ollama error.
    """
    if not pool:
        return None, ""

    pool_names = [c["name"] for c in pool]
    my_names   = [c["name"] for c in my_picks]
    opp_names  = [c["name"] for c in opp_picks]
    prompt     = build_prompt(phase, pool_names, my_names, opp_names, card_stats)

    try:
        import ollama  # lazy import — missing package falls through to best-by-winrate

        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )
        raw         = response["message"]["content"]
        data        = json.loads(raw)
        chosen_name = data.get("card", "")
        reason      = data.get("reason", "")

        matched = _fuzzy_match(chosen_name, pool_names)
        if matched:
            card = next((c for c in pool if c["name"] == matched), None)
            if card:
                print(f"[ai_draft] {phase.upper()}: chose '{matched}' (reason: {reason})")
                return card["id"], reason

        print(f"[ai_draft] LLM returned '{chosen_name}' which isn't in pool; falling back.")

    except ImportError:
        print("[ai_draft] 'ollama' package not installed — falling back to best win-rate card.")
    except Exception as e:
        print(f"[ai_draft] Ollama error ({e}) — falling back to best win-rate card.")

    return _best_card_by_winrate(pool, card_stats)

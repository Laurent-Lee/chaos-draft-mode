"""
ai_draft.py — AI draft logic using Ollama for local LLM inference.

Public API:
    get_card_stats(csv_path)           -> dict   (alias for get_card_win_rates)
    get_matchup_stats(card_data_csv)   -> dict   (alias for get_matchup_win_rates)
    ai_decide(phase, pool, my_picks, opp_picks, card_stats, model,
              matchup_stats=None)      -> (card_id, reason)

NOTE: Modifier data is intentionally excluded from this entire module.
      Modifier columns in output.csv are incomplete and unreliable — see
      CLAUDE.md "Known Issue: Modifier Data Not Reliable".
"""

import json
import random
import re

from config import TIER_CARDS, TYPING_OF_CHAOS_CARD, CSV_FILE, CARD_DATA_CSV
from backend.get_card_data import (
    get_card_win_rates    as get_card_stats,      # preserves existing public alias
    get_matchup_win_rates as get_matchup_stats,   # preserves existing public alias
    get_card_type_relative_win_rates,
    get_overall_ratings,
)

# ── Reverse lookup dicts (built once at module load) ──────────────────────────

# card_name -> type string  (e.g. "Goblin Hut" -> "Tower")
type_lookup = {
    card: type_name
    for type_name, cards in TYPING_OF_CHAOS_CARD.items()
    for card in cards
}

# card_name -> tier string  (e.g. "Electro Wizard" -> "S+")
tier_lookup = {
    card: tier
    for tier, cards in TIER_CARDS.items()
    for card in cards
}


# ── Context selection ─────────────────────────────────────────────────────────

def _select_ban_context(pool_names, overall_ratings, n=12):
    """
    Return the top-N pool cards by overall_rating for the ban phase.

    Ban decisions are purely rating-driven — the LLM should deny the opponent
    the strongest available cards, so we show only the highest-rated ones.
    Counter/matchup data is irrelevant here.
    """
    def rating_key(name):
        return overall_ratings.get(name) or 0.0

    return sorted(pool_names, key=rating_key, reverse=True)[:n]


def _select_pick_context(pool_names, opp_picks, matchup_stats, overall_ratings,
                         exclude_types=None):
    """
    Return a focused subset of pool_names for the pick phase.

    Selection logic:
      1. Top 10 pool cards by overall_rating (highest first), excluding any
         card whose type is in exclude_types (already-filled mandatory slots).
      2. For each card in opp_picks, add the pool card with the best
         matchup_rating against it (as a counter option), also honouring
         exclude_types.
      3. Deduplicate; order: top-rated first, then counter-only additions.

    Args:
        exclude_types: set of type strings to ignore (e.g. {"Tower", "Spells"}).
                       A type is only excluded when it has reached its target
                       count in _TARGET_COMPOSITION — caller is responsible for
                       computing this correctly (see ai_decide).
    """
    excluded = exclude_types or set()

    def is_allowed(name):
        return type_lookup.get(name) not in excluded

    def rating_key(name):
        return overall_ratings.get(name) or 0.0

    eligible    = [n for n in pool_names if is_allowed(n)]
    sorted_pool = sorted(eligible, key=rating_key, reverse=True)
    top10       = sorted_pool[:10]

    # Best counter per opponent pick (by matchup_rating, fall back to win_rate)
    seen            = set(top10)
    unique_counters = []
    for opp in opp_picks:
        best_card   = None
        best_rating = -1.0
        for card in eligible:
            mu = matchup_stats.get(card, {}).get(opp)
            if mu is None:
                continue
            mr = mu.get("matchup_rating")
            if mr is None:
                mr = mu.get("win_rate", 0.0)
            if mr > best_rating:
                best_rating = mr
                best_card   = card
        if best_card and best_card not in seen:
            seen.add(best_card)
            unique_counters.append(best_card)

    return top10 + unique_counters


# ── Prompt builder ─────────────────────────────────────────────────────────────

def _format_card_list(pool_names, card_stats, type_lookup, tier_lookup,
                      type_deltas=None, overall_ratings=None):
    """
    Format pool cards with extended stats, sorted by overall rating descending.

    Line format:
      Goblin Hut [Tower] (S): 65% WR | rating: 0.61 | +10.2% vs Tower avg
      Giant [Tanks] (B): no data | rating: 0.56
    """
    rows = []
    for name in pool_names:
        s      = card_stats.get(name)
        rating = (overall_ratings or {}).get(name)
        rating = rating if rating is not None else 0.0
        rows.append((name, rating, s))

    rows.sort(key=lambda x: x[1], reverse=True)

    lines = []
    for name, rating, s in rows:
        ctype = type_lookup.get(name, "?")
        tier  = tier_lookup.get(name, "?")

        if s and s["win_rate"] is not None:
            wr_str = f"{s['win_rate'] * 100:.0f}% WR"
        else:
            wr_str = "no data"

        rating_str = f"rating: {rating:.2f}"

        delta = (type_deltas or {}).get(name)
        if delta is not None:
            sign      = "+" if delta >= 0 else ""
            delta_str = f" | {sign}{delta * 100:.1f}% vs {ctype} avg"
        else:
            delta_str = ""

        lines.append(
            f"  {name} [{ctype}] ({tier}): {wr_str} | {rating_str}{delta_str}"
        )
    return "\n".join(lines)


def _format_counter_analysis(pool_names, opp_picks, matchup_stats):
    """
    For the pick phase: rank each pool card by its historical win rate when
    facing the opponent's already-picked cards.

    Returns a formatted string section, or "" if there is no matchup data.
    """
    if not opp_picks or not matchup_stats:
        return ""

    rows = []
    for card in pool_names:
        card_mu  = matchup_stats.get(card, {})
        matchups = [
            (opp, card_mu[opp]["win_rate"])
            for opp in opp_picks
            if opp in card_mu
        ]
        if not matchups:
            continue
        avg_wr = sum(wr for _, wr in matchups) / len(matchups)
        detail = ", ".join(f"vs {opp}: {wr * 100:.0f}%" for opp, wr in matchups)
        rows.append((card, avg_wr, len(matchups), detail))

    if not rows:
        return ""

    rows.sort(key=lambda x: x[1], reverse=True)

    lines = [
        f"\nCounter-pick analysis — pool cards ranked by win rate against "
        f"opponent's picks ({', '.join(opp_picks)}):",
        "  (Higher % = historically beats decks containing those opponent cards)",
    ]
    for card, avg_wr, n, detail in rows:
        lines.append(
            f"  {card}: {avg_wr * 100:.0f}% avg "
            f"[{detail}] ({n} matchup{'s' if n != 1 else ''} with data)"
        )
    return "\n".join(lines)



def build_ban_prompt(pool_names, my_picks, opp_picks, card_stats,
                     type_deltas=None, overall_ratings=None):
    """
    Build the LLM prompt for a ban decision.

    Shows only the top-rated pool cards. Ban strategy is purely rating-driven:
    deny the opponent the strongest available card.

    Args:
        pool_names:      full list of card names still in the pool
        my_picks:        list of card names already in the AI's deck
        opp_picks:       list of card names already in the opponent's deck
        card_stats:      dict from get_card_stats()
        type_deltas:     dict from get_card_type_relative_win_rates(), optional
        overall_ratings: dict from get_overall_ratings(), optional

    Returns:
        str prompt
    """
    context_names = _select_ban_context(pool_names, overall_ratings or {})

    card_list = _format_card_list(
        context_names, card_stats, type_lookup, tier_lookup,
        type_deltas=type_deltas, overall_ratings=overall_ratings,
    )
    my_str  = ", ".join(my_picks)  if my_picks  else "none yet"
    opp_str = ", ".join(opp_picks) if opp_picks else "none yet"

    task = (
        "Your task: choose ONE card to BAN from the available pool.\n"
        "Strategy:\n"
        "  Ban the card with the HIGHEST overall rating from the list above.\n"
        "  The cards are already sorted highest-rated first — ban the top card\n"
        "  unless you have a strong reason to prefer the second or third.\n"
        "  Trust the rating — it reflects LOCAL win-rate data, not the general\n"
        "  Clash Royale meta. Ignore your prior knowledge of card strength.\n"
        "Do NOT attempt to ban a card not listed in the pool.\n"
        f"Your current picks so far: {my_str}\n"
        f"Opponent's current picks so far: {opp_str}"
    )

    prompt = f"""You are a Clash Royale CHAOS mode draft expert.

Game context:
- 50-card CHAOS pool. Players first ban 4 cards total (2 each), then snake-draft 16 picks (8 per player).
- Historical ratings come from real games played with this card pool — trust them over general meta knowledge.

Top-rated cards remaining in the pool (sorted by overall rating, highest first):
{card_list}

{task}

Respond with ONLY valid JSON in exactly this format (no other text, no markdown):
{{"card": "Exact Card Name", "reason": "brief one-line reason"}}

The card name MUST exactly match one of the names listed above."""

    return prompt


_TARGET_COMPOSITION = {"Tanks": 1, "Spells": 2, "Ranged": 1, "Melee": 1, "Tower": 1}


def _format_deck_composition(my_picks):
    """
    Return a structured summary of the AI's current deck including explicit
    NEEDS / COVERED lines so small LLMs don't have to infer them.

    Example output:
      Current deck (3 cards): Giant [Tanks], Fireball [Spells], Mortar [Tower]
      Type tally  — Tanks: 1, Spells: 1, Tower: 1
      Still needs — Spells: 1 more, Ranged: 1, Melee: 1
      Already covered — Tanks (1/1), Tower (1/1)
      NOTE: Do NOT pick another Tower or Tanks — those slots are already filled.
    """
    if not my_picks:
        needs = ", ".join(
            f"{t}: {n}" for t, n in _TARGET_COMPOSITION.items()
        )
        return f"Current deck: none yet\n  Still needs — {needs}"

    entries     = [f"{n} [{type_lookup.get(n, '?')}]" for n in my_picks]
    type_counts: dict = {}
    for n in my_picks:
        t = type_lookup.get(n, "?")
        type_counts[t] = type_counts.get(t, 0) + 1

    tally = ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items()))

    needs_parts    = []
    covered_parts  = []
    avoid_types    = []
    for t, target in _TARGET_COMPOSITION.items():
        have = type_counts.get(t, 0)
        if have < target:
            still = target - have
            needs_parts.append(f"{t}: {still} more" if have > 0 else f"{t}: {still}")
        else:
            covered_parts.append(f"{t} ({have}/{target})")
            avoid_types.append(t)

    needs_str   = ", ".join(needs_parts)   if needs_parts   else "nothing — target met, pick best counter or highest-rated"
    covered_str = ", ".join(covered_parts) if covered_parts else "none yet"

    lines = [
        f"Current deck ({len(my_picks)} card{'s' if len(my_picks) != 1 else ''}): {', '.join(entries)}",
        f"  Type tally    — {tally}",
        f"  Still needs   — {needs_str}",
        f"  Already covered — {covered_str}",
    ]
    if avoid_types:
        avoid_str = " or ".join(avoid_types)
        lines.append(
            f"  Tip: A second {avoid_str} is rarely worth it — "
            f"{'those slots are' if len(avoid_types) > 1 else 'that slot is'} already covered. "
            f"Prefer filling the types listed under 'Still needs' unless the counter value is exceptional."
        )
    return "\n".join(lines)


def build_pick_prompt(pool_names, my_picks, opp_picks, card_stats,
                      type_deltas=None, overall_ratings=None, matchup_stats=None,
                      exclude_types=None):
    """
    Build the LLM prompt for a pick decision.

    Shows the top-rated cards plus the best counter per opponent pick.
    Pick strategy is counter-driven with deck balance as a secondary goal.

    Args:
        pool_names:      full list of card names still in the pool
        my_picks:        list of card names already in the AI's deck
        opp_picks:       list of card names already in the opponent's deck
        card_stats:      dict from get_card_stats()
        type_deltas:     dict from get_card_type_relative_win_rates(), optional
        overall_ratings: dict from get_overall_ratings(), optional
        matchup_stats:   dict from get_matchup_stats(), optional

    Returns:
        str prompt
    """
    context_names = _select_pick_context(
        pool_names, opp_picks, matchup_stats or {}, overall_ratings or {},
        exclude_types=exclude_types,
    )

    card_list       = _format_card_list(
        context_names, card_stats, type_lookup, tier_lookup,
        type_deltas=type_deltas, overall_ratings=overall_ratings,
    )
    matchup_section = _format_counter_analysis(context_names, opp_picks, matchup_stats)
    deck_composition = _format_deck_composition(my_picks)
    opp_str          = ", ".join(opp_picks) if opp_picks else "none yet"

    task = (
        "Your task: choose ONE card to PICK for your deck.\n"
        "Strategy:\n"
        "  1. COUNTER the opponent — prioritise cards with a high counter score against\n"
        "     the opponent's current picks (see counter-pick analysis below).\n"
        "  2. Build a balanced deck — aim for: 1× Tank, 2× Spells, 1× Ranged, 1× Melee,\n"
        "     1× Tower. The remaining 2 cards should fill missing types.\n"
        "     A second Tank is rarely correct — only pick one if the counter value is\n"
        "     exceptional AND you already have your Spell, Ranged, Melee, and Tower slots\n"
        "     covered. In nearly all cases, prefer a card that fills a missing type.\n"
        "  3. Use overall rating as a tiebreaker when counter data is limited.\n"
        "Do NOT attempt to pick a card not listed in the pool.\n"
        f"Opponent's current picks so far: {opp_str}"
        f"{matchup_section}"
    )

    prompt = f"""You are a Clash Royale CHAOS mode draft expert.

Game context:
- 50-card CHAOS pool. Players first ban 4 cards total (2 each), then snake-draft 16 picks (8 per player).
- CHAOS mode uses modifiers that amplify certain card types each game.
- A strong deck consists of: 1× Tank, 2× Spells, 1× Ranged, 1× Melee, 1× Tower.
  Fill remaining slots with missing types; a second Tank is only justified in rare cases.
- Each card's type is shown in [brackets] in the pool list below.
- Historical win rates and ratings come from real games played with this card pool.

Your current deck:
{deck_composition}

Available cards in the pool (sorted by overall rating, highest first):
{card_list}

{task}

Respond with ONLY valid JSON in exactly this format (no other text, no markdown):
{{"card": "Exact Card Name", "reason": "brief one-line reason mentioning counter-pick logic if applicable"}}

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


def _best_ban_card(pool, overall_ratings):
    """Fallback for ban: return the pool card with the highest overall_rating."""
    best        = None
    best_rating = -1.0
    for c in pool:
        r = overall_ratings.get(c["name"]) or 0.0
        if r > best_rating:
            best_rating = r
            best        = c
    if best:
        return best["id"], f"fallback: highest-rated card available (rating: {best_rating:.2f})"
    if pool:
        c = random.choice(pool)
        return c["id"], "fallback: random ban (no rating data)"
    return None, ""


def _best_pick_card(pool, card_stats):
    """Fallback for pick: return the pool card with the highest win rate."""
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


def ai_decide(phase, pool, my_picks, opp_picks, card_stats, model, matchup_stats=None):
    """
    Ask Ollama to choose the next ban or pick card.

    Ban and pick use entirely separate prompt strategies:
    - Ban:  top-rated cards shown; strategy is to ban the highest-rated card.
    - Pick: top-rated + counters shown; strategy is counter-pick + deck balance.

    Args:
        phase:         "ban" or "pick"
        pool:          list of card dicts (id, name, elixir, ...)
        my_picks:      list of card dicts already in the current player's deck
        opp_picks:     list of card dicts in the opponent's deck so far
        card_stats:    dict from get_card_stats()
        model:         Ollama model name string (e.g. "llama3.2")
        matchup_stats: dict from get_matchup_stats(), optional (used for pick only)

    Returns:
        (card_id, reason) tuple. card_id is None if pool is empty.
        Falls back to highest-rated card (ban) or highest win-rate card (pick)
        on any Ollama error.
    """
    if not pool:
        return None, ""

    pool_names      = [c["name"] for c in pool]
    my_names        = [c["name"] for c in my_picks]
    opp_names       = [c["name"] for c in opp_picks]
    type_deltas     = get_card_type_relative_win_rates(CSV_FILE)
    overall_ratings = get_overall_ratings(CARD_DATA_CSV)

    if phase == "ban":
        prompt   = build_ban_prompt(
            pool_names, my_names, opp_names, card_stats,
            type_deltas=type_deltas, overall_ratings=overall_ratings,
        )
        fallback = lambda: _best_ban_card(pool, overall_ratings)
    else:
        # Hard-enforce mandatory composition for picks 1-6.
        # Until all required types are filled, restrict the pool to cards
        # that satisfy a still-needed type.  Picks 7-8 are unrestricted.
        type_counts = {}
        for n in my_names:
            t = type_lookup.get(n)
            if t:
                type_counts[t] = type_counts.get(t, 0) + 1

        needed_types = {
            t for t, target in _TARGET_COMPOSITION.items()
            if type_counts.get(t, 0) < target
        }
        # Types at or above their target — exclude from context ranking so the
        # LLM's top-10 and counter lists don't surface cards the deck doesn't need.
        excluded_types = {
            t for t, target in _TARGET_COMPOSITION.items()
            if type_counts.get(t, 0) >= target
        }

        if needed_types:
            # Restrict pool to cards that fill a needed type
            restricted_pool       = [c for c in pool       if type_lookup.get(c["name"]) in needed_types]
            restricted_pool_names = [n for n in pool_names if type_lookup.get(n)         in needed_types]
            # Fall back to full pool if no matching cards exist (e.g. all Towers banned)
            if not restricted_pool:
                restricted_pool       = pool
                restricted_pool_names = pool_names
                excluded_types        = set()   # can't exclude if pool is unrestricted
        else:
            restricted_pool       = pool
            restricted_pool_names = pool_names

        prompt   = build_pick_prompt(
            restricted_pool_names, my_names, opp_names, card_stats,
            type_deltas=type_deltas, overall_ratings=overall_ratings,
            matchup_stats=matchup_stats,
            exclude_types=excluded_types,
        )
        fallback = lambda: _best_pick_card(restricted_pool, card_stats)

    try:
        import ollama  # lazy import — missing package falls through to fallback

        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )
        raw         = response["message"]["content"]
        data        = json.loads(raw)
        chosen_name = data.get("card", "")
        reason      = data.get("reason", "")

        valid_names = restricted_pool_names if phase == "pick" else pool_names
        valid_pool  = restricted_pool       if phase == "pick" else pool
        matched = _fuzzy_match(chosen_name, valid_names)
        if matched:
            card = next((c for c in valid_pool if c["name"] == matched), None)
            if card:
                print(f"[ai_draft] {phase.upper()}: chose '{matched}' (reason: {reason})")
                return card["id"], reason

        print(f"[ai_draft] LLM returned '{chosen_name}' which isn't in pool; falling back.")

    except ImportError:
        print("[ai_draft] 'ollama' package not installed — falling back.")
    except Exception as e:
        print(f"[ai_draft] Ollama error ({e}) — falling back.")

    return fallback()

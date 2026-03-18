"""
draft.py — Draft state, game logic, and draft API Blueprint.

Routes:
  POST /api/start
  GET  /api/<lobby_id>/state
  POST /api/<lobby_id>/action
  POST /api/<lobby_id>/undo
  POST /api/<lobby_id>/reset
  POST /api/<lobby_id>/ai_action
"""

import random
import secrets
from flask import Blueprint, jsonify, request
from config import (
    BAN_SEQUENCE, PICK_SEQUENCE,
    TIER_CARDS, CSV_FILE, CARD_DATA_CSV, OLLAMA_MODEL, PLAYERS,
)

_P1_DEFAULT = PLAYERS[0] if len(PLAYERS) > 0 else ""
_P2_DEFAULT = PLAYERS[1] if len(PLAYERS) > 1 else ""
from backend.cards import fetch_cards, deck_link
from backend.ai_draft import get_card_stats, get_matchup_stats, ai_decide

draft_bp = Blueprint("draft", __name__)

# ── Shared card cache (all lobbies use the same 50-card pool) ─────────────────
cards_cache = []

# ── Active lobbies ────────────────────────────────────────────────────────────
lobbies = {}  # lobby_id (str) -> state dict


def _make_lobby_state(p1, p2, ai_mode=False):
    return {
        "pool":         [],
        "banned":       [],
        "p1_picks":     [],
        "p2_picks":     [],
        "phase":        "setup",
        "action_index": 0,
        "p1_name":      p1,
        "p2_name":      p2,
        "1st_pick":     p1,
        "2nd_pick":     p2,
        "ai_mode":      ai_mode,
        "ai_log":       [],
    }


def get_state_view(st):
    """Return a serialisable snapshot of a lobby state."""
    phase = st["phase"]
    idx   = st["action_index"]
    seq   = BAN_SEQUENCE if phase == "ban" else (PICK_SEQUENCE if phase == "pick" else [])
    cur   = seq[idx] if idx < len(seq) else None
    return {
        "phase":          phase,
        "pool":           st["pool"],
        "banned":         st["banned"],
        "p1_picks":       st["p1_picks"],
        "p2_picks":       st["p2_picks"],
        "p1_name":        st["p1_name"],
        "p2_name":        st["p2_name"],
        "current_player": cur,
        "action_index":   idx,
        "ban_sequence":   BAN_SEQUENCE,
        "pick_sequence":  PICK_SEQUENCE,
        "p1_deck_link":   deck_link(st["p1_picks"]),
        "p2_deck_link":   deck_link(st["p2_picks"]),
        "ai_mode":        st["ai_mode"],
        "ai_log":         list(st["ai_log"]),
    }


def _get_lobby(lobby_id):
    return lobbies.get(lobby_id)


# ── Routes ────────────────────────────────────────────────────────────────────

@draft_bp.route("/api/start", methods=["POST"])
def start_draft():
    body = request.json or {}
    p1       = body.get("p1_name", _P1_DEFAULT)
    p2       = body.get("p2_name", _P2_DEFAULT)
    ai_mode  = bool(body.get("ai_mode", False))

    if not cards_cache:
        cards = fetch_cards()
        if isinstance(cards, dict) and "error" in cards:
            return jsonify({"error": cards["error"]}), 500
        cards_cache[:] = cards  # mutate in-place so all importers see the update

    lobby_id = secrets.token_hex(4)  # 8-char hex string
    st = _make_lobby_state(p1, p2, ai_mode)

    pool = list(cards_cache)
    st["pool"]         = pool
    st["phase"]        = "ban"
    st["action_index"] = 0

    first_picker  = p1 if PICK_SEQUENCE[0] == 1 else p2
    second_picker = p2 if first_picker == p1 else p1
    st["1st_pick"] = first_picker
    st["2nd_pick"] = second_picker

    # ── Random pre-bans: 2x S+ and 1x S ──────────────────────────────────────
    pool_by_name = {c["name"]: c for c in pool}
    splus_pool   = [pool_by_name[n] for n in TIER_CARDS["S+"] if n in pool_by_name]
    s_pool       = [pool_by_name[n] for n in TIER_CARDS["S"]  if n in pool_by_name]
    random_bans  = (random.sample(splus_pool, min(2, len(splus_pool))) +
                    random.sample(s_pool,     min(1, len(s_pool))))
    for card in random_bans:
        st["pool"]   = [c for c in st["pool"] if c["id"] != card["id"]]
        st["banned"].append({"card": card, "by": "random"})

    lobbies[lobby_id] = st

    view = get_state_view(st)
    view["lobby_id"] = lobby_id
    return jsonify(view)


@draft_bp.route("/api/<lobby_id>/state", methods=["GET"])
def get_state(lobby_id):
    st = _get_lobby(lobby_id)
    if st is None:
        return jsonify({"error": "Lobby not found"}), 404
    if st["phase"] == "setup":
        return jsonify({"phase": "setup"})
    view = get_state_view(st)
    view["lobby_id"] = lobby_id
    return jsonify(view)


@draft_bp.route("/api/<lobby_id>/action", methods=["POST"])
def do_action(lobby_id):
    st = _get_lobby(lobby_id)
    if st is None:
        return jsonify({"error": "Lobby not found"}), 404

    body    = request.json or {}
    card_id = body.get("card_id")
    phase   = st["phase"]

    if phase not in ("ban", "pick"):
        return jsonify({"error": "No action needed"}), 400

    seq = BAN_SEQUENCE if phase == "ban" else PICK_SEQUENCE
    idx = st["action_index"]

    if idx >= len(seq):
        return jsonify({"error": "Sequence complete"}), 400

    current = seq[idx]
    card    = next((c for c in st["pool"] if c["id"] == card_id), None)
    if not card:
        return jsonify({"error": "Card not in pool"}), 400

    st["pool"] = [c for c in st["pool"] if c["id"] != card_id]

    if phase == "ban":
        st["banned"].append({"card": card, "by": current})
    else:
        (st["p1_picks"] if current == 1 else st["p2_picks"]).append(card)

    st["action_index"] += 1

    if phase == "ban"  and st["action_index"] >= len(BAN_SEQUENCE):
        st["phase"]        = "pick"
        st["action_index"] = 0
    elif phase == "pick" and st["action_index"] >= len(PICK_SEQUENCE):
        st["phase"] = "done"

    view = get_state_view(st)
    view["lobby_id"] = lobby_id
    return jsonify(view)


@draft_bp.route("/api/<lobby_id>/ai_action", methods=["POST"])
def ai_action(lobby_id):
    """Perform the next ban/pick on behalf of the AI (used in AI draft mode)."""
    st = _get_lobby(lobby_id)
    if st is None:
        return jsonify({"error": "Lobby not found"}), 404

    phase = st["phase"]
    if phase not in ("ban", "pick"):
        return jsonify({"error": "No action needed"}), 400

    seq = BAN_SEQUENCE if phase == "ban" else PICK_SEQUENCE
    idx = st["action_index"]

    if idx >= len(seq):
        return jsonify({"error": "Sequence complete"}), 400

    current      = seq[idx]
    my_picks     = st["p1_picks"] if current == 1 else st["p2_picks"]
    opp_picks    = st["p2_picks"] if current == 1 else st["p1_picks"]
    player_name  = st["p1_name"] if current == 1 else st["p2_name"]

    card_stats     = get_card_stats(CSV_FILE)
    matchup_stats  = get_matchup_stats(CARD_DATA_CSV)
    card_id, reason = ai_decide(phase, st["pool"], my_picks, opp_picks, card_stats, OLLAMA_MODEL, matchup_stats)

    if card_id is None:
        return jsonify({"error": "No cards available"}), 400

    card = next((c for c in st["pool"] if c["id"] == card_id), None)
    if not card:
        return jsonify({"error": "Card not in pool"}), 400

    st["pool"] = [c for c in st["pool"] if c["id"] != card_id]

    if phase == "ban":
        st["banned"].append({"card": card, "by": current})
    else:
        (st["p1_picks"] if current == 1 else st["p2_picks"]).append(card)

    st["ai_log"].append({
        "player":      current,
        "player_name": player_name,
        "phase":       phase,
        "card":        card["name"],
        "reason":      reason,
    })

    st["action_index"] += 1

    if phase == "ban"  and st["action_index"] >= len(BAN_SEQUENCE):
        st["phase"]        = "pick"
        st["action_index"] = 0
    elif phase == "pick" and st["action_index"] >= len(PICK_SEQUENCE):
        st["phase"] = "done"

    view = get_state_view(st)
    view["lobby_id"] = lobby_id
    return jsonify(view)


@draft_bp.route("/api/<lobby_id>/undo", methods=["POST"])
def undo_action(lobby_id):
    """
    Undo the last player ban or pick (Normal Draft only).

    Works across phase boundaries:
      - Undoing when phase="pick" and action_index=0 steps back into the ban phase.
      - Undoing when phase="done" steps back into the pick phase.
    Random pre-bans are never undone.
    """
    st = _get_lobby(lobby_id)
    if st is None:
        return jsonify({"error": "Lobby not found"}), 404

    if st["ai_mode"]:
        return jsonify({"error": "Undo not available in AI Draft mode"}), 400

    phase = st["phase"]
    idx   = st["action_index"]

    if phase == "setup":
        return jsonify({"error": "Nothing to undo"}), 400

    def _undo_last_ban():
        player_bans = [b for b in st["banned"] if b["by"] != "random"]
        if not player_bans:
            return False
        last = player_bans[-1]
        st["banned"].remove(last)
        st["pool"].append(last["card"])
        return True

    if phase == "ban":
        if idx == 0:
            return jsonify({"error": "Nothing to undo"}), 400
        if not _undo_last_ban():
            return jsonify({"error": "Nothing to undo"}), 400
        st["action_index"] -= 1

    elif phase == "pick" and idx == 0:
        if not _undo_last_ban():
            return jsonify({"error": "Nothing to undo"}), 400
        st["phase"]        = "ban"
        st["action_index"] = len(BAN_SEQUENCE) - 1

    elif phase == "pick":
        prev_player = PICK_SEQUENCE[idx - 1]
        picks_list  = st["p1_picks"] if prev_player == 1 else st["p2_picks"]
        if not picks_list:
            return jsonify({"error": "Nothing to undo"}), 400
        st["pool"].append(picks_list.pop())
        st["action_index"] -= 1

    elif phase == "done":
        prev_player = PICK_SEQUENCE[-1]
        picks_list  = st["p1_picks"] if prev_player == 1 else st["p2_picks"]
        if not picks_list:
            return jsonify({"error": "Nothing to undo"}), 400
        st["pool"].append(picks_list.pop())
        st["phase"]        = "pick"
        st["action_index"] = len(PICK_SEQUENCE) - 1

    else:
        return jsonify({"error": "Nothing to undo"}), 400

    view = get_state_view(st)
    view["lobby_id"] = lobby_id
    return jsonify(view)


@draft_bp.route("/api/<lobby_id>/reset", methods=["POST"])
def reset(lobby_id):
    if lobby_id in lobbies:
        del lobbies[lobby_id]
    return jsonify({"phase": "setup"})

"""
draft.py — Draft state, game logic, and draft API Blueprint.

Routes:
  POST /api/start
  GET  /api/state
  POST /api/action
  POST /api/reset
"""

import random
from flask import Blueprint, jsonify, request
from config import (
    PLAYER1_NAME, PLAYER2_NAME,
    BAN_SEQUENCE, PICK_SEQUENCE,
    TIER_CARDS,
)
from backend.cards import fetch_cards, deck_link

draft_bp = Blueprint("draft", __name__)

# ── Global draft state ────────────────────────────────────────────────────────
state = {
    "cards":        [],
    "pool":         [],
    "banned":       [],
    "p1_picks":     [],
    "p2_picks":     [],
    "phase":        "setup",
    "action_index": 0,
    "p1_name":      PLAYER1_NAME,
    "p2_name":      PLAYER2_NAME,
    "1st_pick":     PLAYER1_NAME,
    "2nd_pick":     PLAYER2_NAME,
}


def get_state_view():
    """Return a serialisable snapshot of the current draft state."""
    phase = state["phase"]
    idx   = state["action_index"]
    seq   = BAN_SEQUENCE if phase == "ban" else (PICK_SEQUENCE if phase == "pick" else [])
    cur   = seq[idx] if idx < len(seq) else None
    return {
        "phase":          phase,
        "pool":           state["pool"],
        "banned":         state["banned"],
        "p1_picks":       state["p1_picks"],
        "p2_picks":       state["p2_picks"],
        "p1_name":        state["p1_name"],
        "p2_name":        state["p2_name"],
        "current_player": cur,
        "action_index":   idx,
        "ban_sequence":   BAN_SEQUENCE,
        "pick_sequence":  PICK_SEQUENCE,
        "p1_deck_link":   deck_link(state["p1_picks"]),
        "p2_deck_link":   deck_link(state["p2_picks"]),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@draft_bp.route("/api/start", methods=["POST"])
def start_draft():
    body = request.json or {}
    state["p1_name"] = body.get("p1_name", PLAYER1_NAME)
    state["p2_name"] = body.get("p2_name", PLAYER2_NAME)

    if not state["cards"]:
        cards = fetch_cards()
        if isinstance(cards, dict) and "error" in cards:
            return jsonify({"error": cards["error"]}), 500
        state["cards"] = cards

    pool = list(state["cards"])
    state["pool"]         = pool
    state["banned"]       = []
    state["p1_picks"]     = []
    state["p2_picks"]     = []
    state["phase"]        = "ban"
    state["action_index"] = 0

    first_picker  = state["p1_name"] if PICK_SEQUENCE[0] == 1 else state["p2_name"]
    second_picker = state["p2_name"] if first_picker == state["p1_name"] else state["p1_name"]
    state["1st_pick"] = first_picker
    state["2nd_pick"] = second_picker

    # ── Random pre-bans: 2x S+ and 1x S ──────────────────────────────────────
    pool_by_name = {c["name"]: c for c in state["pool"]}
    splus_pool   = [pool_by_name[n] for n in TIER_CARDS["S+"] if n in pool_by_name]
    s_pool       = [pool_by_name[n] for n in TIER_CARDS["S"]  if n in pool_by_name]
    random_bans  = (random.sample(splus_pool, min(2, len(splus_pool))) +
                    random.sample(s_pool,     min(1, len(s_pool))))
    for card in random_bans:
        state["pool"]   = [c for c in state["pool"] if c["id"] != card["id"]]
        state["banned"].append({"card": card, "by": "random"})

    return jsonify(get_state_view())


@draft_bp.route("/api/state", methods=["GET"])
def get_state():
    if state["phase"] == "setup":
        return jsonify({"phase": "setup"})
    return jsonify(get_state_view())


@draft_bp.route("/api/action", methods=["POST"])
def do_action():
    body    = request.json or {}
    card_id = body.get("card_id")
    phase   = state["phase"]

    if phase not in ("ban", "pick"):
        return jsonify({"error": "No action needed"}), 400

    seq = BAN_SEQUENCE if phase == "ban" else PICK_SEQUENCE
    idx = state["action_index"]

    if idx >= len(seq):
        return jsonify({"error": "Sequence complete"}), 400

    current = seq[idx]
    card    = next((c for c in state["pool"] if c["id"] == card_id), None)
    if not card:
        return jsonify({"error": "Card not in pool"}), 400

    state["pool"] = [c for c in state["pool"] if c["id"] != card_id]

    if phase == "ban":
        state["banned"].append({"card": card, "by": current})
    else:
        (state["p1_picks"] if current == 1 else state["p2_picks"]).append(card)

    state["action_index"] += 1

    if phase == "ban"  and state["action_index"] >= len(BAN_SEQUENCE):
        state["phase"]        = "pick"
        state["action_index"] = 0
    elif phase == "pick" and state["action_index"] >= len(PICK_SEQUENCE):
        state["phase"] = "done"

    return jsonify(get_state_view())


@draft_bp.route("/api/reset", methods=["POST"])
def reset():
    state.update({
        "phase":        "setup",
        "pool":         [],
        "banned":       [],
        "p1_picks":     [],
        "p2_picks":     [],
        "action_index": 0,
    })
    return jsonify({"phase": "setup"})
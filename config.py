"""
config.py — All constants and configuration for the CR Draft app.
"""

import json
import os
from dotenv import load_dotenv

# Absolute path to the project root (directory containing this file)
_ROOT = os.path.dirname(os.path.abspath(__file__))

load_dotenv()

CR_API_TOKEN  = os.getenv("CR_API_TOKEN", "")
PORT          = 5050

# ── Draft sequences ───────────────────────────────────────────────────────────
# Ban:  P1 bans 1, P2 bans 2, P1 bans 1
BAN_SEQUENCE  = [1, 2, 2, 1]
# Pick: snake draft — each player ends with 8 cards
PICK_SEQUENCE = [1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1, 1, 2, 2, 1]

# ── CSV / ELO ─────────────────────────────────────────────────────────────────
CSV_FILE          = os.path.join(_ROOT, "data", "output.csv")
CARD_DATA_CSV     = os.path.join(_ROOT, "data", "card_data.csv")
MODIFIERS_CSV     = os.path.join(_ROOT, "data", "modifiers_data.csv")
PLAYER_TAGS_FILE  = os.path.join(_ROOT, "data", "player_tags.json")
ELO_STARTING      = 1000
ELO_NORMAL_CSV    = os.path.join(_ROOT, "data", "elo_normal_draft.csv")
ELO_AI_CSV        = os.path.join(_ROOT, "data", "elo_ai_draft.csv")

# ── Known players (loaded from data/player_tags.json) ─────────────────────────
def _load_players():
    try:
        with open(PLAYER_TAGS_FILE, "r", encoding="utf-8") as f:
            return list(json.load(f).keys())
    except (FileNotFoundError, json.JSONDecodeError):
        return []

PLAYERS = _load_players()
OLLAMA_MODEL      = "llama3.2"   # swap to e.g. "qwen2.5:3b" for a faster/smaller model

# ── All 50 official C.H.A.O.S mode cards (March 2026) ─────────────────────────
CHAOS_CARDS = {
    "Electro Spirit", "Ice Spirit", "The Log", "Giant Snowball", "Rage",
    "Suspicious Bush", "Berserker", "Tombstone", "Vines", "Goblin Barrel",
    "Royal Delivery", "Princess", "Ice Wizard", "Fisherman", "Knight",
    "Dart Goblin", "Elixir Golem", "Mortar", "Fireball", "Poison",
    "Musketeer", "Goblin Hut", "Flying Machine", "Baby Dragon", "Rune Giant",
    "Zappies", "Furnace", "Hunter", "Electro Wizard", "Goblin Drill",
    "Goblin Demolisher", "Night Witch", "Mother Witch", "Graveyard",
    "Inferno Tower", "Giant", "Ram Rider", "Rascals", "Executioner",
    "Wizard", "Witch", "Rocket", "Royal Giant", "Barbarian Hut",
    "Goblin Giant", "X-Bow", "P.E.K.K.A", "Mega Knight", "Lava Hound", "Golem",
}

# Stable sorted list of all 50 CHAOS cards for consistent CSV column ordering
CHAOS_CARD_LIST = sorted(CHAOS_CARDS)

# ── Tier data (used for random pre-bans) ──────────────────────────────────────
TIER_CARDS = {
    "S+": ["Goblin Demolisher", "Electro Wizard", "Barbarian Hut", "Furnace"],
    "S":  ["Golem", "Goblin Barrel", "X-Bow", "Baby Dragon", "Vines", "Goblin Hut"],
}

# ── Card type mapping ─────────────────────────────────────────────────────────
TYPING_OF_CHAOS_CARD = {
    "Tower":  ["Inferno Tower", "Mortar", "Goblin Hut",
               "Barbarian Hut", "Goblin Drill", "Tombstone", "X-Bow"],
    "Tanks":  ["Elixir Golem", "Golem", "Rune Giant", "Giant", "Rascals",
               "Royal Giant", "Goblin Giant", "Lava Hound",
               "Mega Knight", "P.E.K.K.A"],
    "Ranged": ["Princess", "Ice Wizard", "Dart Goblin", "Musketeer",
               "Flying Machine", "Baby Dragon", "Zappies", "Furnace",
               "Hunter", "Electro Wizard", "Goblin Demolisher", "Mother Witch",
               "Executioner", "Wizard", "Witch"],
    "Melee":  ["Electro Spirit", "Ice Spirit", "Berserker", "Fisherman", "Knight",
               "Night Witch"],
    "Charge": ["Ram Rider", "Suspicious Bush", "Goblin Barrel"],
    "Spells": ["The Log", "Giant Snowball", "Rage", "Vines",
               "Fireball", "Poison", "Graveyard", "Rocket",
               "Royal Delivery"],
}
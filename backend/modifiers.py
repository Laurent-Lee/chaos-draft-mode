"""
modifiers.py — CHAOS modifier name mapping and modifiers_data.csv aggregation.

The CR API returns modifier identifiers like "Poison3" or "BlowdartGoblin3".
This module converts them to human-readable display names ("Poison III",
"Dart Goblin III") and maintains the running aggregate in modifiers_data.csv.

modifiers_data.csv structure
-----------------------------
  One row per unique modifier display name (e.g. "Poison III").
  Columns:
    modifier_name       — display name
    total_games_played  — total games in which this modifier appeared (either side)
    Modifier_1_W        — times picked 1st by the winning team
    Modifier_2_W        — times picked 2nd by the winning team
    Modifier_3_W        — times picked 3rd by the winning team
    Modifier_4_W        — times picked 4th by the winning team
    Modifier_5_W        — times picked 5th by the winning team
    Modifier_1_L        — times picked 1st by the losing team
    Modifier_2_L        — times picked 2nd by the losing team
    Modifier_3_L        — times picked 3rd by the losing team
    Modifier_4_L        — times picked 4th by the losing team
    Modifier_5_L        — times picked 5th by the losing team

With ~150 unique modifier variants (50 CHAOS cards × 3 tiers), each having
10 data columns, there are up to 1500 data points across the file.

The file is regenerated from scratch from output.csv after each recorded match,
analogous to how card_data.csv is handled.
"""

import csv
import os
import re

from config import CSV_FILE, MODIFIERS_CSV

# ── Tier suffix → Roman numeral ───────────────────────────────────────────────
_TIER_ROMAN = {"1": "I", "2": "II", "3": "III"}

# ── Internal base name → CHAOS card display name ──────────────────────────────
# Derived by cross-referencing modifier identifiers from the CR API against
# the actual card decks used in each game.  Add new entries here as previously
# unseen modifiers appear in future matches.
MODIFIER_BASE_TO_DISPLAY = {
    # Confirmed mappings (cross-referenced against card decks)
    "AxeMan":           "Executioner",       # Executioner throws axes
    "BabyDragon":       "Baby Dragon",
    "BarbarianHut":     "Barbarian Hut",
    "Berserker":        "Berserker",
    "BlowdartGoblin":   "Dart Goblin",       # Dart Goblin fires a blow dart
    "DartBarrell":      "Flying Machine",    # Flying Machine fires dart-like shots
    "ElectroSpirit":    "Electro Spirit",
    "ElectroWizard":    "Electro Wizard",
    "ElixirGolem":      "Elixir Golem",
    "Fireball":         "Fireball",
    "Fisherman":        "Fisherman",
    "Furnace":          "Furnace",
    "Giant":            "Giant",
    "GiantSnowball":    "Giant Snowball",
    "GoblinBarrel":     "Goblin Barrel",
    "GoblinDemolisher": "Goblin Demolisher",
    "GoblinDrill":      "Goblin Drill",
    "GoblinGiant":      "Goblin Giant",
    "GoblinHut":        "Goblin Hut",
    "Golem":            "Golem",
    "Graveyard":        "Graveyard",
    "Hunter":           "Hunter",
    "IceSpirits":       "Ice Spirit",        # API pluralises "Ice Spirit"
    "IceWizard":        "Ice Wizard",
    "InfernoTower":     "Inferno Tower",
    "Knight":           "Knight",
    "LavaHound":        "Lava Hound",
    "Log":              "The Log",
    "MegaKnight":       "Mega Knight",
    "Mortar":           "Mortar",
    "MotherWitch":      "Mother Witch",
    "Musketeer":        "Musketeer",
    "NightWitch":       "Night Witch",
    "Pekka":            "P.E.K.K.A",
    "Poison":           "Poison",
    "Princess":         "Princess",
    "Rage":             "Rage",
    "RamRider":         "Ram Rider",
    "Rascals":          "Rascals",
    "Rocket":           "Rocket",
    "RoyalDelivery":    "Royal Delivery",
    "RoyalGiant":       "Royal Giant",
    "RuneGiant":        "Rune Giant",
    "SuspiciousBush":   "Suspicious Bush",
    "Tombstone":        "Tombstone",
    "Vines":            "Vines",
    "Witch":            "Witch",
    "Wizard":           "Wizard",
    "Xbow":             "X-Bow",
    "Zappies":          "Zappies",
}

MODIFIER_COLS = (
    ["modifier_name", "total_games_played"]
    + [f"Modifier_{i}_W" for i in range(1, 6)]
    + [f"Modifier_{i}_L" for i in range(1, 6)]
)


# ── Public helpers ─────────────────────────────────────────────────────────────

def parse_modifier(internal: str):
    """Split "Poison3" → ("Poison", "3").  Returns ("...", "") if no trailing digit."""
    m = re.match(r"^(.+?)(\d+)$", internal)
    if m:
        return m.group(1), m.group(2)
    return internal, ""


def modifier_display_name(internal: str) -> str:
    """
    Convert an internal modifier string to a human-readable display name.

    Examples:
        "Poison3"         → "Poison III"
        "BlowdartGoblin3" → "Dart Goblin III"
        "DartBarrell1"    → "Flying Machine I"
        "AxeMan1"         → "Executioner I"
        "Xbow2"           → "X-Bow II"
    """
    base, tier = parse_modifier(internal)
    display_base = MODIFIER_BASE_TO_DISPLAY.get(base)
    if not display_base:
        # Fallback: insert spaces before each capital letter run
        display_base = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base)
    tier_str = _TIER_ROMAN.get(tier, tier)
    return f"{display_base} {tier_str}" if tier_str else display_base


# ── CSV generation ─────────────────────────────────────────────────────────────

def _build_modifier_agg():
    """
    Read output.csv and return a dict:
        {display_name: {"total_games_played": int, "1_W": int, ..., "5_L": int}}
    """
    agg = {}

    if not os.path.exists(CSV_FILE):
        return agg

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Collect winner modifiers (Modifier_1_W … Modifier_5_W)
            w_mods = [row.get(f"Modifier_{i}_W", "").strip() for i in range(1, 6)]
            # Collect loser modifiers (Modifier_1_L … Modifier_5_L)
            l_mods = [row.get(f"Modifier_{i}_L", "").strip() for i in range(1, 6)]

            # Skip rows that have no modifier data at all
            if not any(w_mods + l_mods):
                continue

            for pos, internal in enumerate(w_mods, start=1):
                if not internal:
                    continue
                name = modifier_display_name(internal)
                if name not in agg:
                    agg[name] = {"total_games_played": 0, **{f"{j}_W": 0 for j in range(1, 6)},
                                 **{f"{j}_L": 0 for j in range(1, 6)}}
                agg[name]["total_games_played"] += 1
                agg[name][f"{pos}_W"] += 1

            for pos, internal in enumerate(l_mods, start=1):
                if not internal:
                    continue
                name = modifier_display_name(internal)
                if name not in agg:
                    agg[name] = {"total_games_played": 0, **{f"{j}_W": 0 for j in range(1, 6)},
                                 **{f"{j}_L": 0 for j in range(1, 6)}}
                agg[name]["total_games_played"] += 1
                agg[name][f"{pos}_L"] += 1

    return agg


def write_modifiers_csv():
    """Recompute modifiers_data.csv from scratch using output.csv."""
    os.makedirs(os.path.dirname(MODIFIERS_CSV), exist_ok=True)
    agg = _build_modifier_agg()

    with open(MODIFIERS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MODIFIER_COLS)
        writer.writeheader()
        for name in sorted(agg):
            d = agg[name]
            writer.writerow({
                "modifier_name":      name,
                "total_games_played": d["total_games_played"],
                **{f"Modifier_{i}_W": d[f"{i}_W"] for i in range(1, 6)},
                **{f"Modifier_{i}_L": d[f"{i}_L"] for i in range(1, 6)},
            })


def refresh_modifiers():
    """Called after every recorded match to keep modifiers_data.csv current."""
    try:
        write_modifiers_csv()
    except Exception as e:
        print(f"[modifiers] CSV refresh failed: {e}")

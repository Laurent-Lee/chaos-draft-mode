"""
cards.py — CR API fetching and deck link generation.
"""

import requests as req
from config import CR_API_TOKEN, CHAOS_CARDS  # noqa: E402


def fetch_cards():
    """Fetch all cards from the CR API, filtered to CHAOS mode cards only."""
    headers = {"Authorization": f"Bearer {CR_API_TOKEN}"}
    url = "https://api.clashroyale.com/v1/cards?limit=200"
    r = req.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    items = r.json().get("items", [])
    cards = []
    for c in items:
        if c.get("name") not in CHAOS_CARDS:
            continue
        cards.append({
            "id":      c.get("id"),
            "name":    c.get("name", "?"),
            "elixir":  c.get("elixirCost", 0),
            "rarity":  c.get("rarity", ""),
            "type":    c.get("type", ""),
            "iconUrl": (c.get("iconUrls") or {}).get("medium", ""),
        })
    return cards


def deck_link(picks):
    """Generate a Clash Royale deep-link to import a deck from a list of card dicts."""
    ids = ";".join(str(c["id"]) for c in picks)
    return f"https://link.clashroyale.com/en/?clashroyale://copyDeck?deck={ids}&l=Royals&tt=159000000"
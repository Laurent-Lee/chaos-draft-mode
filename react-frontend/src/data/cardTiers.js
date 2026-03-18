export const TIER_ORDER = { "S+": 0, "S": 1, "A": 2, "B": 3, "C": 4, "D": 5, "F": 6 };
export const TIER_ICONS = { "S+": "💎", "S": "🥇", "A": "🥈", "B": "🥉", "C": "🔵", "D": "🟣", "F": "⬛" };

export const CARD_TIER = {};
{
  const tiers = {
    "S+": ["Goblin Demolisher","Electro Wizard","Barbarian Hut","Furnace"],
    "S":  ["Golem","Goblin Barrel","Baby Dragon","Vines","Goblin Hut","Graveyard"],
    "A":  ["Giant","Knight","Poison","The Log","Musketeer","Tombstone","Fireball","Suspicious Bush","Dart Goblin","X-Bow"],
    "B":  ["Witch","Electro Spirit","Ice Spirit","Executioner","Wizard","Flying Machine","Rascals","Rune Giant","Berserker","Goblin Giant","P.E.K.K.A"],
    "C":  ["Princess","Goblin Drill","Zappies","Royal Giant","Night Witch"],
    "D":  ["Royal Delivery","Berserker","Mega Knight","Ram Rider","Lava Hound","Elixir Golem"],
    "F":  ["Giant Snowball","Inferno Tower","Rocket","Hunter","Rage","Mother Witch","Fisherman","Ice Wizard","Mortar"]
  };
  for (const [tier, cards] of Object.entries(tiers))
    cards.forEach(c => CARD_TIER[c] = tier);
}

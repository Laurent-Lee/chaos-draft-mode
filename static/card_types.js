/**
 * card_types.js — CHAOS mode card type assignments.
 *
 * Edit this file to update card types without touching index.html.
 * TYPE_ORDER controls the display order of type groups in the pool.
 * TYPE_ICONS maps type names to emoji shown in group headers.
 */

const TYPE_ORDER = {
  "Tower": 0, "Tanks": 1, "Ranged": 2, "Melee": 3, "Charge": 4, "Spells": 5
};

const TYPE_ICONS = {
  "Tower": "🏰", "Tanks": "🛡️", "Ranged": "🏹", "Melee": "⚔️", "Charge": "💨", "Spells": "✨"
};

const CARD_TYPE = {
  "Inferno Tower":"Tower","Mortar":"Tower","Goblin Hut":"Tower",
  "Barbarian Hut":"Tower","Goblin Drill":"Tower","Tombstone":"Tower","X-Bow":"Tower",
  "Elixir Golem":"Tanks","Golem":"Tanks","Rune Giant":"Tanks","Giant":"Tanks",
  "Rascals":"Tanks","Royal Giant":"Tanks","Goblin Giant":"Tanks","Lava Hound":"Tanks",
  "Mega Knight":"Tanks","P.E.K.K.A":"Tanks",
  "Princess":"Ranged","Ice Wizard":"Ranged","Dart Goblin":"Ranged","Musketeer":"Ranged",
  "Flying Machine":"Ranged","Baby Dragon":"Ranged","Zappies":"Ranged","Furnace":"Ranged",
  "Hunter":"Ranged","Electro Wizard":"Ranged","Goblin Demolisher":"Ranged",
  "Mother Witch":"Ranged","Executioner":"Ranged","Wizard":"Ranged","Witch":"Ranged",
  "Electro Spirit":"Melee","Ice Spirit":"Melee","Berserker":"Melee",
  "Fisherman":"Melee","Knight":"Melee","Night Witch":"Melee",
  "Ram Rider":"Charge","Suspicious Bush":"Charge","Goblin Barrel":"Charge",
  "The Log":"Spells","Giant Snowball":"Spells","Rage":"Spells","Vines":"Spells",
  "Fireball":"Spells","Poison":"Spells","Graveyard":"Spells","Rocket":"Spells",
  "Royal Delivery":"Spells"
};

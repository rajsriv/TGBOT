import random

def execute_ability_hook(hook_type, ability_name, **kwargs):
    if not ability_name: return None
    func = ABILITY_REGISTRY.get(ability_name, {}).get(hook_type)
    if func:
        return func(**kwargs)
    return None

# --- HOOK IMPLEMENTATIONS ---

def intimidate_on_switch_in(pkmn, opp_pkmn, **kwargs):
    if opp_pkmn["hp"] <= 0: return ""
    old_stage = opp_pkmn["stat_stages"].get("atk", 0)
    new_stage = max(-6, old_stage - 1)
    if new_stage < old_stage:
        opp_pkmn["stat_stages"]["atk"] = new_stage
        return f"📉 {pkmn['name']}'s Intimidate cut {opp_pkmn['name']}'s Attack!\n"
    return ""

def drizzle_on_switch_in(battle, **kwargs):
    if battle.get("weather") != "rain":
        battle["weather"] = "rain"
        battle["weather_turns"] = 5
        return "🌧️ It started to rain!\n"
    return ""

def drought_on_switch_in(battle, **kwargs):
    if battle.get("weather") != "sun":
        battle["weather"] = "sun"
        battle["weather_turns"] = 5
        return "☀️ The sunlight turned harsh!\n"
    return ""

def sand_stream_on_switch_in(battle, **kwargs):
    if battle.get("weather") != "sandstorm":
        battle["weather"] = "sandstorm"
        battle["weather_turns"] = 5
        return "🌪️ A sandstorm kicked up!\n"
    return ""

def snow_warning_on_switch_in(battle, **kwargs):
    if battle.get("weather") != "hail":
        battle["weather"] = "hail"
        battle["weather_turns"] = 5
        return "🌨️ It started to hail!\n"
    return ""

def levitate_on_defense(move, **kwargs):
    if move["type"] == "ground": return 0.0
    return 1.0

def overgrow_on_attack(atk_pkmn, move, stab, **kwargs):
    if atk_pkmn["hp"] <= atk_pkmn["max_hp"] / 3 and move["type"] == "grass": return stab * 1.5
    return stab

def blaze_on_attack(atk_pkmn, move, stab, **kwargs):
    if atk_pkmn["hp"] <= atk_pkmn["max_hp"] / 3 and move["type"] == "fire": return stab * 1.5
    return stab

def torrent_on_attack(atk_pkmn, move, stab, **kwargs):
    if atk_pkmn["hp"] <= atk_pkmn["max_hp"] / 3 and move["type"] == "water": return stab * 1.5
    return stab

def swarm_on_attack(atk_pkmn, move, stab, **kwargs):
    if atk_pkmn["hp"] <= atk_pkmn["max_hp"] / 3 and move["type"] == "bug": return stab * 1.5
    return stab

def sturdy_on_damage(dmg, def_pkmn, **kwargs):
    if dmg >= def_pkmn["hp"] and def_pkmn["hp"] == def_pkmn["max_hp"]:
        return def_pkmn["max_hp"] - 1
    return dmg

def thick_fat_on_defense(move, **kwargs):
    if move["type"] in ["fire", "ice"]: return 0.5
    return 1.0

def static_on_hit_receive(move, atk_pkmn, **kwargs):
    if move["class"] == "physical" and not atk_pkmn.get("status") and "electric" not in atk_pkmn["types"]:
        if random.randint(1, 100) <= 30:
            atk_pkmn["status"] = "paralyzed"
            return f"⚡ {atk_pkmn['name']} was paralyzed by Static!\n"
    return ""

def flame_body_on_hit_receive(move, atk_pkmn, **kwargs):
    if move["class"] == "physical" and not atk_pkmn.get("status") and "fire" not in atk_pkmn["types"]:
        if random.randint(1, 100) <= 30:
            atk_pkmn["status"] = "burned"
            return f"🔥 {atk_pkmn['name']} was burned by Flame Body!\n"
    return ""

def poison_point_on_hit_receive(move, atk_pkmn, **kwargs):
    if move["class"] == "physical" and not atk_pkmn.get("status") and "poison" not in atk_pkmn["types"] and "steel" not in atk_pkmn["types"]:
        if random.randint(1, 100) <= 30:
            atk_pkmn["status"] = "poisoned"
            return f"☠️ {atk_pkmn['name']} was poisoned by Poison Point!\n"
    return ""

def effect_spore_on_hit_receive(move, atk_pkmn, **kwargs):
    if move["class"] == "physical" and not atk_pkmn.get("status") and "grass" not in atk_pkmn["types"]:
        if random.randint(1, 100) <= 30:
            r = random.randint(1, 3)
            if r == 1:
                atk_pkmn["status"] = "poisoned"
                return f"☠️ {atk_pkmn['name']} was poisoned by Effect Spore!\n"
            elif r == 2:
                atk_pkmn["status"] = "paralyzed"
                return f"⚡ {atk_pkmn['name']} was paralyzed by Effect Spore!\n"
            else:
                atk_pkmn["status"] = "sleep"
                return f"💤 {atk_pkmn['name']} fell asleep due to Effect Spore!\n"
    return ""

ABILITY_REGISTRY = {
    "Intimidate": {"on_switch_in": intimidate_on_switch_in},
    "Drizzle": {"on_switch_in": drizzle_on_switch_in},
    "Drought": {"on_switch_in": drought_on_switch_in},
    "Sand Stream": {"on_switch_in": sand_stream_on_switch_in},
    "Snow Warning": {"on_switch_in": snow_warning_on_switch_in},
    
    "Levitate": {"on_defense": levitate_on_defense},
    "Thick Fat": {"on_defense": thick_fat_on_defense},
    
    "Overgrow": {"on_attack": overgrow_on_attack},
    "Blaze": {"on_attack": blaze_on_attack},
    "Torrent": {"on_attack": torrent_on_attack},
    "Swarm": {"on_attack": swarm_on_attack},
    
    "Sturdy": {"on_damage": sturdy_on_damage},
    
    "Static": {"on_hit_receive": static_on_hit_receive},
    "Flame Body": {"on_hit_receive": flame_body_on_hit_receive},
    "Poison Point": {"on_hit_receive": poison_point_on_hit_receive},
    "Effect Spore": {"on_hit_receive": effect_spore_on_hit_receive},
}

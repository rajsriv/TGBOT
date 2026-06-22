import httpx
import random
import asyncio
from utils.formulas import calc_stat, roll_ivs

import json
import os

with open("data/gen4randombattle.json", "r") as f:
    RANDBATS_DATA = json.load(f)

def get_random_battle_level(bst):
    if bst >= 680: return 72
    if bst >= 600: return 80
    if bst >= 500: return 84
    if bst >= 400: return 88
    if bst >= 300: return 94
    return 100

async def fetch_random_team(size=6, level=None):
    tasks = [fetch_random_pokemon(level) for _ in range(size)]
    return await asyncio.gather(*tasks)

async def fetch_random_pokemon(level: int = None):
    async with httpx.AsyncClient() as client:
        while True:
            pkmn_name = random.choice(list(RANDBATS_DATA.keys()))
            randbats_pkmn = RANDBATS_DATA[pkmn_name]
            
            # Format name for PokeAPI
            api_name = pkmn_name.lower().replace(" ", "-").replace(".", "").replace("'", "")
            
            resp = await client.get(f"https://pokeapi.co/api/v2/pokemon/{api_name}")
            if resp.status_code == 200:
                data = resp.json()
                break
                
        base_stats = {stat["stat"]["name"]: stat["base_stat"] for stat in data["stats"]}
        types = [t["type"]["name"] for t in data["types"]]
        
        # Pick a random competitive role
        roles = list(randbats_pkmn["roles"].values())
        role = random.choice(roles)
        
        ability = random.choice(role["abilities"]) if role.get("abilities") else "None"
        item = random.choice(role["items"]) if role.get("items") else "None"
        
        moves_to_pick = role.get("moves", [])
        if len(moves_to_pick) > 4:
            moves_to_pick = random.sample(moves_to_pick, 4)
            
        # Fetch move info from PokeAPI
        move_data = []
        for m_name in moves_to_pick:
            m_api_name = m_name.lower().replace(" ", "-")
            m_resp = await client.get(f"https://pokeapi.co/api/v2/move/{m_api_name}")
            if m_resp.status_code != 200:
                continue
            m_data = m_resp.json()
            
            stat_map = {
                "attack": "atk", "defense": "def", "special-attack": "sp_atk", 
                "special-defense": "sp_def", "speed": "spd", "accuracy": "accuracy", "evasion": "evasion"
            }
            stat_changes = []
            
            meta = m_data.get("meta") or {}
            stat_chance = meta.get("stat_chance", 0) or 100
            category = meta.get("category", {}).get("name", "")
            
            sc_list = m_data.get("stat_changes", [])
            for sc in sc_list:
                mapped_stat = stat_map.get(sc["stat"]["name"])
                if mapped_stat:
                    stat_changes.append({"stat": mapped_stat, "change": sc["change"]})
                    
            stat_target = m_data["target"]["name"]
            if category == "damage+raise" or category == "damage-raise":
                stat_target = "user"
                
            move_data.append({
                "name": m_data["name"].replace("-", " ").title(),
                "power": m_data.get("power", 0) or 0,
                "accuracy": m_data.get("accuracy", "-") or "-",
                "type": m_data["type"]["name"],
                "class": m_data["damage_class"]["name"],
                "pp": m_data.get("pp", 10),
                "max_pp": m_data.get("pp", 10),
                "stat_changes": stat_changes,
                "stat_chance": stat_chance,
                "stat_target": stat_target,
                "target": m_data["target"]["name"]
            })
            
        if not move_data:
            move_data.append({"name": "Struggle", "power": 50, "accuracy": 100, "type": "normal", "class": "physical", "pp": 10, "max_pp": 10, "stat_changes": [], "stat_chance": 100, "stat_target": "selected-pokemon", "target": "selected-pokemon"})
            
        ivs = roll_ivs()
        
        # Override IVs if specified in role (e.g. 0 Atk for Foul Play or 0 Spd for Trick Room)
        if "ivs" in role:
            for k, v in role["ivs"].items():
                if k in ivs: ivs[k] = v
                
        final_level = level if level is not None else randbats_pkmn.get("level", 85)
        
        hp = calc_stat(base_stats.get("hp", 50), ivs["hp"], 85, final_level, is_hp=True)
        atk = calc_stat(base_stats.get("attack", 50), ivs["atk"], 85, final_level)
        def_ = calc_stat(base_stats.get("defense", 50), ivs["def"], 85, final_level)
        sp_atk = calc_stat(base_stats.get("special-attack", 50), ivs["sp_atk"], 85, final_level)
        sp_def = calc_stat(base_stats.get("special-defense", 50), ivs["sp_def"], 85, final_level)
        spd = calc_stat(base_stats.get("speed", 50), ivs["spd"], 85, final_level)
        
        # Download sprite
        sprite_url = data["sprites"]["front_default"]
        sprite_resp = await client.get(sprite_url)
        sprite_bytes = sprite_resp.content
        
        return {
            "name": pkmn_name,
            "level": final_level,
            "hp": hp,
            "max_hp": hp,
            "stats": {"atk": atk, "def": def_, "sp_atk": sp_atk, "sp_def": sp_def, "spd": spd},
            "stat_stages": {"atk": 0, "def": 0, "sp_atk": 0, "sp_def": 0, "spd": 0},
            "types": types,
            "moves": move_data,
            "ability": ability,
            "item": item,
            "sprite": sprite_bytes,
            "status": None,
            "volatile_status": []
        }

def calculate_damage(level, power, attacker_stats, defender_stats, move_class, stab=1.0, type_mod=1.0, crit=1.0, weather_mod=1.0):
    if power <= 0:
        return 0
    a = attacker_stats["atk"] if move_class == "physical" else attacker_stats["sp_atk"]
    d = defender_stats["def"] if move_class == "physical" else defender_stats["sp_def"]
    
    damage = (((2 * level / 5 + 2) * power * (a / d)) / 50 + 2)
    modifier = stab * type_mod * crit * weather_mod * random.uniform(0.85, 1.0)
    return int(damage * modifier)

import httpx
import random
import asyncio
from utils.formulas import calc_stat, roll_ivs

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
    pokemon_id = random.randint(1, 493) # Gen 1 to Gen 4 (Sinnoh)
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}")
        data = resp.json()
        
        base_stats = {stat["stat"]["name"]: stat["base_stat"] for stat in data["stats"]}
        types = [t["type"]["name"] for t in data["types"]]
        
        # Pick random moves. Try to find damaging moves!
        all_moves = data["moves"]
        random.shuffle(all_moves)
        
        move_data = []
        for m in all_moves:
            if len(move_data) >= 4:
                break
            # Fetch move info
            m_resp = await client.get(m["move"]["url"])
            m_data = m_resp.json()
            if m_data.get("power") or m_data.get("stat_changes") or m_data["name"] in ["protect", "detect"]:
                stat_map = {
                    "attack": "atk", "defense": "def", "special-attack": "sp_atk", 
                    "special-defense": "sp_def", "speed": "spd", "accuracy": "accuracy", "evasion": "evasion"
                }
                stat_changes = []
                
                meta = m_data.get("meta") or {}
                stat_chance = meta.get("stat_chance", 0) or 100
                category = meta.get("category", {}).get("name", "")
                
                # Ignore tera blast stat drops since we don't support terastallization
                if m_data["name"] == "tera-blast":
                    sc_list = []
                else:
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
                    "class": m_data["damage_class"]["name"], # 'physical', 'special', 'status'
                    "pp": m_data.get("pp", 10),
                    "max_pp": m_data.get("pp", 10),
                    "stat_changes": stat_changes,
                    "stat_chance": stat_chance,
                    "stat_target": stat_target,
                    "target": m_data["target"]["name"]
                })
        
        # Fallback if somehow no damaging moves
        if not any(m["power"] > 0 for m in move_data):
            move_data.append({"name": "Tackle", "power": 40, "accuracy": 100, "type": "normal", "class": "physical", "pp": 35, "max_pp": 35, "stat_changes": [], "stat_chance": 100, "stat_target": "selected-pokemon", "target": "selected-pokemon"})
            
        if len(move_data) > 4:
            move_data = move_data[:4]
            
        ivs = roll_ivs()
        bst = sum(base_stats.values())
        final_level = level if level is not None else get_random_battle_level(bst)
        
        # Random EVs per stat (simplified)
        hp = calc_stat(base_stats.get("hp", 50), ivs["hp"], 85, final_level, is_hp=True)
        atk = calc_stat(base_stats.get("attack", 50), ivs["atk"], 85, final_level)
        def_ = calc_stat(base_stats.get("defense", 50), ivs["def"], 85, final_level)
        sp_atk = calc_stat(base_stats.get("special-attack", 50), ivs["sp_atk"], 85, final_level)
        sp_def = calc_stat(base_stats.get("special-defense", 50), ivs["sp_def"], 85, final_level)
        spd = calc_stat(base_stats.get("speed", 50), ivs["spd"], 85, final_level)
        
        abilities = [a["ability"]["name"] for a in data["abilities"]]
        ability = random.choice(abilities).replace("-", " ").title() if abilities else "None"
        items = ["Leftovers", "Life Orb", "Sitrus Berry", "Expert Belt", "Focus Sash", "None"]
        item = random.choice(items)
        
        # Download sprite
        sprite_url = data["sprites"]["front_default"]
        sprite_resp = await client.get(sprite_url)
        sprite_bytes = sprite_resp.content
        
        return {
            "name": data["name"].capitalize(),
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

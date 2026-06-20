import httpx
import random
import asyncio
from utils.formulas import calc_stat, roll_ivs

async def fetch_random_team(size=6, level=50):
    tasks = [fetch_random_pokemon(level) for _ in range(size)]
    return await asyncio.gather(*tasks)

async def fetch_random_pokemon(level: int = 50):
    pokemon_id = random.randint(1, 151) # Gen 1 to keep it fast and classic
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
            if m_data.get("power"): # Only take moves that do damage
                move_data.append({
                    "name": m_data["name"].replace("-", " ").title(),
                    "power": m_data["power"],
                    "type": m_data["type"]["name"],
                    "class": m_data["damage_class"]["name"], # 'physical' or 'special'
                    "pp": m_data.get("pp", 10),
                    "max_pp": m_data.get("pp", 10)
                })
        
        # Fallback if somehow no damaging moves
        if not move_data:
            move_data.append({"name": "Tackle", "power": 40, "type": "normal", "class": "physical", "pp": 35, "max_pp": 35})
            
        ivs = roll_ivs()
        # Random EVs per stat (simplified)
        hp = calc_stat(base_stats.get("hp", 50), ivs["hp"], 85, level, is_hp=True)
        atk = calc_stat(base_stats.get("attack", 50), ivs["atk"], 85, level)
        defense = calc_stat(base_stats.get("defense", 50), ivs["def"], 85, level)
        sp_atk = calc_stat(base_stats.get("special-attack", 50), ivs["sp_atk"], 85, level)
        sp_def = calc_stat(base_stats.get("special-defense", 50), ivs["sp_def"], 85, level)
        spd = calc_stat(base_stats.get("speed", 50), ivs["spd"], 85, level)
        
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
            "level": level,
            "hp": hp,
            "max_hp": hp,
            "stats": {"atk": atk, "def": defense, "sp_atk": sp_atk, "sp_def": sp_def, "spd": spd},
            "types": types,
            "moves": move_data,
            "ability": ability,
            "item": item,
            "sprite": sprite_bytes
        }

def calculate_damage(level, power, attacker_stats, defender_stats, move_class, stab=1.0, type_mod=1.0):
    a = attacker_stats["atk"] if move_class == "physical" else attacker_stats["sp_atk"]
    d = defender_stats["def"] if move_class == "physical" else defender_stats["sp_def"]
    
    damage = (((2 * level / 5 + 2) * power * (a / d)) / 50 + 2)
    modifier = stab * type_mod * random.uniform(0.85, 1.0)
    return int(damage * modifier)

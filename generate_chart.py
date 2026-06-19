import httpx
import json

types_list = ["normal", "fighting", "flying", "poison", "ground", "rock", "bug", "ghost", "steel", "fire", "water", "grass", "electric", "psychic", "ice", "dragon", "dark", "fairy"]
chart = {}

with httpx.Client() as client:
    for t in types_list:
        try:
            r = client.get(f"https://pokeapi.co/api/v2/type/{t}")
            dmg = r.json()["damage_relations"]
            chart[t] = {
                "2": [x["name"] for x in dmg["double_damage_to"]],
                "0.5": [x["name"] for x in dmg["half_damage_to"]],
                "0": [x["name"] for x in dmg["no_damage_to"]]
            }
        except: pass

with open("utils/type_chart.py", "w") as f:
    f.write(f"TYPE_CHART = {json.dumps(chart, indent=4)}\n")
    f.write("""
def get_type_multiplier(move_type, defender_types):
    if move_type not in TYPE_CHART:
        return 1.0
    mod = 1.0
    for dt in defender_types:
        if dt in TYPE_CHART[move_type]["2"]:
            mod *= 2.0
        elif dt in TYPE_CHART[move_type]["0.5"]:
            mod *= 0.5
        elif dt in TYPE_CHART[move_type]["0"]:
            mod *= 0.0
    return mod
""")

print("Generated type_chart.py")

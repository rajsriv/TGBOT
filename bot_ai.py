import random
from utils.type_chart import get_type_multiplier

def get_bot_action(battle, bot_key, personality="Balanced"):
    """
    Determines the bot's next action based on the current battle state and its personality.
    Returns a choice dictionary: {"type": "move", "index": 0} or {"type": "switch", "index": 1}
    """
    bot_player = battle[bot_key]
    opponent_key = "p1" if bot_key == "p2" else "p2"
    opponent_player = battle[opponent_key]
    
    bot_active = bot_player["team"][bot_player["active"]]
    opp_active = opponent_player["team"][opponent_player["active"]]
    
    # 1. Handle forced locked states (recharge / charging)
    if "recharging" in bot_active.get("volatile_status", []):
        return {"type": "recharge", "index": 0}
        
    menu_state = battle["menus"][bot_key]
    
    # 2. If forced to switch (e.g. active Pokemon fainted)
    if menu_state in ["switch", "force_switch"]:
        available_switches = [i for i, pkmn in enumerate(bot_player["team"]) if pkmn["hp"] > 0 and i != bot_player["active"]]
        if not available_switches:
            return None # Should not happen if game hasn't ended
            
        # Basic heuristic: pick a random switch, or prioritize based on type advantage later.
        if personality == "Defensive":
            # Pick pokemon with most HP percentage
            best_switch = max(available_switches, key=lambda i: bot_player["team"][i]["hp"] / bot_player["team"][i]["max_hp"])
            return {"type": "switch", "index": best_switch}
        else:
            return {"type": "switch", "index": random.choice(available_switches)}
            
    # 3. Main menu state (choose move or switch)
    if menu_state == "main":
        locked_move = bot_active.get("choice_locked")
        
        hp_pct = bot_active["hp"] / bot_active["max_hp"]
        available_switches = [i for i, pkmn in enumerate(bot_player["team"]) if pkmn["hp"] > 0 and i != bot_player["active"]]
        
        if available_switches and locked_move is None:
            if personality == "Defensive" and hp_pct < 0.3 and random.random() < 0.6:
                return {"type": "switch", "index": random.choice(available_switches)}

        available_moves = [i for i in range(len(bot_active["moves"])) if bot_active["moves"][i].get("pp", 1) > 0]
        if locked_move is not None and locked_move < len(bot_active["moves"]):
            if bot_active["moves"][locked_move].get("pp", 1) > 0:
                available_moves = [locked_move]
            else:
                available_moves = [] # Forces Struggle if locked into 0 PP move
            
        if not available_moves:
            return {"type": "move", "index": 0} # Struggle fallback
            
        if personality == "Aggressive":
            def move_score(idx):
                m = bot_active["moves"][idx]
                score = m.get("power", 0)
                if m["type"] in bot_active["types"]: score *= 1.5
                score *= get_type_multiplier(m["type"], opp_active["types"])
                return score
            best_move = max(available_moves, key=move_score)
            return {"type": "move", "index": best_move}
            
        elif personality == "Defensive":
            def move_score(idx):
                m = bot_active["moves"][idx]
                if m.get("power", 0) == 0: return 100
                score = m.get("power", 0)
                score *= get_type_multiplier(m["type"], opp_active["types"])
                return score
            best_move = max(available_moves, key=move_score)
            if random.random() < 0.3:
                return {"type": "move", "index": random.choice(available_moves)}
            return {"type": "move", "index": best_move}
            
        else:
            def move_score(idx):
                m = bot_active["moves"][idx]
                score = m.get("power", 0)
                if m["type"] in bot_active["types"]: score *= 1.5
                score *= get_type_multiplier(m["type"], opp_active["types"])
                return score + random.uniform(0, 50)
            best_move = max(available_moves, key=move_score)
            return {"type": "move", "index": best_move}
            
    return None

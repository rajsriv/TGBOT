from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from engine import fetch_random_team, calculate_damage
import random

# Extremely simplified in-memory state. In production, use Redis or MongoDB.
active_battles = {}

async def battle_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    battle_id = context.job.data
    if battle_id not in active_battles:
        return

    battle = active_battles[battle_id]
    
    p1_picked = battle["choices"]["p1"] is not None
    p2_picked = battle["choices"]["p2"] is not None
    
    if not p1_picked and not p2_picked:
        text = "⌛ Battle timed out! Both players fled."
    elif p1_picked and not p2_picked:
        text = f"🏆 {battle['p1']['name']} wins by forfeit! ({battle['p2']['name']} ran away)"
    elif p2_picked and not p1_picked:
        text = f"🏆 {battle['p2']['name']} wins by forfeit! ({battle['p1']['name']} ran away)"
        
    chat_id = battle["chat_id"]
    message_id = battle["message_id"]
    
    del active_battles[battle_id]
    try:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    except Exception:
        pass

def reset_timeout(context, battle_id):
    current_jobs = context.job_queue.get_jobs_by_name(f"timeout_{battle_id}")
    for job in current_jobs:
        job.schedule_removal()
    context.job_queue.run_once(battle_timeout_job, 120, data=battle_id, name=f"timeout_{battle_id}")

async def showdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message and len(context.args) == 0:
        await msg.reply_text("Please reply to a user or tag them with /showdown @username!")
        return

    challenger = msg.from_user
    target_username = context.args[0] if context.args else msg.reply_to_message.from_user.username

    sent_msg = await msg.reply_text(f"⚔️ {challenger.first_name} challenged {target_username} to a 6v6 Random Battle!\n\nGenerating teams... (this may take a few seconds)")

    # Generate 6v6 Teams
    p1_team = await fetch_random_team()
    p2_team = await fetch_random_team()

    battle_id = f"b_{msg.message_id}"
    active_battles[battle_id] = {
        "chat_id": msg.chat_id,
        "message_id": sent_msg.message_id,
        "p1": {"id": challenger.id, "name": challenger.first_name, "team": p1_team, "active": 0},
        "p2_tag": target_username.replace("@", ""),
        "p2": {"id": None, "name": target_username, "team": p2_team, "active": 0},
        "choices": {"p1": None, "p2": None}, # {"type": "move", "index": 0}
        "menus": {"p1": "main", "p2": "main"}, # "main", "switch", "force_switch"
        "status": "active"
    }

    reset_timeout(context, battle_id)
    await send_battle_state(msg.chat_id, battle_id, context, message_to_edit=sent_msg)

def get_player_buttons(battle, player_key, battle_id):
    opponent_key = "p2" if player_key == "p1" else "p1"
    
    # If the opponent is forced to switch and we are not, we wait for them!
    if battle["menus"][opponent_key] == "force_switch" and battle["menus"][player_key] != "force_switch":
        return []
        
    p_data = battle[player_key]
    menu = battle["menus"][player_key]
    color = "🔴" if player_key == "p1" else "🔵"
    buttons = []
    
    # If we already locked in a choice, hide our buttons to prevent clutter
    if battle["choices"][player_key] is not None:
        return []
    
    if menu == "main":
        active_pkmn = p_data["team"][p_data["active"]]
        row1 = [InlineKeyboardButton(f"{color} {m['name']}", callback_data=f"btn_{battle_id}_{player_key}_move_{i}") for i, m in enumerate(active_pkmn['moves'][:2])]
        row2 = [InlineKeyboardButton(f"{color} {m['name']}", callback_data=f"btn_{battle_id}_{player_key}_move_{i}") for i, m in enumerate(active_pkmn['moves'][2:])]
        switch_btn = [InlineKeyboardButton(f"🔄 Switch Pokémon", callback_data=f"btn_{battle_id}_{player_key}_menu_switch")]
        buttons.extend([row1, row2, switch_btn])
        
    elif menu in ["switch", "force_switch"]:
        for i, pkmn in enumerate(p_data["team"]):
            if i != p_data["active"] and pkmn["hp"] > 0:
                buttons.append([InlineKeyboardButton(f"{color} {pkmn['name']} ({pkmn['hp']}/{pkmn['max_hp']})", callback_data=f"btn_{battle_id}_{player_key}_switch_{i}")])
        if menu == "switch":
            buttons.append([InlineKeyboardButton(f"⬅️ Back", callback_data=f"btn_{battle_id}_{player_key}_menu_main")])
            
    return buttons

async def send_battle_state(chat_id, battle_id, context, action_text="", message_to_edit=None):
    if battle_id not in active_battles: return
    battle = active_battles[battle_id]
    p1 = battle["p1"]
    p2 = battle["p2"]
    
    text = ""
    if action_text:
        text += f"{action_text}\n\n"

    p1_active = p1["team"][p1["active"]]
    p2_active = p2["team"][p2["active"]]
    p1_alive = sum(1 for p in p1["team"] if p["hp"] > 0)
    p2_alive = sum(1 for p in p2["team"] if p["hp"] > 0)

    text += (
        f"🔴 {p1['name']}'s {p1_active['name']}: {p1_active['hp']}/{p1_active['max_hp']} HP (Poké: {p1_alive}/6)\n"
        f"🔵 {p2['name']}'s {p2_active['name']}: {p2_active['hp']}/{p2_active['max_hp']} HP (Poké: {p2_alive}/6)\n\n"
    )
    
    if p1_alive == 0 or p2_alive == 0:
        if p1_alive == 0: text += f"🏆 {p2['name']} wins!"
        else: text += f"🏆 {p1['name']} wins!"
        del active_battles[battle_id]
        current_jobs = context.job_queue.get_jobs_by_name(f"timeout_{battle_id}")
        for job in current_jobs: job.schedule_removal()
        if message_to_edit: await message_to_edit.edit_text(text)
        else: await context.bot.send_message(chat_id=chat_id, text=text)
        return

    # Info Text
    thinking = []
    if battle["choices"]["p1"] is None and battle["menus"]["p1"] != "main" and battle["menus"]["p2"] == "force_switch" and battle["menus"]["p1"] != "force_switch":
        pass # P1 is waiting for P2 force switch, not thinking
    else:
        if battle["choices"]["p1"] is None and len(get_player_buttons(battle, "p1", battle_id)) > 0: thinking.append(p1["name"])
        if battle["choices"]["p2"] is None and len(get_player_buttons(battle, "p2", battle_id)) > 0: thinking.append(p2["name"])
        
    if len(thinking) == 2: text += f"👉 Both players making choices..."
    elif len(thinking) == 1: text += f"⌛ Waiting for {thinking[0]}..."

    keyboard = []
    keyboard.extend(get_player_buttons(battle, "p1", battle_id))
    keyboard.extend(get_player_buttons(battle, "p2", battle_id))

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    if message_to_edit:
        await message_to_edit.edit_text(text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def handle_move_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_") # btn_b_1234_p1_move_0
    
    if data[0] != "btn" or len(data) < 6:
        await query.answer("This battle is from an older version! Please start a new /showdown.", show_alert=True)
        return
        
    battle_id = f"{data[1]}_{data[2]}"
    player_key = data[3]
    action_type = data[4]
    action_val = data[5]

    if battle_id not in active_battles:
        await query.answer("This battle is no longer active.", show_alert=True)
        return

    battle = active_battles[battle_id]
    user_id = query.from_user.id

    if battle["p2"]["id"] is None and player_key == "p2" and query.from_user.username == battle["p2_tag"]:
        battle["p2"]["id"] = user_id
        battle["p2"]["name"] = query.from_user.first_name

    if user_id != battle[player_key]["id"]:
        await query.answer("These are not your buttons!", show_alert=True)
        return

    # Handle UI Menus
    if action_type == "menu":
        battle["menus"][player_key] = action_val
        await send_battle_state(query.message.chat_id, battle_id, context, action_text="", message_to_edit=query.message)
        await query.answer()
        return

    if battle["choices"][player_key] is not None:
        await query.answer("You already locked in!", show_alert=True)
        return

    battle["choices"][player_key] = {"type": action_type, "index": int(action_val)}
    await query.answer("Locked in!")

    # Check if ready to resolve
    ready = True
    for p_key in ["p1", "p2"]:
        opponent_key = "p2" if p_key == "p1" else "p1"
        if battle["menus"][opponent_key] == "force_switch" and battle["menus"][p_key] != "force_switch":
            continue # This player doesn't need to choose right now
        if battle["choices"][p_key] is None:
            ready = False
            break

    if ready:
        await resolve_turn(battle_id, context, query)
    else:
        await send_battle_state(query.message.chat_id, battle_id, context, action_text="", message_to_edit=query.message)

async def resolve_turn(battle_id, context, query):
    battle = active_battles[battle_id]
    is_force_switch = battle["menus"]["p1"] == "force_switch" or battle["menus"]["p2"] == "force_switch"
    action_text = ""
    
    if is_force_switch:
        for p_key in ["p1", "p2"]:
            if battle["menus"][p_key] == "force_switch" and battle["choices"][p_key]:
                choice = battle["choices"][p_key]
                battle[p_key]["active"] = choice["index"]
                pkmn_name = battle[p_key]["team"][choice["index"]]["name"]
                action_text += f"🔄 {battle[p_key]['name']} sent out {pkmn_name}!\n"
                battle["menus"][p_key] = "main"
        battle["choices"] = {"p1": None, "p2": None}
    else:
        # Normal Turn
        actions = []
        for p_key in ["p1", "p2"]:
            actions.append((p_key, battle["choices"][p_key]))
            
        def priority(action):
            p, c = action
            if c["type"] == "switch": return 1000000
            spd = battle[p]["team"][battle[p]["active"]]["stats"]["spd"]
            return spd + random.uniform(0, 0.99)
            
        actions.sort(key=priority, reverse=True)
        
        for p_key, choice in actions:
            player = battle[p_key]
            opponent_key = "p2" if p_key == "p1" else "p1"
            opponent = battle[opponent_key]
            
            # If our pokemon died this turn, we can't attack
            if player["team"][player["active"]]["hp"] <= 0:
                continue
                
            if choice["type"] == "switch":
                old_name = player["team"][player["active"]]["name"]
                player["active"] = choice["index"]
                new_name = player["team"][choice["index"]]["name"]
                action_text += f"🔄 {player['name']} withdrew {old_name} and sent out {new_name}!\n"
            elif choice["type"] == "move":
                atk_pkmn = player["team"][player["active"]]
                def_pkmn = opponent["team"][opponent["active"]]
                move = atk_pkmn["moves"][choice["index"]]
                
                dmg = calculate_damage(atk_pkmn["level"], move["power"], atk_pkmn["stats"], def_pkmn["stats"], move["class"], stab=1.5 if move["type"] in atk_pkmn["types"] else 1.0)
                def_pkmn["hp"] = max(0, def_pkmn["hp"] - dmg)
                action_text += f"💥 {atk_pkmn['name']} used {move['name']}! ({dmg} dmg)\n"
                
                if def_pkmn["hp"] == 0:
                    action_text += f"💀 {def_pkmn['name']} fainted!\n"
                    battle["menus"][opponent_key] = "force_switch"
                    
        battle["choices"] = {"p1": None, "p2": None}
        
    reset_timeout(context, battle_id)
    await send_battle_state(query.message.chat_id, battle_id, context, action_text=action_text, message_to_edit=query.message)

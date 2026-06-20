from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from engine import fetch_random_team, calculate_damage
from utils.type_chart import get_type_multiplier
import random

active_battles = {}

async def battle_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    battle_id = context.job.data
    if battle_id not in active_battles: return
    battle = active_battles[battle_id]
    
    p1_picked = battle["choices"]["p1"] is not None
    p2_picked = battle["choices"]["p2"] is not None
    
    if not p1_picked and not p2_picked: text = "⌛ Battle timed out! Both players fled."
    elif p1_picked and not p2_picked: text = f"🏆 {battle['p1']['name']} wins by forfeit! ({battle['p2']['name']} ran away)"
    elif p2_picked and not p1_picked: text = f"🏆 {battle['p2']['name']} wins by forfeit! ({battle['p1']['name']} ran away)"
        
    for p_key in ["p1", "p2"]:
        if battle[p_key]["dm_chat_id"]:
            try: await context.bot.edit_message_text(chat_id=battle[p_key]["dm_chat_id"], message_id=battle[p_key]["dm_msg_id"], text=text)
            except Exception: pass
            
    try:
        await context.bot.send_message(chat_id=battle["group_chat_id"], reply_to_message_id=battle["group_msg_id"], text=f"The battle ended due to inactivity! {text}")
    except Exception: pass

    del active_battles[battle_id]

def reset_timeout(context, battle_id):
    current_jobs = context.job_queue.get_jobs_by_name(f"timeout_{battle_id}")
    for job in current_jobs: job.schedule_removal()
    context.job_queue.run_once(battle_timeout_job, 120, data=battle_id, name=f"timeout_{battle_id}")

async def showdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message and len(context.args) == 0:
        await msg.reply_text("Please reply to a user or tag them with /showdown @username!")
        return

    challenger = msg.from_user
    target_username = context.args[0] if context.args else msg.reply_to_message.from_user.username

    loading_msg = await msg.reply_text(f"⚔️ {challenger.first_name} challenged {target_username} to a 6v6 Random Battle!\n\nGenerating teams... (this may take a few seconds)")

    p1_team = await fetch_random_team()
    p2_team = await fetch_random_team()

    battle_id = f"b_{msg.message_id}"
    active_battles[battle_id] = {
        "group_chat_id": msg.chat_id,
        "group_msg_id": msg.message_id,
        "action_text": "",
        "p1": {"id": challenger.id, "name": challenger.first_name, "tag": challenger.username, "team": p1_team, "active": 0, "dm_chat_id": None, "dm_msg_id": None},
        "p2": {"id": None, "name": target_username, "tag": target_username.replace("@", ""), "team": p2_team, "active": 0, "dm_chat_id": None, "dm_msg_id": None},
        "choices": {"p1": None, "p2": None},
        "menus": {"p1": "main", "p2": "main"}
    }

    bot_username = context.bot.username
    url = f"https://t.me/{bot_username}?start={battle_id}"
    keyboard = [[InlineKeyboardButton("⚔️ Join Battle", url=url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await loading_msg.edit_text(f"⚔️ {challenger.first_name} challenged {target_username} to a 6v6 Random Battle!\n\nBoth players must click the button below to join the arena in my DMs!", reply_markup=reply_markup)

async def join_battle(update: Update, context: ContextTypes.DEFAULT_TYPE, battle_id: str):
    user = update.effective_user
    if battle_id not in active_battles:
        await update.message.reply_text("This battle no longer exists or has expired.")
        return
        
    battle = active_battles[battle_id]
    player_key = None
    
    if user.id == battle["p1"]["id"]: player_key = "p1"
    elif battle["p2"]["id"] is None and (user.username == battle["p2"]["tag"] or user.first_name == battle["p2"]["tag"]):
        battle["p2"]["id"] = user.id
        battle["p2"]["name"] = user.first_name
        player_key = "p2"
    elif user.id == battle["p2"]["id"]: player_key = "p2"
        
    if not player_key:
        await update.message.reply_text("You are not a participant in this battle!")
        return
        
    battle[player_key]["dm_chat_id"] = update.message.chat_id
    dm_msg = await update.message.reply_text("Loading arena...")
    battle[player_key]["dm_msg_id"] = dm_msg.message_id
    
    if battle["p1"]["dm_chat_id"] and battle["p2"]["dm_chat_id"]:
        reset_timeout(context, battle_id)
        await sync_battle_state(battle_id, context)
    else:
        await dm_msg.edit_text("⌛ Waiting for your opponent to join...")

def get_player_buttons(battle, player_key, battle_id):
    opponent_key = "p2" if player_key == "p1" else "p1"
    if battle["menus"][opponent_key] == "force_switch" and battle["menus"][player_key] != "force_switch": return []
        
    p_data = battle[player_key]
    menu = battle["menus"][player_key]
    buttons = []
    if battle["choices"][player_key] is not None: return []
    
    if menu == "main":
        active_pkmn = p_data["team"][p_data["active"]]
        row1 = [InlineKeyboardButton(f"{m['name']} (Pow: {m['power']} | PP: {m['pp']}/{m['max_pp']})", callback_data=f"btn_{battle_id}_{player_key}_move_{i}") for i, m in enumerate(active_pkmn['moves'][:2])]
        row2 = [InlineKeyboardButton(f"{m['name']} (Pow: {m['power']} | PP: {m['pp']}/{m['max_pp']})", callback_data=f"btn_{battle_id}_{player_key}_move_{i}") for i, m in enumerate(active_pkmn['moves'][2:], start=2)]
        switch_btn = [InlineKeyboardButton(f"Switch Pokémon", callback_data=f"btn_{battle_id}_{player_key}_menu_switch")]
        buttons.extend([row1, row2, switch_btn])
    elif menu in ["switch", "force_switch"]:
        for i, pkmn in enumerate(p_data["team"]):
            if i != p_data["active"] and pkmn["hp"] > 0:
                buttons.append([InlineKeyboardButton(f"🐾 {pkmn['name']} ({pkmn['hp']}/{pkmn['max_hp']})", callback_data=f"btn_{battle_id}_{player_key}_switch_{i}")])
        if menu == "switch":
            buttons.append([InlineKeyboardButton(f"⬅◁ Back", callback_data=f"btn_{battle_id}_{player_key}_menu_main")])
    return buttons

async def sync_battle_state(battle_id, context):
    if battle_id not in active_battles: return
    battle = active_battles[battle_id]
    
    p1_alive = sum(1 for p in battle["p1"]["team"] if p["hp"] > 0)
    p2_alive = sum(1 for p in battle["p2"]["team"] if p["hp"] > 0)
    
    if p1_alive == 0 or p2_alive == 0:
        winner = battle["p2"]["name"] if p1_alive == 0 else battle["p1"]["name"]
        loser = battle["p1"]["name"] if p1_alive == 0 else battle["p2"]["name"]
        win_text = f"{battle['action_text']}\n\n🏆 **{winner}** wins the battle!"
        
        for p_key in ["p1", "p2"]:
            if battle[p_key]["dm_chat_id"]:
                try: await context.bot.edit_message_text(chat_id=battle[p_key]["dm_chat_id"], message_id=battle[p_key]["dm_msg_id"], text=win_text)
                except Exception: pass
                
        try:
            await context.bot.send_message(chat_id=battle["group_chat_id"], reply_to_message_id=battle["group_msg_id"], text=f"🏆 The battle has concluded!\n{winner} defeated {loser} in a 6v6 Showdown!")
        except Exception: pass
        
        del active_battles[battle_id]
        current_jobs = context.job_queue.get_jobs_by_name(f"timeout_{battle_id}")
        for job in current_jobs: job.schedule_removal()
        return

    await update_player_dm(battle_id, context, "p1")
    await update_player_dm(battle_id, context, "p2")

async def update_player_dm(battle_id, context, player_key):
    battle = active_battles[battle_id]
    me = battle[player_key]
    opponent_key = "p2" if player_key == "p1" else "p1"
    opp = battle[opponent_key]
    if not me["dm_chat_id"]: return
        
    text = ""
    if battle["action_text"]: text += f"{battle['action_text']}\n\n"
        
    my_active = me["team"][me["active"]]
    opp_active = opp["team"][opp["active"]]
    me_alive = sum(1 for p in me["team"] if p["hp"] > 0)
    opp_alive = sum(1 for p in opp["team"] if p["hp"] > 0)
    
    text += (
        f"▛ Your {my_active['name']}: {my_active['hp']}/{my_active['max_hp']} HP (Poké: {me_alive}/6)\n"
        f"╰ Item: {my_active['item']} | Ability: {my_active['ability']}\n"
        f"▙ Enemy {opp_active['name']}: {int(opp_active['hp']/opp_active['max_hp']*100)}% HP (Poké: {opp_alive}/6)\n\n"
    )
    
    thinking = []
    if battle["choices"][player_key] is None and battle["menus"][player_key] != "main" and battle["menus"][opponent_key] == "force_switch" and battle["menus"][player_key] != "force_switch":
        pass 
    else:
        if battle["choices"][player_key] is None and len(get_player_buttons(battle, player_key, battle_id)) > 0: thinking.append(me["name"])
        if battle["choices"][opponent_key] is None and len(get_player_buttons(battle, opponent_key, battle_id)) > 0: thinking.append(opp["name"])
        
    if len(thinking) == 2: text += f"■ Both players making choices..."
    elif len(thinking) == 1: text += f"Waiting for {thinking[0]}..."
    
    keyboard = get_player_buttons(battle, player_key, battle_id)
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    try: await context.bot.edit_message_text(chat_id=me["dm_chat_id"], message_id=me["dm_msg_id"], text=text, reply_markup=reply_markup)
    except Exception: pass

async def handle_move_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    
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
    if query.from_user.id != battle[player_key]["id"]: return

    if action_type == "menu":
        battle["menus"][player_key] = action_val
        await sync_battle_state(battle_id, context)
        await query.answer()
        return

    if battle["choices"][player_key] is not None:
        await query.answer("You already locked in!", show_alert=True)
        return

    if action_type == "move":
        move = battle[player_key]["team"][battle[player_key]["active"]]["moves"][int(action_val)]
        if move["pp"] <= 0:
            await query.answer("You don't have any PP left for this move!", show_alert=True)
            return
            
    battle["choices"][player_key] = {"type": action_type, "index": int(action_val)}
    await query.answer("Locked in!")

    ready = True
    for p_key in ["p1", "p2"]:
        opponent_key = "p2" if p_key == "p1" else "p1"
        if battle["menus"][opponent_key] == "force_switch" and battle["menus"][p_key] != "force_switch": continue
        if battle["choices"][p_key] is None:
            ready = False
            break

    if ready: await resolve_turn(battle_id, context, query)
    else: await sync_battle_state(battle_id, context)

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
        actions = []
        for p_key in ["p1", "p2"]: actions.append((p_key, battle["choices"][p_key]))
        def priority(action):
            p, c = action
            if c["type"] == "switch": return 1000000
            return battle[p]["team"][battle[p]["active"]]["stats"]["spd"] + random.uniform(0, 0.99)
        actions.sort(key=priority, reverse=True)
        
        for p_key, choice in actions:
            player, opponent = battle[p_key], battle["p2" if p_key == "p1" else "p1"]
            if player["team"][player["active"]]["hp"] <= 0: continue
                
            if choice["type"] == "switch":
                old_name = player["team"][player["active"]]["name"]
                player["active"] = choice["index"]
                new_name = player["team"][choice["index"]]["name"]
                action_text += f"🔄 {player['name']} withdrew {old_name} and sent out {new_name}!\n"
            elif choice["type"] == "move":
                atk_pkmn, def_pkmn = player["team"][player["active"]], opponent["team"][opponent["active"]]
                move = atk_pkmn["moves"][choice["index"]]
                
                if move["pp"] <= 0:
                    action_text += f"{atk_pkmn['name']} tried to use {move['name']} but has no PP left!\n"
                    continue
                move["pp"] -= 1
                
                type_mod = get_type_multiplier(move["type"], def_pkmn["types"])
                
                # Abilities (Defender)
                if def_pkmn["ability"] == "Levitate" and move["type"] == "ground":
                    type_mod = 0.0
                    
                stab = 1.5 if move["type"] in atk_pkmn["types"] else 1.0
                
                # Abilities (Attacker)
                if atk_pkmn["hp"] <= atk_pkmn["max_hp"] / 3:
                    if atk_pkmn["ability"] == "Overgrow" and move["type"] == "grass": stab *= 1.5
                    elif atk_pkmn["ability"] == "Blaze" and move["type"] == "fire": stab *= 1.5
                    elif atk_pkmn["ability"] == "Torrent" and move["type"] == "water": stab *= 1.5
                    elif atk_pkmn["ability"] == "Swarm" and move["type"] == "bug": stab *= 1.5
                
                dmg = calculate_damage(atk_pkmn["level"], move["power"], atk_pkmn["stats"], def_pkmn["stats"], move["class"], stab=stab, type_mod=type_mod)
                
                # Items (Attacker)
                if atk_pkmn["item"] == "Expert Belt" and type_mod > 1.0:
                    dmg = int(dmg * 1.2)
                elif atk_pkmn["item"] == "Life Orb":
                    dmg = int(dmg * 1.3)
                    
                # Abilities (Defender) passive
                if move["class"] == "physical" and def_pkmn["ability"] == "Intimidate":
                    dmg = int(dmg * 0.67)
                    
                # Items/Abilities preventing OHKO
                if dmg >= def_pkmn["hp"] and def_pkmn["hp"] == def_pkmn["max_hp"]:
                    if def_pkmn["item"] == "Focus Sash":
                        dmg = def_pkmn["hp"] - 1
                        def_pkmn["item"] = "None"
                        action_text += f"🎗️ {def_pkmn['name']} hung on using its Focus Sash!\n"
                    elif def_pkmn["ability"] == "Sturdy":
                        dmg = def_pkmn["hp"] - 1
                        action_text += f"🛡️ {def_pkmn['name']} endured the hit due to Sturdy!\n"
                        
                def_pkmn["hp"] = max(0, def_pkmn["hp"] - dmg)
                
                action_text += f"💥 {atk_pkmn['name']} used {move['name']}! "
                if type_mod > 1.0: action_text += "(It's super effective!) "
                elif type_mod > 0.0 and type_mod < 1.0: action_text += "(It's not very effective...) "
                elif type_mod == 0.0: action_text += "(It had no effect!) "
                action_text += f"(-{dmg} HP)\n"
                
                # Items (Defender) after damage
                if def_pkmn["hp"] > 0 and def_pkmn["hp"] <= def_pkmn["max_hp"] / 2 and def_pkmn["item"] == "Sitrus Berry":
                    heal = int(def_pkmn["max_hp"] / 4)
                    def_pkmn["hp"] = min(def_pkmn["max_hp"], def_pkmn["hp"] + heal)
                    def_pkmn["item"] = "None"
                    action_text += f"🫐 {def_pkmn['name']} restored health using its Sitrus Berry!\n"
                    
                # Life Orb Recoil
                if atk_pkmn["item"] == "Life Orb" and dmg > 0:
                    atk_pkmn["hp"] = max(0, atk_pkmn["hp"] - int(atk_pkmn["max_hp"] * 0.1))
                    action_text += f"🔮 {atk_pkmn['name']} lost some HP to its Life Orb!\n"
                    if atk_pkmn["hp"] == 0:
                        action_text += f"💀 {atk_pkmn['name']} fainted from Life Orb recoil!\n"
                        battle["menus"][p_key] = "force_switch"
                
                if def_pkmn["hp"] == 0:
                    action_text += f"💀 {def_pkmn['name']} fainted!\n"
                    battle["menus"]["p2" if p_key == "p1" else "p1"] = "force_switch"
                    
        battle["choices"] = {"p1": None, "p2": None}
        
        # End of turn effects
        for p_key in ["p1", "p2"]:
            active = battle[p_key]["team"][battle[p_key]["active"]]
            if active["hp"] > 0 and active["hp"] < active["max_hp"] and active["item"] == "Leftovers":
                heal = max(1, int(active["max_hp"] / 16))
                active["hp"] = min(active["max_hp"], active["hp"] + heal)
                action_text += f"🍏 {active['name']} restored a little HP using Leftovers!\n"
        
    reset_timeout(context, battle_id)
    battle["action_text"] = action_text
    await sync_battle_state(battle_id, context)

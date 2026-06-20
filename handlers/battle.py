from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from engine import fetch_random_team, calculate_damage
from utils.type_chart import get_type_multiplier
from utils.card_generator import generate_trainer_card
from database import db
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
            try: await context.bot.edit_message_caption(chat_id=battle[p_key]["dm_chat_id"], message_id=battle[p_key]["dm_msg_id"], caption=text)
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
        "p1": {"id": challenger.id, "name": challenger.first_name, "tag": challenger.username, "team": p1_team, "active": 0, "dm_chat_id": None, "dm_msg_id": None, "damage_dealt": 0},
        "p2": {"id": None, "name": target_username, "tag": target_username.replace("@", ""), "team": p2_team, "active": 0, "dm_chat_id": None, "dm_msg_id": None, "damage_dealt": 0},
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
    
    card_bytes = generate_trainer_card({"_id": user.id, "username": user.first_name}, battle[player_key]["team"])
    dm_msg = await update.message.reply_photo(photo=card_bytes, caption="Loading arena...")
    battle[player_key]["dm_msg_id"] = dm_msg.message_id
    
    if battle["p1"]["dm_chat_id"] and battle["p2"]["dm_chat_id"]:
        reset_timeout(context, battle_id)
        await sync_battle_state(battle_id, context)
    else:
        await context.bot.edit_message_caption(chat_id=battle[player_key]["dm_chat_id"], message_id=battle[player_key]["dm_msg_id"], caption="⌛ Waiting for your opponent to join...")

def get_player_buttons(battle, player_key, battle_id):
    opponent_key = "p2" if player_key == "p1" else "p1"
    if battle["menus"][opponent_key] == "force_switch" and battle["menus"][player_key] != "force_switch": return []
        
    p_data = battle[player_key]
    menu = battle["menus"][player_key]
    buttons = []
    if battle["choices"][player_key] is not None: return []
    
    if menu == "main":
        active_pkmn = p_data["team"][p_data["active"]]
        row1 = [InlineKeyboardButton(str(i+1), callback_data=f"btn_{battle_id}_{player_key}_move_{i}") for i in range(min(2, len(active_pkmn['moves'])))]
        row2 = [InlineKeyboardButton(str(i+1), callback_data=f"btn_{battle_id}_{player_key}_move_{i}") for i in range(2, len(active_pkmn['moves']))]
        switch_btn = [InlineKeyboardButton(f"Switch Pokémon", callback_data=f"btn_{battle_id}_{player_key}_menu_switch")]
        resign_btn = [InlineKeyboardButton(f"🏳️ Resign", callback_data=f"btn_{battle_id}_{player_key}_menu_resign")]
        if row1: buttons.append(row1)
        if row2: buttons.append(row2)
        buttons.append(switch_btn)
        buttons.append(resign_btn)
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
        p1_won = p2_alive == 0
        p2_won = p1_alive == 0
        
        winner = battle["p2"]["name"] if p1_alive == 0 else battle["p1"]["name"]
        loser = battle["p1"]["name"] if p1_alive == 0 else battle["p2"]["name"]
        win_text = f"{battle['action_text']}\n\n🏆 <b>{winner}</b> wins the battle!"
        
        # Calculate Elo and update DB
        p1_db = await db.get_user(battle["p1"]["id"])
        p2_db = await db.get_user(battle["p2"]["id"])
        
        elo_text = ""
        if p1_db and p2_db:
            p1_elo = p1_db.get("elo", 1000)
            p2_elo = p2_db.get("elo", 1000)
            
            p1_expected = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
            p2_expected = 1 / (1 + 10 ** ((p1_elo - p2_elo) / 400))
            
            k = 32
            p1_elo_change = int(k * ((1 if p1_won else 0) - p1_expected))
            p2_elo_change = int(k * ((1 if p2_won else 0) - p2_expected))
            
            await db.update_battle_stats(battle["p1"]["id"], p1_won, battle["p1"]["damage_dealt"], p1_elo_change)
            await db.update_battle_stats(battle["p2"]["id"], p2_won, battle["p2"]["damage_dealt"], p2_elo_change)
            
            elo_text = f"\n\n📈 {battle['p1']['name']}: {p1_elo_change:+d} Elo\n📉 {battle['p2']['name']}: {p2_elo_change:+d} Elo"
            win_text += elo_text
        
        for p_key in ["p1", "p2"]:
            if battle[p_key]["dm_chat_id"]:
                try: await context.bot.edit_message_caption(chat_id=battle[p_key]["dm_chat_id"], message_id=battle[p_key]["dm_msg_id"], caption=win_text, parse_mode="HTML")
                except Exception: pass
                
        try:
            winner_key = "p2" if p1_alive == 0 else "p1"
            winner_user = {"_id": battle[winner_key]["id"], "username": battle[winner_key]["name"]}
            winner_card = generate_trainer_card(winner_user, battle[winner_key]["team"])
            await context.bot.send_photo(chat_id=battle["group_chat_id"], reply_to_message_id=battle["group_msg_id"], photo=winner_card, caption=f"🏆 The battle has concluded!\n<b>{winner}</b> defeated <b>{loser}</b> in a 6v6 Showdown!{elo_text}", parse_mode="HTML")
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
    
    my_hp_pct = my_active['hp'] / my_active['max_hp']
    opp_hp_pct = opp_active['hp'] / opp_active['max_hp']
    
    my_bars = max(1, int(round(my_hp_pct * 10))) if my_active['hp'] > 0 else 0
    opp_bars = max(1, int(round(opp_hp_pct * 10))) if opp_active['hp'] > 0 else 0
    
    my_hp_bar = "▓" * my_bars + "░" * (10 - my_bars)
    opp_hp_bar = "▓" * opp_bars + "░" * (10 - opp_bars)

    my_status = f" [{my_active['status'].upper()}]" if my_active.get("status") else ""
    opp_status = f" [{opp_active['status'].upper()}]" if opp_active.get("status") else ""

    text += (
        f"{my_hp_bar} {my_active['hp']}/{my_active['max_hp']} HP\n"
        f"▛ Your {my_active['name']}{my_status} (Poké: {me_alive}/6)\n"
        f"╰ Item: {my_active['item']} | Ability: {my_active['ability']}\n\n"
        f"{opp_hp_bar} {int(opp_hp_pct * 100)}% HP\n"
        f"▙ Enemy {opp_active['name']}{opp_status} (Poké: {opp_alive}/6)\n\n"
    )
    
    thinking = []
    if battle["choices"][player_key] is None and battle["menus"][player_key] != "main" and battle["menus"][opponent_key] == "force_switch" and battle["menus"][player_key] != "force_switch":
        pass 
    else:
        if battle["choices"][player_key] is None and len(get_player_buttons(battle, player_key, battle_id)) > 0: thinking.append(me["name"])
        if battle["choices"][opponent_key] is None and len(get_player_buttons(battle, opponent_key, battle_id)) > 0: thinking.append(opp["name"])
        
    if battle["choices"][player_key] is None and battle["menus"][player_key] == "main":
        for i, m in enumerate(my_active["moves"]):
            acc = m.get("accuracy", "-")
            text += f"{i+1}. {m['name']} ({m['power']}/{acc} | {m['pp']}/{m['max_pp']})\n"
        text += "\n"
        
    if len(thinking) == 2: text += f"■ Both players making choices..."
    elif len(thinking) == 1: text += f"Waiting for {thinking[0]}..."
    
    keyboard = get_player_buttons(battle, player_key, battle_id)
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    try: await context.bot.edit_message_caption(chat_id=me["dm_chat_id"], message_id=me["dm_msg_id"], caption=text, reply_markup=reply_markup)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to edit dm message: {e}")

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
        if action_val == "resign":
            for pkmn in battle[player_key]["team"]:
                pkmn["hp"] = 0
            battle["action_text"] = f"{battle[player_key]['name']} forfeited the match!"
            await sync_battle_state(battle_id, context)
            await query.answer("You resigned.")
            return
            
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
            spd = battle[p]["team"][battle[p]["active"]]["stats"]["spd"]
            if battle[p]["team"][battle[p]["active"]].get("status") == "paralyzed": spd *= 0.5
            return spd + random.uniform(0, 0.99)
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
                
                # Pre-attack status checks
                if atk_pkmn.get("status") == "paralyzed" and random.randint(1, 100) <= 25:
                    action_text += f"⚡ {atk_pkmn['name']} is fully paralyzed and can't move!\n"
                    continue
                elif atk_pkmn.get("status") == "frozen":
                    if random.randint(1, 100) <= 20:
                        action_text += f"🧊 {atk_pkmn['name']} thawed out!\n"
                        atk_pkmn["status"] = None
                    else:
                        action_text += f"🧊 {atk_pkmn['name']} is frozen solid!\n"
                        continue
                elif atk_pkmn.get("status") == "sleep":
                    if random.randint(1, 100) <= 33:
                        action_text += f"💤 {atk_pkmn['name']} woke up!\n"
                        atk_pkmn["status"] = None
                    else:
                        action_text += f"💤 {atk_pkmn['name']} is fast asleep.\n"
                        continue
                
                if move["pp"] <= 0:
                    action_text += f"{atk_pkmn['name']} tried to use {move['name']} but has no PP left!\n"
                    continue
                move["pp"] -= 1
                
                acc = move.get("accuracy", "-")
                if acc != "-" and isinstance(acc, int):
                    if random.randint(1, 100) > acc:
                        action_text += f"💥 {atk_pkmn['name']}'s {move['name']} missed!\n"
                        continue
                
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
                
                is_crit = False
                if random.randint(1, 100) <= 6: # ~6.25% standard gen crit chance
                    is_crit = True
                crit_mod = 1.5 if is_crit else 1.0
                
                dmg = calculate_damage(atk_pkmn["level"], move["power"], atk_pkmn["stats"], def_pkmn["stats"], move["class"], stab=stab, type_mod=type_mod, crit=crit_mod)
                
                if is_crit:
                    action_text += "A critical hit! "
                
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
                    if def_pkmn["ability"] == "Sturdy":
                        dmg = def_pkmn["max_hp"] - 1
                        action_text += f"🛡️ {def_pkmn['name']} endured the hit due to Sturdy!\n"
                    elif def_pkmn["item"] == "Focus Sash":
                        dmg = def_pkmn["max_hp"] - 1
                        def_pkmn["item"] = "None"
                        action_text += f"🎗️ {def_pkmn['name']} hung on using its Focus Sash!\n"
                        
                if atk_pkmn.get("status") == "burned" and move["class"] == "physical":
                    dmg = max(1, int(dmg * 0.5))
                
                # Track actual damage dealt
                actual_dmg = min(def_pkmn["hp"], dmg)
                battle[p_key]["damage_dealt"] += actual_dmg
                def_pkmn["hp"] = max(0, def_pkmn["hp"] - dmg)
                
                action_text += f"💥 {atk_pkmn['name']} used {move['name']}! "
                if type_mod > 1.0: action_text += "(It's super effective!) "
                elif type_mod < 1.0 and type_mod > 0: action_text += "(It's not very effective...) "
                elif type_mod == 0: action_text += "(It had no effect...) "
                action_text += f"(-{actual_dmg} HP)\n"
                
                # Secondary Effects
                if def_pkmn["hp"] > 0 and type_mod > 0 and not def_pkmn.get("status"):
                    if move["type"] == "fire" and random.randint(1, 100) <= 10:
                        def_pkmn["status"] = "burned"
                        action_text += f"🔥 {def_pkmn['name']} was burned!\n"
                    elif move["type"] == "electric" and random.randint(1, 100) <= 10:
                        def_pkmn["status"] = "paralyzed"
                        action_text += f"⚡ {def_pkmn['name']} was paralyzed!\n"
                    elif move["type"] == "poison" and random.randint(1, 100) <= 30:
                        def_pkmn["status"] = "poisoned"
                        action_text += f"☠️ {def_pkmn['name']} was poisoned!\n"
                    elif move["type"] == "ice" and random.randint(1, 100) <= 10:
                        def_pkmn["status"] = "frozen"
                        action_text += f"🧊 {def_pkmn['name']} was frozen solid!\n"
                
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
            if active["hp"] <= 0: continue
            
            if active.get("status") in ["burned", "poisoned"]:
                dmg = max(1, active["max_hp"] // 8)
                active["hp"] = max(0, active["hp"] - dmg)
                if active["hp"] == 0:
                    if active["status"] == "burned": action_text += f"🔥 {active['name']} fainted from its burn!\n"
                    else: action_text += f"☠️ {active['name']} fainted from poison!\n"
                    battle["menus"][p_key] = "force_switch"
                else:
                    if active["status"] == "burned": action_text += f"🔥 {active['name']} was hurt by its burn!\n"
                    else: action_text += f"☠️ {active['name']} was hurt by poison!\n"
                    
            if active["hp"] > 0 and active["hp"] < active["max_hp"] and active["item"] == "Leftovers":
                heal = max(1, int(active["max_hp"] / 16))
                active["hp"] = min(active["max_hp"], active["hp"] + heal)
                action_text += f"🍏 {active['name']} restored a little HP using Leftovers!\n"
        
    reset_timeout(context, battle_id)
    battle["action_text"] = action_text
    await sync_battle_state(battle_id, context)

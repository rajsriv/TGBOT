from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from engine import fetch_random_team, calculate_damage
from utils.formulas import get_stat_multiplier
from utils.type_chart import get_type_multiplier
from utils.card_generator import generate_trainer_card
from utils.abilities import execute_ability_hook
from database import db
import random

active_battles = {}

async def battle_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    battle_id = context.job.data
    if battle_id not in active_battles: return
    battle = active_battles[battle_id]
    
    p1_picked = battle["choices"]["p1"] is not None
    p2_picked = battle["choices"]["p2"] is not None
    
    if p1_picked and not p2_picked:
        battle["action_text"] = f"{battle['p2']['name']} fled the battle!"
        for pkmn in battle["p2"]["team"]: pkmn["hp"] = 0
        await sync_battle_state(battle_id, context)
        return
    elif p2_picked and not p1_picked:
        battle["action_text"] = f"{battle['p1']['name']} fled the battle!"
        for pkmn in battle["p1"]["team"]: pkmn["hp"] = 0
        await sync_battle_state(battle_id, context)
        return
        
    # Both fled or never joined
    text = "⌛ Battle timed out! Both players fled."
    for p_key in ["p1", "p2"]:
        if battle[p_key]["dm_chat_id"]:
            try: await context.bot.edit_message_caption(chat_id=battle[p_key]["dm_chat_id"], message_id=battle[p_key]["dm_msg_id"], caption=text)
            except Exception: pass
            
    try:
        await context.bot.send_message(chat_id=battle["group_chat_id"], reply_to_message_id=battle["group_msg_id"], text=f"The battle ended due to inactivity! {text}")
    except Exception: pass

    del active_battles[battle_id]

async def auto_resolve_job(context: ContextTypes.DEFAULT_TYPE):
    battle_id = context.job.data
    if battle_id not in active_battles: return
    battle = active_battles[battle_id]
    if battle["menus"]["p1"] == "force_switch" or battle["menus"]["p2"] == "force_switch": return
    
    for p_key in ["p1", "p2"]:
        pkmn = battle[p_key]["team"][battle[p_key]["active"]]
        if "charging" in pkmn.get("volatile_status", []):
            battle["choices"][p_key] = {"type": "move", "index": pkmn.get("charging_move", 0)}
        elif "recharging" in pkmn.get("volatile_status", []):
            battle["choices"][p_key] = {"type": "recharge"}
            
    try: await resolve_turn(battle_id, context, None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        battle["action_text"] = f"An engine error occurred during auto-resolve: {str(e)}. Turn reset."
        battle["choices"] = {"p1": None, "p2": None}
        for pk in ["p1", "p2"]: battle["menus"][pk] = "main"
        await sync_battle_state(battle_id, context)

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
        "menus": {"p1": "main", "p2": "main"},
        "spectators": {},
        "hazards": {
            "p1": {"stealth_rock": False, "spikes": 0, "toxic_spikes": 0, "sticky_web": False},
            "p2": {"stealth_rock": False, "spikes": 0, "toxic_spikes": 0, "sticky_web": False}
        },
        "terrain": None,
        "terrain_turns": 0
    }

    bot_username = context.bot.username
    url = f"https://t.me/{bot_username}?start={battle_id}"
    keyboard = [[InlineKeyboardButton("⚔️ Join Battle", url=url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await loading_msg.edit_text(f"⚔️ {challenger.first_name} challenged {target_username} to a 6v6 Random Battle!\n\nBoth players must click the button below to join the arena in my DMs!", reply_markup=reply_markup)
    
    # Start initial join timeout
    reset_timeout(context, battle_id)

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
        if "spectators" not in battle: battle["spectators"] = {}
        battle["spectators"][user.id] = {"dm_chat_id": update.message.chat_id, "dm_msg_id": None}
        dm_msg = await update.message.reply_text(f"👁️ You are now spectating {battle['p1']['name']} vs {battle['p2']['name']}!")
        battle["spectators"][user.id]["dm_msg_id"] = dm_msg.message_id
        await update_spectator_dm(battle_id, context, user.id)
        return
        
    user_db = await db.get_user(user.id)
    if not user_db:
        user_db = await db.create_user(user.id, user.username or user.first_name)
        
    battle[player_key]["dm_chat_id"] = update.message.chat_id
    
    user_db["first_name"] = user.first_name
    opponent_key = "p2" if player_key == "p1" else "p1"
    card_bytes = generate_trainer_card(
        user_db, 
        team=battle[player_key]["team"], 
        card_type="BATTLE"
    )
    
    if battle["p1"]["dm_chat_id"] and battle["p2"]["dm_chat_id"]:
        dm_msg = await update.message.reply_photo(photo=card_bytes, caption="Entering the arena...")
        battle[player_key]["dm_msg_id"] = dm_msg.message_id
        reset_timeout(context, battle_id)
        await sync_battle_state(battle_id, context)
    else:
        dm_msg = await update.message.reply_photo(photo=card_bytes, caption="⌛ Waiting for your opponent to join...")
        battle[player_key]["dm_msg_id"] = dm_msg.message_id

def get_player_buttons(battle, player_key, battle_id):
    opponent_key = "p2" if player_key == "p1" else "p1"
    if battle["menus"][opponent_key] == "force_switch" and battle["menus"][player_key] != "force_switch": return []
        
    p_data = battle[player_key]
    menu = battle["menus"][player_key]
    buttons = []
    if battle["choices"][player_key] is not None: return []
    
    if menu == "main":
        active_pkmn = p_data["team"][p_data["active"]]
        locked_move = active_pkmn.get("choice_locked")
        
        row1 = []
        row2 = []
        for i in range(len(active_pkmn['moves'])):
            if locked_move is not None and locked_move != i: continue
            btn = InlineKeyboardButton(str(i+1), callback_data=f"btn_{battle_id}_{player_key}_move_{i}")
            if len(row1) < 2: row1.append(btn)
            else: row2.append(btn)
            
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
            
            p1_seen = [p["name"] for p in battle["p1"]["team"]] + [p["name"] for p in battle["p2"]["team"]]
            p2_seen = p1_seen
            
            await db.update_battle_stats(battle["p1"]["id"], p1_won, battle["p1"]["damage_dealt"], p1_elo_change, p1_seen)
            await db.update_battle_stats(battle["p2"]["id"], p2_won, battle["p2"]["damage_dealt"], p2_elo_change, p2_seen)
            
            elo_text = f"\n\n📈 {battle['p1']['name']}: {p1_elo_change:+d} Elo\n📉 {battle['p2']['name']}: {p2_elo_change:+d} Elo"
            win_text += elo_text
        
        for p_key in ["p1", "p2"]:
            if battle[p_key]["dm_chat_id"]:
                try: await context.bot.edit_message_caption(chat_id=battle[p_key]["dm_chat_id"], message_id=battle[p_key]["dm_msg_id"], caption=win_text, parse_mode="HTML")
                except Exception: pass
                
        for spec_id, spec_data in battle.get("spectators", {}).items():
            if spec_data["dm_chat_id"]:
                try: await context.bot.edit_message_text(chat_id=spec_data["dm_chat_id"], message_id=spec_data["dm_msg_id"], text=win_text, parse_mode="HTML")
                except Exception: pass
                
        try:
            winner_key = "p2" if p1_alive == 0 else "p1"
            winner_db = p2_db if p1_alive == 0 else p1_db
            
            # Re-fetch winner DB to get the newly updated stats (including just-added win and elo)
            winner_db = await db.get_user(battle[winner_key]["id"]) if winner_db else {"_id": battle[winner_key]["id"], "username": battle[winner_key]["name"]}
            
            winner_db["first_name"] = battle[winner_key]["name"]
            loser_key = "p1" if winner_key == "p2" else "p2"
            
            winner_card = generate_trainer_card(
                winner_db, 
                team=battle[winner_key]["team"],
                card_type="RESULT",
                opponent_team=battle[loser_key]["team"],
                opponent_name=battle[loser_key]["name"]
            )
            await context.bot.send_photo(chat_id=battle["group_chat_id"], reply_to_message_id=battle["group_msg_id"], photo=winner_card, caption=f"🏆 The battle has concluded!\n<b>{winner}</b> defeated <b>{loser}</b> in a 6v6 Showdown!{elo_text}", parse_mode="HTML")
        except Exception: pass
        
        del active_battles[battle_id]
        current_jobs = context.job_queue.get_jobs_by_name(f"timeout_{battle_id}")
        for job in current_jobs: job.schedule_removal()
        return

    await update_player_dm(battle_id, context, "p1")
    await update_player_dm(battle_id, context, "p2")
    for spec_id in battle.get("spectators", {}).keys():
        await update_spectator_dm(battle_id, context, spec_id)

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
        if "Message is not modified" in str(e): return
        import asyncio
        for pkmn in me["team"]:
            if pkmn["hp"] > 0:
                opp["damage_dealt"] += pkmn["hp"]
                pkmn["hp"] = 0
        battle["action_text"] = f"🏳️ {me['name']} abandoned the battle! (Error: {e})"
        asyncio.create_task(sync_battle_state(battle_id, context))

async def update_spectator_dm(battle_id, context, spec_id):
    if battle_id not in active_battles: return
    battle = active_battles[battle_id]
    spec = battle.get("spectators", {}).get(spec_id)
    if not spec or not spec["dm_chat_id"]: return
    
    p1 = battle["p1"]
    p2 = battle["p2"]
    
    text = f"👁️ <b>Spectating: {p1['name']} vs {p2['name']}</b>\n\n"
    if battle["action_text"]: text += f"{battle['action_text']}\n\n"
    
    for pk, name in [("p1", p1['name']), ("p2", p2['name'])]:
        player = battle[pk]
        if not player["team"]: continue
        active = player["team"][player["active"]]
        alive = sum(1 for p in player["team"] if p["hp"] > 0)
        hp_pct = active['hp'] / active['max_hp']
        bars = max(1, int(round(hp_pct * 10))) if active['hp'] > 0 else 0
        hp_bar = "▓" * bars + "░" * (10 - bars)
        status = f" [{active['status'].upper()}]" if active.get("status") else ""
        
        text += (
            f"<b>{name}'s Team:</b>\n"
            f"{hp_bar} {int(hp_pct * 100)}% HP\n"
            f"▙ {active['name']}{status} (Poké: {alive}/6)\n\n"
        )
        
    thinking = []
    if battle["choices"]["p1"] is None and len(get_player_buttons(battle, "p1", battle_id)) > 0: thinking.append(p1["name"])
    if battle["choices"]["p2"] is None and len(get_player_buttons(battle, "p2", battle_id)) > 0: thinking.append(p2["name"])
    
    if len(thinking) == 2: text += f"■ Both players making choices..."
    elif len(thinking) == 1: text += f"Waiting for {thinking[0]}..."
    
    try: await context.bot.edit_message_text(chat_id=spec["dm_chat_id"], message_id=spec["dm_msg_id"], text=text, parse_mode="HTML")
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
    
    pkmn = battle[player_key]["team"][battle[player_key]["active"]]
    if "recharging" in pkmn.get("volatile_status", []) or "charging" in pkmn.get("volatile_status", []):
        await query.answer("Your Pokémon is locked in a move!", show_alert=True)
        return

    if action_type == "menu":
        if action_val == "resign":
            opponent_key = "p2" if player_key == "p1" else "p1"
            for pkmn in battle[player_key]["team"]:
                if pkmn["hp"] > 0:
                    battle[opponent_key]["damage_dealt"] += pkmn["hp"]
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

    # Auto-set choices for locked players BEFORE checking if ready!
    for p_key in ["p1", "p2"]:
        if battle["choices"][p_key] is None:
            active_pkmn = battle[p_key]["team"][battle[p_key]["active"]]
            if "charging" in active_pkmn.get("volatile_status", []):
                battle["choices"][p_key] = {"type": "move", "index": active_pkmn.get("charging_move", 0)}
            elif "recharging" in active_pkmn.get("volatile_status", []):
                battle["choices"][p_key] = {"type": "recharge"}

    ready = True
    for p_key in ["p1", "p2"]:
        opponent_key = "p2" if p_key == "p1" else "p1"
        if battle["menus"][opponent_key] == "force_switch" and battle["menus"][p_key] != "force_switch": continue
        if battle["choices"][p_key] is None:
            ready = False
            break

    if ready:
        try:
            await resolve_turn(battle_id, context, query)
        except Exception as e:
            import traceback
            traceback.print_exc()
            battle["action_text"] = f"An engine error occurred: {str(e)}. Turn reset to prevent freeze."
            battle["choices"] = {"p1": None, "p2": None}
            for pk in ["p1", "p2"]: battle["menus"][pk] = "main"
            await sync_battle_state(battle_id, context)
    else: await sync_battle_state(battle_id, context)

def apply_hazards(battle, p_key, pkmn):
    hazards = battle["hazards"][p_key]
    text = ""
    grounded = is_grounded(pkmn)
    
    if hazards["stealth_rock"]:
        from engine import get_type_multiplier
        weakness = get_type_multiplier("rock", pkmn["types"])
        dmg = max(1, int((pkmn["max_hp"] / 8) * weakness))
        pkmn["hp"] = max(0, pkmn["hp"] - dmg)
        text += f"🪨 Pointed stones dug into {pkmn['name']}! (-{dmg} HP)\n"
        
    if pkmn["hp"] <= 0: return text
        
    if grounded:
        if hazards["spikes"] > 0:
            dmg_frac = [8, 6, 4][hazards["spikes"] - 1]
            dmg = max(1, int(pkmn["max_hp"] / dmg_frac))
            pkmn["hp"] = max(0, pkmn["hp"] - dmg)
            text += f"🪡 {pkmn['name']} was hurt by the Spikes!\n"
            
        if pkmn["hp"] <= 0: return text
            
        if hazards["toxic_spikes"] > 0:
            if "poison" in pkmn["types"]:
                hazards["toxic_spikes"] = 0
                text += f"🧹 {pkmn['name']} absorbed the Toxic Spikes!\n"
            elif "steel" not in pkmn["types"] and not pkmn.get("status"):
                pkmn["status"] = "poisoned"
                text += f"☠️ {pkmn['name']} was poisoned by the Toxic Spikes!\n"
                
        if hazards["sticky_web"]:
            old_stage = pkmn["stat_stages"].get("spd", 0)
            new_stage = max(-6, old_stage - 1)
            if new_stage < old_stage:
                pkmn["stat_stages"]["spd"] = new_stage
                text += f"🕸️ {pkmn['name']} was caught in a Sticky Web! Its Speed fell!\n"
                
    return text

async def resolve_turn(battle_id, context, query):
    battle = active_battles[battle_id]
    is_force_switch = battle["menus"]["p1"] == "force_switch" or battle["menus"]["p2"] == "force_switch"
    action_text = ""
    
    if is_force_switch:
        for p_key in ["p1", "p2"]:
            if battle["menus"][p_key] == "force_switch" and battle["choices"][p_key]:
                choice = battle["choices"][p_key]
                battle[p_key]["active"] = choice["index"]
                pkmn = battle[p_key]["team"][choice["index"]]
                action_text += f"🔄 {battle[p_key]['name']} sent out {pkmn['name']}!\n"
                action_text += apply_hazards(battle, p_key, pkmn)
                if pkmn["hp"] <= 0:
                    action_text += f"💀 {pkmn['name']} fainted immediately upon switching in!\n"
                    # Stays in force switch menu
                else:
                    battle["menus"][p_key] = "main"
                    opp_key = "p2" if p_key == "p1" else "p1"
                    opp_pkmn = battle[opp_key]["team"][battle[opp_key]["active"]]
                    switch_hook_msg = execute_ability_hook("on_switch_in", pkmn["ability"], pkmn=pkmn, opp_pkmn=opp_pkmn, battle=battle)
                    if switch_hook_msg: action_text += switch_hook_msg
        battle["choices"] = {"p1": None, "p2": None}
    else:
        actions = []
        for p_key in ["p1", "p2"]: actions.append((p_key, battle["choices"][p_key]))
        def priority(action):
            p, c = action
            if c["type"] == "switch": return 1000000
            
            pkmn = battle[p]["team"][battle[p]["active"]]
            base_spd = pkmn["stats"]["spd"] * get_stat_multiplier(pkmn["stat_stages"].get("spd", 0))
            if pkmn.get("status") == "paralyzed": base_spd *= 0.5
            if pkmn["item"] == "Choice Scarf": base_spd *= 1.5
            
            if battle.get("trick_room", 0) > 0:
                base_spd = 10000 - base_spd
            
            prio = base_spd + random.uniform(0, 0.99)
            if c["type"] == "move":
                move_name = pkmn["moves"][c["index"]]["name"].lower()
                if move_name in ["protect", "detect"]:
                    prio += 10000
                elif move_name in ["fake out", "extreme speed", "quick attack", "mach punch", "bullet punch", "ice shard", "aqua jet", "sucker punch"]:
                    prio += 5000
                elif move_name == "trick room":
                    prio -= 10000
            return prio
            
        actions.sort(key=priority, reverse=True)
        
        for p_key, choice in actions:
            player, opponent = battle[p_key], battle["p2" if p_key == "p1" else "p1"]
            if player["team"][player["active"]]["hp"] <= 0: continue
                
            if choice["type"] == "switch":
                old_pkmn = player["team"][player["active"]]
                old_pkmn["toxic_turns"] = 1
                if "choice_locked" in old_pkmn: del old_pkmn["choice_locked"]
                
                player["active"] = choice["index"]
                new_pkmn = player["team"][choice["index"]]
                action_text += f"🔄 {player['name']} withdrew {old_name} and sent out {new_pkmn['name']}!\n"
                action_text += apply_hazards(battle, p_key, new_pkmn)
                if new_pkmn["hp"] <= 0:
                    action_text += f"💀 {new_pkmn['name']} fainted immediately upon switching in!\n"
                    battle["menus"][p_key] = "force_switch"
                else:
                    opp_key = "p2" if p_key == "p1" else "p1"
                    opp_pkmn = battle[opp_key]["team"][battle[opp_key]["active"]]
                    switch_hook_msg = execute_ability_hook("on_switch_in", new_pkmn["ability"], pkmn=new_pkmn, opp_pkmn=opp_pkmn, battle=battle)
                    if switch_hook_msg: action_text += switch_hook_msg
            elif choice["type"] == "move":
                atk_pkmn, def_pkmn = player["team"][player["active"]], opponent["team"][opponent["active"]]
                move = atk_pkmn["moves"][choice["index"]]
                
                # Psychic Terrain Priority Check
                is_priority = move["name"].lower() in ["fake out", "extreme speed", "quick attack", "mach punch", "bullet punch", "ice shard", "aqua jet", "sucker punch", "vacuum wave", "shadow sneak"]
                if is_priority and battle.get("terrain") == "psychic" and is_grounded(def_pkmn):
                    action_text += f"{atk_pkmn['name']} cannot use {move['name']} because of Psychic Terrain!\n"
                    continue
                
                # Pre-attack status checks
                if "confused" in atk_pkmn.get("volatile_status", []):
                    atk_pkmn["confusion_turns"] = atk_pkmn.get("confusion_turns", 0) - 1
                    if atk_pkmn["confusion_turns"] <= 0:
                        atk_pkmn["volatile_status"].remove("confused")
                        action_text += f"💫 {atk_pkmn['name']} snapped out of its confusion!\n"
                    else:
                        action_text += f"💫 {atk_pkmn['name']} is confused!\n"
                        if random.randint(1, 100) <= 33:
                            action_text += f"It hurt itself in its confusion!\n"
                            conf_dmg = calculate_damage(atk_pkmn["level"], 40, atk_pkmn["stats"].copy(), atk_pkmn["stats"].copy(), "physical")
                            atk_pkmn["hp"] = max(0, atk_pkmn["hp"] - conf_dmg)
                            if atk_pkmn["hp"] == 0:
                                action_text += f"💀 {atk_pkmn['name']} fainted from confusion damage!\n"
                                battle["menus"][p_key] = "force_switch"
                            continue

                if "taunted" in atk_pkmn.get("volatile_status", []):
                    atk_pkmn["taunt_turns"] = atk_pkmn.get("taunt_turns", 0) - 1
                    if atk_pkmn["taunt_turns"] <= 0:
                        atk_pkmn["volatile_status"].remove("taunted")
                        action_text += f"🗯️ {atk_pkmn['name']}'s taunt wore off!\n"
                    elif move["power"] == 0:
                        action_text += f"🗯️ {atk_pkmn['name']} can't use {move['name']} after the taunt!\n"
                        continue

                if "flinch" in atk_pkmn.get("volatile_status", []):
                    action_text += f"{atk_pkmn['name']} flinched and couldn't move!\n"
                    atk_pkmn["volatile_status"].remove("flinch")
                    continue
                    
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
                    
                if move["name"].lower() == "steel roller":
                    action_text += f"{atk_pkmn['name']} tried to use Steel Roller, but it failed without Terrain!\n"
                    continue
                    
                if move["name"].lower() == "trick room":
                    move["pp"] -= 1
                    if battle.get("trick_room", 0) > 0:
                        battle["trick_room"] = 0
                        action_text += f"✨ {atk_pkmn['name']} used Trick Room!\nThe twisted dimensions returned to normal!\n"
                    else:
                        battle["trick_room"] = 5
                        action_text += f"✨ {atk_pkmn['name']} used Trick Room!\nThe dimensions were twisted!\n"
                    continue
                    
                # Charging Moves
                is_charging_move = move["name"].lower() in ["solar beam", "fly", "dig", "dive", "bounce", "skull bash", "razor wind", "sky attack"]
                if is_charging_move and "charging" not in atk_pkmn.get("volatile_status", []):
                    atk_pkmn.setdefault("volatile_status", []).append("charging")
                    atk_pkmn["charging_move"] = choice["index"]
                    move["pp"] -= 1 # Deduct PP on turn 1
                    
                    if move["name"].lower() == "solar beam": action_text += f"☀️ {atk_pkmn['name']} absorbed light!\n"
                    elif move["name"].lower() in ["fly", "bounce"]:
                        action_text += f"🦅 {atk_pkmn['name']} flew up high!\n"
                        atk_pkmn["volatile_status"].append("invulnerable")
                    elif move["name"].lower() == "dig":
                        action_text += f"🕳️ {atk_pkmn['name']} burrowed underground!\n"
                        atk_pkmn["volatile_status"].append("invulnerable")
                    elif move["name"].lower() == "dive":
                        action_text += f"🌊 {atk_pkmn['name']} dove underwater!\n"
                        atk_pkmn["volatile_status"].append("invulnerable")
                    else:
                        action_text += f"🔋 {atk_pkmn['name']} is charging its attack!\n"
                    continue
                elif is_charging_move:
                    atk_pkmn["volatile_status"].remove("charging")
                    if "invulnerable" in atk_pkmn["volatile_status"]: atk_pkmn["volatile_status"].remove("invulnerable")
                else:
                    move["pp"] -= 1 # Normal move
                    if "Choice" in atk_pkmn["item"] and "choice_locked" not in atk_pkmn:
                        atk_pkmn["choice_locked"] = choice["index"]
                
                if move["name"].lower() in ["protect", "detect"]:
                    success_rate = 100 // (2 ** atk_pkmn.get("protect_counter", 0))
                    
                    if random.randint(1, 100) <= success_rate:
                        if "protect" not in atk_pkmn.get("volatile_status", []):
                            atk_pkmn.setdefault("volatile_status", []).append("protect")
                        atk_pkmn["protect_counter"] = atk_pkmn.get("protect_counter", 0) + 1
                        action_text += f"🛡️ {atk_pkmn['name']} protected itself!\n"
                    else:
                        atk_pkmn["protect_counter"] = 0
                        action_text += f"💥 {atk_pkmn['name']}'s {move['name']} failed!\n"
                    continue
                else:
                    atk_pkmn["protect_counter"] = 0
                    
                # Defender is protecting or invulnerable?
                if "protect" in def_pkmn.get("volatile_status", []):
                    action_text += f"{atk_pkmn['name']} tried to use {move['name']}, but {def_pkmn['name']} protected itself!\n"
                    continue
                if "invulnerable" in def_pkmn.get("volatile_status", []) and move["name"].lower() not in ["earthquake", "magnitude", "surf"]:
                    action_text += f"{atk_pkmn['name']} used {move['name']}, but it missed because {def_pkmn['name']} is out of reach!\n"
                    continue
                
                acc = move.get("accuracy", "-")
                if acc != "-" and isinstance(acc, int):
                    atk_acc_stage = atk_pkmn.get("stat_stages", {}).get("accuracy", 0)
                    def_eva_stage = def_pkmn.get("stat_stages", {}).get("evasion", 0)
                    net_stage = max(-6, min(6, atk_acc_stage - def_eva_stage))
                    
                    if net_stage > 0:
                        acc_multiplier = (3 + net_stage) / 3.0
                    else:
                        acc_multiplier = 3.0 / (3 - net_stage)
                        
                    final_acc = int(acc * acc_multiplier)
                    
                    if random.randint(1, 100) > final_acc:
                        action_text += f"💥 {atk_pkmn['name']}'s {move['name']} missed!\n"
                        continue
                
                type_mod = get_type_multiplier(move["type"], def_pkmn["types"])
                
                # Abilities (Defender)
                defense_mod = execute_ability_hook("on_defense", def_pkmn["ability"], move=move)
                if defense_mod is not None:
                    type_mod *= defense_mod
                    
                stab = 1.5 if move["type"] in atk_pkmn["types"] else 1.0
                
                # Abilities (Attacker)
                attack_mod = execute_ability_hook("on_attack", atk_pkmn["ability"], atk_pkmn=atk_pkmn, move=move, stab=stab)
                if attack_mod is not None: stab = attack_mod
                
                is_crit = False
                if random.randint(1, 100) <= 6: # ~6.25% standard gen crit chance
                    is_crit = True
                crit_mod = 1.5 if is_crit else 1.0
                
                # Apply stat stages
                atk_stats = atk_pkmn["stats"].copy()
                def_stats = def_pkmn["stats"].copy()
                
                if atk_pkmn["item"] == "Choice Band" and move["class"] == "physical":
                    atk_stats["atk"] = int(atk_stats["atk"] * 1.5)
                elif atk_pkmn["item"] == "Choice Specs" and move["class"] == "special":
                    atk_stats["sp_atk"] = int(atk_stats["sp_atk"] * 1.5)
                
                # Critical hits ignore attacker's negative stages and defender's positive stages
                if move["class"] == "physical":
                    atk_stage = max(0, atk_pkmn["stat_stages"]["atk"]) if is_crit else atk_pkmn["stat_stages"]["atk"]
                    def_stage = min(0, def_pkmn["stat_stages"]["def"]) if is_crit else def_pkmn["stat_stages"]["def"]
                    atk_stats["atk"] = int(atk_stats["atk"] * get_stat_multiplier(atk_stage))
                    def_stats["def"] = int(def_stats["def"] * get_stat_multiplier(def_stage))
                else:
                    atk_stage = max(0, atk_pkmn["stat_stages"]["sp_atk"]) if is_crit else atk_pkmn["stat_stages"]["sp_atk"]
                    def_stage = min(0, def_pkmn["stat_stages"]["sp_def"]) if is_crit else def_pkmn["stat_stages"]["sp_def"]
                    atk_stats["sp_atk"] = int(atk_stats["sp_atk"] * get_stat_multiplier(atk_stage))
                    def_stats["sp_def"] = int(def_stats["sp_def"] * get_stat_multiplier(def_stage))
                
                weather_mod = 1.0
                if battle.get("weather") == "rain":
                    if move["type"] == "water": weather_mod = 1.5
                    elif move["type"] == "fire": weather_mod = 0.5
                elif battle.get("weather") == "sun":
                    if move["type"] == "fire": weather_mod = 1.5
                    elif move["type"] == "water": weather_mod = 0.5
                    
                if battle.get("weather") == "sandstorm" and "rock" in def_pkmn["types"]:
                    def_stats["sp_def"] = int(def_stats["sp_def"] * 1.5)
                    
                terrain_mod = 1.0
                if battle.get("terrain") == "electric" and move["type"] == "electric" and is_grounded(atk_pkmn): terrain_mod = 1.3
                elif battle.get("terrain") == "grassy" and move["type"] == "grass" and is_grounded(atk_pkmn): terrain_mod = 1.3
                elif battle.get("terrain") == "psychic" and move["type"] == "psychic" and is_grounded(atk_pkmn): terrain_mod = 1.3
                
                if battle.get("terrain") == "misty" and move["type"] == "dragon" and is_grounded(def_pkmn): terrain_mod = 0.5
                elif battle.get("terrain") == "grassy" and move["name"].lower() in ["earthquake", "magnitude", "bulldoze"] and is_grounded(def_pkmn): terrain_mod = 0.5
                
                dmg = calculate_damage(atk_pkmn["level"], move["power"], atk_stats, def_stats, move["class"], stab=stab, type_mod=type_mod, crit=crit_mod, weather_mod=weather_mod)
                dmg = int(dmg * terrain_mod)
                
                if is_crit and move["power"] > 0:
                    action_text += "A critical hit! "
                
                # Items (Attacker)
                if atk_pkmn["item"] == "Expert Belt" and type_mod > 1.0:
                    dmg = int(dmg * 1.2)
                elif atk_pkmn["item"] == "Life Orb":
                    dmg = int(dmg * 1.3)
                    
                # Items/Abilities preventing OHKO
                if dmg >= def_pkmn["hp"] and def_pkmn["hp"] == def_pkmn["max_hp"]:
                    if def_pkmn["item"] == "Focus Sash":
                        dmg = def_pkmn["max_hp"] - 1
                        def_pkmn["item"] = "None"
                        action_text += f"🎗️ {def_pkmn['name']} hung on using its Focus Sash!\n"
                
                dmg_hook = execute_ability_hook("on_damage", def_pkmn["ability"], dmg=dmg, def_pkmn=def_pkmn)
                if dmg_hook is not None:
                    if dmg_hook < dmg and dmg_hook == def_pkmn["max_hp"] - 1:
                        action_text += f"🛡️ {def_pkmn['name']} endured the hit due to Sturdy!\n"
                    dmg = dmg_hook
                        
                if atk_pkmn.get("status") == "burned" and move["class"] == "physical":
                    dmg = max(1, int(dmg * 0.5))
                
                hit_substitute = False
                hits = 1
                multi_2 = ["double kick", "twinneedle", "gear grind", "bonemerang", "dual chop", "double hit"]
                multi_2_5 = ["bullet seed", "icicle spear", "rock blast", "pin missile", "bone rush", "fury swipes", "double slap", "comet punch", "spike cannon", "barrage", "fury attack", "tail slap", "water shuriken"]
                m_name_lower = move["name"].lower()
                
                if m_name_lower in multi_2: hits = 2
                elif m_name_lower in multi_2_5:
                    r = random.randint(1, 100)
                    if r <= 35: hits = 2
                    elif r <= 70: hits = 3
                    elif r <= 85: hits = 4
                    else: hits = 5
                    
                total_actual_dmg = 0
                hits_landed = 0
                
                if move["power"] > 0:
                    action_text += f"💥 {atk_pkmn['name']} used {move['name']}! "
                    
                    for _ in range(hits):
                        if def_pkmn["hp"] <= 0: break
                        hits_landed += 1
                        
                        if "substitute" in def_pkmn.get("volatile_status", []):
                            actual_dmg = min(def_pkmn["substitute_hp"], dmg)
                            def_pkmn["substitute_hp"] -= dmg
                            total_actual_dmg += actual_dmg
                            hit_substitute = True
                            if def_pkmn["substitute_hp"] <= 0:
                                def_pkmn["volatile_status"].remove("substitute")
                                action_text += f"(The substitute broke!) "
                        else:
                            actual_dmg = min(def_pkmn["hp"], dmg)
                            total_actual_dmg += actual_dmg
                            def_pkmn["hp"] = max(0, def_pkmn["hp"] - dmg)
                            hit_substitute = False
                            
                    battle[p_key]["damage_dealt"] += total_actual_dmg
                    
                    if hits_landed > 1: action_text += f"Hit {hits_landed} time(s)! "
                    if move["type"] in atk_pkmn["types"]: action_text += "(STAB!) "
                    if type_mod > 1.0: action_text += "(It's super effective!) "
                    elif type_mod < 1.0 and type_mod > 0: action_text += "(It's not very effective...) "
                    elif type_mod == 0: action_text += "(It had no effect...) "
                    action_text += f"(-{total_actual_dmg} HP)\n"
                    
                    actual_dmg = total_actual_dmg
                    if actual_dmg > 0 and not hit_substitute:
                        hit_msg = execute_ability_hook("on_hit_receive", def_pkmn["ability"], move=move, atk_pkmn=atk_pkmn)
                        if hit_msg: action_text += hit_msg
                        
                        # Draining Moves
                        draining_moves = ["giga drain", "drain punch", "horn leech", "absorb", "mega drain", "leech life", "oblivion wing", "parabolic charge"]
                        if move["name"].lower() in draining_moves:
                            if def_pkmn["ability"] == "Liquid Ooze":
                                ooze_dmg = max(1, actual_dmg // 2)
                                atk_pkmn["hp"] = max(0, atk_pkmn["hp"] - ooze_dmg)
                                action_text += f"💧 {atk_pkmn['name']} sucked up the liquid ooze and was hurt! (-{ooze_dmg} HP)\n"
                            else:
                                heal = max(1, actual_dmg // 2)
                                if atk_pkmn["hp"] < atk_pkmn["max_hp"]:
                                    atk_pkmn["hp"] = min(atk_pkmn["max_hp"], atk_pkmn["hp"] + heal)
                                    action_text += f"🌿 {atk_pkmn['name']} had its HP restored! (+{heal} HP)\n"
                                    
                        # Recoil Moves
                        recoil_moves_33 = ["flare blitz", "double-edge", "brave bird", "wood hammer", "wild charge", "volt tackle"]
                        recoil_moves_25 = ["take down", "submission"]
                        recoil_moves_50 = ["head smash", "light of ruin"]
                        
                        m_name = move["name"].lower()
                        recoil_frac = 0
                        if m_name in recoil_moves_33: recoil_frac = 1/3
                        elif m_name in recoil_moves_25: recoil_frac = 1/4
                        elif m_name in recoil_moves_50: recoil_frac = 1/2
                        
                        if recoil_frac > 0:
                            if atk_pkmn["ability"] != "Rock Head":
                                recoil_dmg = max(1, int(actual_dmg * recoil_frac))
                                atk_pkmn["hp"] = max(0, atk_pkmn["hp"] - recoil_dmg)
                                action_text += f"💥 {atk_pkmn['name']} was damaged by the recoil! (-{recoil_dmg} HP)\n"
                
                if move["power"] == 0:
                    m_name = move["name"].lower()
                    
                    def can_status(pkmn, status_type):
                        if battle.get("terrain") == "misty" and is_grounded(pkmn): return False
                        if battle.get("terrain") == "electric" and is_grounded(pkmn) and status_type == "sleep": return False
                        return True
                        
                    if "substitute" in def_pkmn.get("volatile_status", []) and move.get("target") in ["selected-pokemon", "all-opponents"]:
                        action_text += f"✨ {atk_pkmn['name']} used {move['name']}!\nBut it failed against the substitute!\n"
                        continue
                        
                    action_text += f"✨ {atk_pkmn['name']} used {move['name']}!\n"
                    
                    if m_name == "electric terrain":
                        battle["terrain"] = "electric"
                        battle["terrain_turns"] = 5
                        action_text += "⚡ An electric current runs across the battlefield!\n"
                    elif m_name == "grassy terrain":
                        battle["terrain"] = "grassy"
                        battle["terrain_turns"] = 5
                        action_text += "🌿 Grass grew to cover the battlefield!\n"
                    elif m_name == "misty terrain":
                        battle["terrain"] = "misty"
                        battle["terrain_turns"] = 5
                        action_text += "🌫️ Mist swirled around the battlefield!\n"
                    elif m_name == "psychic terrain":
                        battle["terrain"] = "psychic"
                        battle["terrain_turns"] = 5
                        action_text += "🔮 The battlefield got weird!\n"
                    elif m_name == "substitute":
                        if "substitute" not in atk_pkmn.get("volatile_status", []) and atk_pkmn["hp"] > atk_pkmn["max_hp"] // 4:
                            atk_pkmn["hp"] -= atk_pkmn["max_hp"] // 4
                            atk_pkmn.setdefault("volatile_status", []).append("substitute")
                            atk_pkmn["substitute_hp"] = atk_pkmn["max_hp"] // 4
                            action_text += f"🧸 {atk_pkmn['name']} put in a substitute!\n"
                        else:
                            action_text += "But it failed!\n"
                    elif m_name == "leech seed":
                        if "grass" not in def_pkmn["types"] and "leech_seed" not in def_pkmn.get("volatile_status", []):
                            def_pkmn.setdefault("volatile_status", []).append("leech_seed")
                            action_text += f"🌱 {def_pkmn['name']} was seeded!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "taunt":
                        if "taunted" not in def_pkmn.get("volatile_status", []):
                            def_pkmn.setdefault("volatile_status", []).append("taunted")
                            def_pkmn["taunt_turns"] = 4
                            action_text += f"🗯️ {def_pkmn['name']} fell for the taunt!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name in ["confuse ray", "supersonic", "sweet kiss", "teeter dance"]:
                        if "confused" not in def_pkmn.get("volatile_status", []) and can_status(def_pkmn, "confusion"):
                            def_pkmn.setdefault("volatile_status", []).append("confused")
                            def_pkmn["confusion_turns"] = random.randint(2, 5)
                            action_text += f"💫 {def_pkmn['name']} became confused!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "toxic":
                        if "poison" in def_pkmn["types"] or "steel" in def_pkmn["types"] or not can_status(def_pkmn, "poison"):
                            action_text += "But it failed!\n"
                        elif "substitute" not in def_pkmn.get("volatile_status", []) and not def_pkmn.get("status"):
                            def_pkmn["status"] = "badly_poisoned"
                            def_pkmn["toxic_turns"] = 1
                            action_text += f"☣️ {def_pkmn['name']} was badly poisoned!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "thunder wave":
                        if "ground" in def_pkmn["types"] or not can_status(def_pkmn, "paralysis"):
                            action_text += "But it failed!\n"
                        elif "substitute" not in def_pkmn.get("volatile_status", []) and not def_pkmn.get("status"):
                            def_pkmn["status"] = "paralyzed"
                            action_text += f"⚡ {def_pkmn['name']} is paralyzed! It may be unable to move!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name in ["sleep powder", "spore", "hypnosis"]:
                        if ("grass" in def_pkmn["types"] and m_name in ["sleep powder", "spore"]) or not can_status(def_pkmn, "sleep"):
                            action_text += "But it failed!\n"
                        elif "substitute" not in def_pkmn.get("volatile_status", []) and not def_pkmn.get("status"):
                            def_pkmn["status"] = "sleep"
                            def_pkmn["sleep_turns"] = random.randint(1, 3)
                            action_text += f"💤 {def_pkmn['name']} fell asleep!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "will-o-wisp":
                        if "fire" in def_pkmn["types"] or not can_status(def_pkmn, "burn"):
                            action_text += "But it failed!\n"
                        elif "substitute" not in def_pkmn.get("volatile_status", []) and not def_pkmn.get("status"):
                            def_pkmn["status"] = "burned"
                            action_text += f"🔥 {def_pkmn['name']} was burned!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name in ["aromatherapy", "heal bell"]:
                        for pk in player["team"]: pk["status"] = None
                        action_text += f"✨ A soothing bell chimed! {player['name']}'s team was cured of all status problems!\n"
                    
                    if m_name == "rain dance":
                        battle["weather"] = "rain"
                        battle["weather_turns"] = 5
                        action_text += "🌧️ It started to rain!\n"
                    elif m_name == "sunny day":
                        battle["weather"] = "sun"
                        battle["weather_turns"] = 5
                        action_text += "☀️ The sunlight turned harsh!\n"
                    elif m_name == "sandstorm":
                        battle["weather"] = "sandstorm"
                        battle["weather_turns"] = 5
                        action_text += "🌪️ A sandstorm kicked up!\n"
                    elif m_name == "hail":
                        battle["weather"] = "hail"
                        battle["weather_turns"] = 5
                        action_text += "🌨️ It started to hail!\n"
                    elif m_name == "stealth rock":
                        if not battle["hazards"][opponent_key]["stealth_rock"]:
                            battle["hazards"][opponent_key]["stealth_rock"] = True
                            action_text += f"🪨 Pointed stones float in the air around {opponent['name']}'s team!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "spikes":
                        if battle["hazards"][opponent_key]["spikes"] < 3:
                            battle["hazards"][opponent_key]["spikes"] += 1
                            action_text += f"🪡 Spikes were scattered all around the feet of {opponent['name']}'s team!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "toxic spikes":
                        if battle["hazards"][opponent_key]["toxic_spikes"] < 2:
                            battle["hazards"][opponent_key]["toxic_spikes"] += 1
                            action_text += f"☠️ Poison spikes were scattered all around the feet of {opponent['name']}'s team!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "sticky web":
                        if not battle["hazards"][opponent_key]["sticky_web"]:
                            battle["hazards"][opponent_key]["sticky_web"] = True
                            action_text += f"🕸️ A sticky web spreads out on the ground around {opponent['name']}'s team!\n"
                        else: action_text += "But it failed!\n"
                    elif m_name == "defog":
                        battle["hazards"]["p1"] = {"stealth_rock": False, "spikes": 0, "toxic_spikes": 0, "sticky_web": False}
                        battle["hazards"]["p2"] = {"stealth_rock": False, "spikes": 0, "toxic_spikes": 0, "sticky_web": False}
                        action_text += "💨 A strong wind blew away all entry hazards!\n"
                
                if move["power"] > 0 and move["name"].lower() == "rapid spin":
                    battle["hazards"][p_key] = {"stealth_rock": False, "spikes": 0, "toxic_spikes": 0, "sticky_web": False}
                    action_text += f"🌀 {atk_pkmn['name']} blew away the hazards on its side!\n"
                
                # Apply Stat Changes
                for sc in move.get("stat_changes", []):
                    stat_chance = move.get("stat_chance", 100)
                    if random.randint(1, 100) > stat_chance: continue
                    
                    stat_target = move.get("stat_target", move.get("target", "selected-pokemon"))
                    target_pkmn = atk_pkmn if stat_target in ["user", "user-and-allies"] else def_pkmn
                    if target_pkmn == def_pkmn and hit_substitute: continue
                    
                    stat_name = sc["stat"]
                    change = sc["change"]
                    
                    if target_pkmn["hp"] <= 0: continue
                    
                    old_stage = target_pkmn["stat_stages"].get(stat_name, 0)
                    new_stage = max(-6, min(6, old_stage + change))
                    
                    if new_stage == old_stage:
                        action_text += f"{target_pkmn['name']}'s {stat_name} won't go any {'higher' if change > 0 else 'lower'}!\n"
                    else:
                        target_pkmn["stat_stages"][stat_name] = new_stage
                        direction = "rose" if change > 0 else "fell"
                        degree = "sharply " if abs(change) > 1 else ""
                        action_text += f"📈 {target_pkmn['name']}'s {stat_name} {degree}{direction}!\n"
                
                # Secondary Effects
                if def_pkmn["hp"] > 0 and type_mod > 0 and not def_pkmn.get("status") and not hit_substitute:
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
                        
                if def_pkmn["hp"] > 0 and type_mod > 0 and move["class"] == "physical" and not hit_substitute:
                    if move["name"].lower() in ["bite", "headbutt", "rock slide", "waterfall", "iron head", "air slash", "dark pulse", "fake out"]:
                        if random.randint(1, 100) <= 30:
                            if "flinch" not in def_pkmn.setdefault("volatile_status", []):
                                def_pkmn["volatile_status"].append("flinch")
                
                if move["name"].lower() in ["hyper beam", "giga impact", "frenzy plant", "blast burn", "hydro cannon", "meteor mash"]:
                    atk_pkmn.setdefault("volatile_status", []).append("recharging")
                
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
                        
                if "confusion" in move.get("secondary", []) and not hit_substitute:
                    if random.randint(1, 100) <= 20 and "confused" not in def_pkmn.get("volatile_status", []):
                        def_pkmn.setdefault("volatile_status", []).append("confused")
                        def_pkmn["confusion_turns"] = random.randint(2, 5)
                        action_text += f"💫 {def_pkmn['name']} became confused!\n"
                
                for p_idx in [atk_pkmn, def_pkmn]:
                    if p_idx["item"] == "Lum Berry" and (p_idx.get("status") or "confused" in p_idx.get("volatile_status", [])):
                        p_idx["status"] = None
                        if "confused" in p_idx.get("volatile_status", []): p_idx["volatile_status"].remove("confused")
                        p_idx["item"] = "None"
                        action_text += f"🍒 {p_idx['name']} cured its status problem using its Lum Berry!\n"
                
                if def_pkmn["hp"] == 0:
                    action_text += f"💀 {def_pkmn['name']} fainted!\n"
                    battle["menus"]["p2" if p_key == "p1" else "p1"] = "force_switch"
            elif choice["type"] == "recharge":
                atk_pkmn = player["team"][player["active"]]
                action_text += f"💤 {atk_pkmn['name']} must recharge!\n"
                if "recharging" in atk_pkmn.get("volatile_status", []):
                    atk_pkmn["volatile_status"].remove("recharging")
                    
        battle["choices"] = {"p1": None, "p2": None}
        
        # End of turn effects
        if battle.get("weather_turns", 0) > 0:
            battle["weather_turns"] -= 1
            if battle["weather_turns"] <= 0:
                w_msg = {"rain": "The rain stopped.", "sun": "The sunlight faded.", "sandstorm": "The sandstorm subsided.", "hail": "The hail stopped."}
                action_text += f"☁️ {w_msg.get(battle['weather'])}\n"
                battle["weather"] = None
                
        if battle.get("trick_room", 0) > 0:
            battle["trick_room"] -= 1
            if battle["trick_room"] == 0:
                action_text += "The twisted dimensions returned to normal!\n"
                
        # Terrain Turns
        if battle.get("terrain_turns", 0) > 0:
            battle["terrain_turns"] -= 1
            if battle["terrain_turns"] == 0:
                t_name = battle["terrain"].capitalize()
                action_text += f"🌍 The {t_name} Terrain disappeared.\n"
                battle["terrain"] = None
                
        for p_key in ["p1", "p2"]:
            active = battle[p_key]["team"][battle[p_key]["active"]]
            
            # Grassy Terrain Healing
            if battle.get("terrain") == "grassy" and is_grounded(active) and active["hp"] > 0 and active["hp"] < active["max_hp"]:
                heal = max(1, active["max_hp"] // 16)
                active["hp"] = min(active["max_hp"], active["hp"] + heal)
                action_text += f"🌿 {active['name']} restored a little HP from the Grassy Terrain!\n"
                
            if active["hp"] > 0 and active["hp"] < active["max_hp"] and active["item"] == "Leftovers":
                heal = max(1, int(active["max_hp"] / 16))
                active["hp"] = min(active["max_hp"], active["hp"] + heal)
                action_text += f"🍏 {active['name']} restored a little HP using Leftovers!\n"
            
            # Clear volatile statuses like protect and flinch at the end of the turn
            if "protect" in active.get("volatile_status", []):
                active["volatile_status"].remove("protect")
            if "flinch" in active.get("volatile_status", []):
                active["volatile_status"].remove("flinch")
                
            if active["hp"] <= 0: continue
            
            # Weather damage
            if battle.get("weather") == "sandstorm" and not any(t in active["types"] for t in ["rock", "ground", "steel"]):
                if active["ability"] not in ["Sand Veil", "Sand Rush", "Sand Force", "Overcoat"]:
                    dmg = max(1, active["max_hp"] // 16)
                    active["hp"] = max(0, active["hp"] - dmg)
                    if active["hp"] == 0:
                        action_text += f"🌪️ {active['name']} was buffeted by the sandstorm and fainted!\n"
                        battle["menus"][p_key] = "force_switch"
                    else:
                        action_text += f"🌪️ {active['name']} is buffeted by the sandstorm!\n"

            if active["hp"] <= 0: continue

            if battle.get("weather") == "hail" and "ice" not in active["types"]:
                if active["ability"] not in ["Snow Cloak", "Ice Body", "Overcoat"]:
                    dmg = max(1, active["max_hp"] // 16)
                    active["hp"] = max(0, active["hp"] - dmg)
                    if active["hp"] == 0:
                        action_text += f"🌨️ {active['name']} was pelted by hail and fainted!\n"
                        battle["menus"][p_key] = "force_switch"
                    else:
                        action_text += f"🌨️ {active['name']} is pelted by hail!\n"

            if active["hp"] <= 0: continue
            
            if "leech_seed" in active.get("volatile_status", []):
                dmg = max(1, active["max_hp"] // 8)
                active["hp"] = max(0, active["hp"] - dmg)
                
                opp_key = "p2" if p_key == "p1" else "p1"
                opp_active = battle[opp_key]["team"][battle[opp_key]["active"]]
                if opp_active["hp"] > 0 and opp_active["hp"] < opp_active["max_hp"]:
                    opp_active["hp"] = min(opp_active["max_hp"], opp_active["hp"] + dmg)
                    
                if active["hp"] == 0:
                    action_text += f"🌱 {active['name']} had its energy drained and fainted!\n"
                    battle["menus"][p_key] = "force_switch"
                else:
                    action_text += f"🌱 {active['name']}'s health is sapped by Leech Seed!\n"
                    
            if active["hp"] <= 0: continue
            
            if active.get("status") in ["burned", "poisoned", "badly_poisoned"]:
                if active["status"] == "badly_poisoned":
                    dmg = max(1, active["max_hp"] * active.get("toxic_turns", 1) // 16)
                    active["toxic_turns"] = active.get("toxic_turns", 1) + 1
                else:
                    dmg = max(1, active["max_hp"] // 8)
                    
                active["hp"] = max(0, active["hp"] - dmg)
                if active["hp"] == 0:
                    if active["status"] == "burned": action_text += f"🔥 {active['name']} fainted from its burn!\n"
                    else: action_text += f"☠️ {active['name']} fainted from poison!\n"
                    battle["menus"][p_key] = "force_switch"
                else:
                    if active["status"] == "burned": action_text += f"🔥 {active['name']} was hurt by its burn!\n"
                    else: action_text += f"☠️ {active['name']} was hurt by poison!\n"
                    
            if active["hp"] > 0 and active["item"] == "Black Sludge":
                if "poison" in active["types"]:
                    heal = max(1, int(active["max_hp"] / 16))
                    if active["hp"] < active["max_hp"]:
                        active["hp"] = min(active["max_hp"], active["hp"] + heal)
                        action_text += f"🛢️ {active['name']} restored a little HP using Black Sludge!\n"
                else:
                    dmg = max(1, int(active["max_hp"] / 8))
                    active["hp"] = max(0, active["hp"] - dmg)
                    if active["hp"] == 0:
                        action_text += f"💀 {active['name']} fainted from Black Sludge!\n"
                        battle["menus"][p_key] = "force_switch"
                    else:
                        action_text += f"🛢️ {active['name']} was hurt by Black Sludge!\n"
        
    reset_timeout(context, battle_id)
    battle["action_text"] = action_text
    await sync_battle_state(battle_id, context)
    
    # Check if both players are locked into next turn!
    is_fs = battle["menus"]["p1"] == "force_switch" or battle["menus"]["p2"] == "force_switch"
    if not is_fs:
        p1_locked = "charging" in battle["p1"]["team"][battle["p1"]["active"]].get("volatile_status", []) or "recharging" in battle["p1"]["team"][battle["p1"]["active"]].get("volatile_status", [])
        p2_locked = "charging" in battle["p2"]["team"][battle["p2"]["active"]].get("volatile_status", []) or "recharging" in battle["p2"]["team"][battle["p2"]["active"]].get("volatile_status", [])
        if p1_locked and p2_locked:
            context.job_queue.run_once(auto_resolve_job, 2.5, data=battle_id)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from engine import fetch_random_pokemon, calculate_damage
import random

# Extremely simplified in-memory state. In production, use Redis or MongoDB.
active_battles = {}

async def showdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.reply_to_message and len(context.args) == 0:
        await msg.reply_text("Please reply to a user or tag them with /showdown @username!")
        return

    challenger = msg.from_user
    # Simplified target resolution
    target_username = context.args[0] if context.args else msg.reply_to_message.from_user.username

    sent_msg = await msg.reply_text(f"⚔️ {challenger.first_name} challenged {target_username} to a Random Battle!\n\nGenerating teams...")

    # Generate 1v1 Random Battle
    p1_pokemon = await fetch_random_pokemon()
    p2_pokemon = await fetch_random_pokemon()

    battle_id = f"b_{msg.message_id}"
    active_battles[battle_id] = {
        "p1": {"id": challenger.id, "name": challenger.first_name, "pkmn": p1_pokemon},
        "p2_tag": target_username.replace("@", ""),
        "p2": {"id": None, "name": target_username, "pkmn": p2_pokemon}, # We don't know their ID until they click
        "choices": {"p1": None, "p2": None}, # Simultaneous turn choices
        "status": "active"
    }

    await send_battle_state(msg.chat_id, battle_id, context, message_to_edit=sent_msg)

async def send_battle_state(chat_id, battle_id, context, action_text="", message_to_edit=None):
    battle = active_battles[battle_id]
    p1 = battle["p1"]
    p2 = battle["p2"]
    
    text = ""
    if action_text:
        text += f"{action_text}\n\n"

    text += (
        f"🔴 {p1['name']}'s {p1['pkmn']['name']}: {p1['pkmn']['hp']}/{p1['pkmn']['max_hp']} HP\n"
        f"🔵 {p2['name']}'s {p2['pkmn']['name']}: {p2['pkmn']['hp']}/{p2['pkmn']['max_hp']} HP\n\n"
    )
    
    # Check win condition
    if p1['pkmn']['hp'] <= 0:
        text += f"🏆 {p2['name']} wins!"
        if message_to_edit:
            await message_to_edit.edit_text(text)
        else:
            await context.bot.send_message(chat_id=chat_id, text=text)
        return
    elif p2['pkmn']['hp'] <= 0:
        text += f"🏆 {p1['name']} wins!"
        if message_to_edit:
            await message_to_edit.edit_text(text)
        else:
            await context.bot.send_message(chat_id=chat_id, text=text)
        return

    # If neither fainted, show buttons
    choices = battle["choices"]
    
    # Display who is still thinking
    thinking = []
    if choices["p1"] is None: thinking.append(p1["name"])
    if choices["p2"] is None: thinking.append(p2["name"])
    
    if len(thinking) == 2:
        text += f"👉 Both players must select a move!"
    elif len(thinking) == 1:
        text += f"⌛ Waiting for {thinking[0]} to select a move..."

    keyboard = []
    # P1 Moves (Red)
    p1_row1 = [InlineKeyboardButton(f"🔴 {m['name']}", callback_data=f"move_{battle_id}_p1_{i}") for i, m in enumerate(p1['pkmn']['moves'][:2])]
    p1_row2 = [InlineKeyboardButton(f"🔴 {m['name']}", callback_data=f"move_{battle_id}_p1_{i}") for i, m in enumerate(p1['pkmn']['moves'][2:])]
    keyboard.extend([p1_row1, p1_row2])
    
    # P2 Moves (Blue)
    p2_row1 = [InlineKeyboardButton(f"🔵 {m['name']}", callback_data=f"move_{battle_id}_p2_{i}") for i, m in enumerate(p2['pkmn']['moves'][:2])]
    p2_row2 = [InlineKeyboardButton(f"🔵 {m['name']}", callback_data=f"move_{battle_id}_p2_{i}") for i, m in enumerate(p2['pkmn']['moves'][2:])]
    keyboard.extend([p2_row1, p2_row2])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if message_to_edit:
        await message_to_edit.edit_text(text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def handle_move_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_") # move_b_1234_p1_0
    
    if len(data) < 5:
        await query.answer("This battle is from an older version! Please start a new /showdown.", show_alert=True)
        return
        
    battle_id = f"{data[1]}_{data[2]}"
    player_key = data[3]
    move_index = int(data[4])

    if battle_id not in active_battles:
        await query.answer("This battle is no longer active.", show_alert=True)
        return

    battle = active_battles[battle_id]
    user_id = query.from_user.id

    # Register Player 2 if they are clicking for the first time
    if battle["p2"]["id"] is None and player_key == "p2" and query.from_user.username == battle["p2_tag"]:
        battle["p2"]["id"] = user_id
        battle["p2"]["name"] = query.from_user.first_name

    # Validate correct player is clicking their own buttons
    if user_id != battle[player_key]["id"]:
        await query.answer("These are not your moves!", show_alert=True)
        return

    # Check if they already locked in
    if battle["choices"][player_key] is not None:
        await query.answer("You already locked in your move! Waiting for opponent...", show_alert=True)
        return

    # Lock in move
    battle["choices"][player_key] = move_index
    await query.answer("Move locked in!")

    # Check if both have chosen
    if battle["choices"]["p1"] is not None and battle["choices"]["p2"] is not None:
        # Resolve turn
        p1 = battle["p1"]
        p2 = battle["p2"]
        p1_move = p1["pkmn"]["moves"][battle["choices"]["p1"]]
        p2_move = p2["pkmn"]["moves"][battle["choices"]["p2"]]
        
        # Speed tiebreaker
        p1_spd = p1["pkmn"]["stats"]["spd"]
        p2_spd = p2["pkmn"]["stats"]["spd"]
        
        p1_first = True
        if p2_spd > p1_spd:
            p1_first = False
        elif p1_spd == p2_spd:
            p1_first = random.choice([True, False]) # Speed Tie
            
        first = ("p1", p1, p1_move) if p1_first else ("p2", p2, p2_move)
        second = ("p2", p2, p2_move) if p1_first else ("p1", p1, p1_move)
        
        action_text = ""
        
        # Resolve first attacker
        dmg1 = calculate_damage(first[1]["pkmn"]["level"], first[2]["power"], first[1]["pkmn"]["stats"], second[1]["pkmn"]["stats"], first[2]["class"], stab=1.5 if first[2]["type"] in first[1]["pkmn"]["types"] else 1.0)
        second[1]["pkmn"]["hp"] = max(0, second[1]["pkmn"]["hp"] - dmg1)
        action_text += f"💨 {first[1]['name']}'s {first[1]['pkmn']['name']} is faster!\n"
        action_text += f"💥 {first[1]['pkmn']['name']} used {first[2]['name']}! ({dmg1} dmg)\n"
        
        # Resolve second attacker if still alive
        if second[1]["pkmn"]["hp"] > 0:
            dmg2 = calculate_damage(second[1]["pkmn"]["level"], second[2]["power"], second[1]["pkmn"]["stats"], first[1]["pkmn"]["stats"], second[2]["class"], stab=1.5 if second[2]["type"] in second[1]["pkmn"]["types"] else 1.0)
            first[1]["pkmn"]["hp"] = max(0, first[1]["pkmn"]["hp"] - dmg2)
            action_text += f"\n💥 {second[1]['pkmn']['name']} used {second[2]['name']}! ({dmg2} dmg)"
        else:
            action_text += f"\n💀 {second[1]['pkmn']['name']} fainted before it could move!"
            
        # Reset choices for next turn
        battle["choices"] = {"p1": None, "p2": None}
        
        await send_battle_state(query.message.chat_id, battle_id, context, action_text=action_text, message_to_edit=query.message)
    else:
        # Just update the text to say "Waiting for X..."
        await send_battle_state(query.message.chat_id, battle_id, context, action_text="", message_to_edit=query.message)

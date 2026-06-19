from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from engine import fetch_random_pokemon, calculate_damage

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

    await msg.reply_text(f"⚔️ {challenger.first_name} challenged {target_username} to a Random Battle!\n\nGenerating teams...")

    # Generate 1v1 Random Battle
    p1_pokemon = await fetch_random_pokemon()
    p2_pokemon = await fetch_random_pokemon()

    battle_id = f"b_{msg.message_id}"
    active_battles[battle_id] = {
        "p1": {"id": challenger.id, "name": challenger.first_name, "pkmn": p1_pokemon},
        "p2_tag": target_username.replace("@", ""),
        "p2": {"id": None, "name": target_username, "pkmn": p2_pokemon}, # We don't know their ID until they click
        "turn": "p1", # Player 1 goes first
        "status": "active"
    }

    await send_battle_state(msg.chat_id, battle_id, context)

async def send_battle_state(chat_id, battle_id, context):
    battle = active_battles[battle_id]
    p1 = battle["p1"]
    p2 = battle["p2"]
    
    text = (
        f"🔴 {p1['name']}'s {p1['pkmn']['name']}: {p1['pkmn']['hp']}/{p1['pkmn']['max_hp']} HP\n"
        f"🔵 {p2['name']}'s {p2['pkmn']['name']}: {p2['pkmn']['hp']}/{p2['pkmn']['max_hp']} HP\n\n"
    )
    
    # Check win condition
    if p1['pkmn']['hp'] <= 0:
        text += f"🏆 {p2['name']} wins!"
        await context.bot.send_message(chat_id=chat_id, text=text)
        return
    elif p2['pkmn']['hp'] <= 0:
        text += f"🏆 {p1['name']} wins!"
        await context.bot.send_message(chat_id=chat_id, text=text)
        return

    # Determine whose turn it is
    current_player = p1 if battle["turn"] == "p1" else p2
    text += f"👉 It is {current_player['name']}'s turn! Select a move:"

    keyboard = []
    for i, move in enumerate(current_player['pkmn']['moves']):
        keyboard.append([InlineKeyboardButton(f"{move['name']} ({move['power']} BP)", callback_data=f"move_{battle_id}_{i}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

async def handle_move_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_") # move_b_1234_0
    battle_id = f"{data[1]}_{data[2]}"
    move_index = int(data[3])

    if battle_id not in active_battles:
        await query.answer("This battle is no longer active.", show_alert=True)
        return

    battle = active_battles[battle_id]
    user_id = query.from_user.id

    # Register Player 2 if they are clicking for the first time and match the tag
    if battle["p2"]["id"] is None and query.from_user.username == battle["p2_tag"]:
        battle["p2"]["id"] = user_id
        battle["p2"]["name"] = query.from_user.first_name

    current_player_key = battle["turn"]
    current_player = battle[current_player_key]
    other_player_key = "p2" if current_player_key == "p1" else "p1"
    other_player = battle[other_player_key]

    if user_id != current_player["id"]:
        await query.answer("It's not your turn!", show_alert=True)
        return

    # Execute Move
    move = current_player["pkmn"]["moves"][move_index]
    
    stab = 1.5 if move["type"] in current_player["pkmn"]["types"] else 1.0
    damage = calculate_damage(
        current_player["pkmn"]["level"], 
        move["power"], 
        current_player["pkmn"]["stats"], 
        other_player["pkmn"]["stats"], 
        move["class"], 
        stab=stab
    )

    other_player["pkmn"]["hp"] = max(0, other_player["pkmn"]["hp"] - damage)
    
    await query.message.edit_text(f"💥 {current_player['name']}'s {current_player['pkmn']['name']} used {move['name']}!\nDealt {damage} damage.")

    # Swap turns
    battle["turn"] = other_player_key
    
    # Send next turn state
    await send_battle_state(query.message.chat_id, battle_id, context)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from handlers.battle import active_battles, fetch_random_team, sync_battle_state, reset_timeout
from utils.card_generator import generate_trainer_card
import random

async def match_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.chat.type != "private":
        await msg.reply_text("The /match command can only be used in my DMs!")
        return

    user = msg.from_user
    
    # Check if player is already in a battle
    to_delete = []
    for b_id, b_data in active_battles.items():
        if b_data["p1"]["id"] == user.id or b_data["p2"]["id"] == user.id:
            if not b_data["p1"].get("dm_chat_id") or not b_data["p2"].get("dm_chat_id"):
                to_delete.append(b_id)
            else:
                await msg.reply_text(f"⚔️ You are already in a battle! Please finish it first.")
                return
                
    for b_id in to_delete:
        del active_battles[b_id]

    keyboard = [
        [
            InlineKeyboardButton("🎮 Classic Mode", callback_data="match_classic"),
            InlineKeyboardButton("🏆 Ranked Mode", callback_data="match_ranked")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await msg.reply_text("Select a matchmaking mode against the AI:", reply_markup=reply_markup)

async def handle_match_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    user = query.from_user
    
    if data[0] != "match":
        return
        
    mode = data[1]
    
    if mode == "classic":
        # Ask for generation
        keyboard = [
            [InlineKeyboardButton("Gen 1", callback_data="match_start_classic_gen1"), InlineKeyboardButton("Gen 2", callback_data="match_start_classic_gen2")],
            [InlineKeyboardButton("Gen 3", callback_data="match_start_classic_gen3"), InlineKeyboardButton("Gen 4", callback_data="match_start_classic_gen4")],
            [InlineKeyboardButton("🎲 Random Gen", callback_data="match_start_classic_random")]
        ]
        await query.edit_message_text("Select the Generation for Classic Mode:", reply_markup=InlineKeyboardMarkup(keyboard))
        return
        
    elif mode == "start":
        match_type = data[2]
        gen_choice = data[3] if len(data) > 3 else "random"
        
        if gen_choice == "random":
            gen_choice = random.choice(["gen1", "gen2", "gen3", "gen4"])
            
        await query.edit_message_text(f"⚔️ Generating {match_type.capitalize()} Mode Match ({gen_choice.capitalize()})... (This may take a few seconds)")
        
        p1_team = await fetch_random_team(gen=gen_choice)
        p2_team = await fetch_random_team(gen=gen_choice)
        
        battle_id = f"bai_{query.message.message_id}"
        
        bot_personalities = {
            "Aggressive": ["Rival Blue", "Rival Silver", "Paul", "Champion Lance", "Boss Giovanni", "Champion Leon"],
            "Defensive": ["Gym Leader Brock", "Gym Leader Whitney", "Gym Leader Jasmine", "Elite Four Bertha", "Gym Leader Roxanne"],
            "Balanced": ["Pokemon Trainer Red", "Champion Cynthia", "Champion Steven", "Ash Ketchum", "Professor Oak", "Dawn"]
        }
        bot_personality = random.choice(list(bot_personalities.keys()))
        bot_name = random.choice(bot_personalities[bot_personality])
        
        user_db = await db.get_user(user.id)
        if not user_db:
            user_db = await db.create_user(user.id, user.username or user.first_name)
        user_db["first_name"] = user.first_name
        
        card_bytes = generate_trainer_card(
            user_db, 
            team=p1_team, 
            card_type="BATTLE"
        )
        dm_msg = await query.message.reply_photo(photo=card_bytes, caption="Entering the arena...")
        
        active_battles[battle_id] = {
            "group_chat_id": query.message.chat_id,
            "group_msg_id": dm_msg.message_id,
            "action_text": "",
            "is_ranked": match_type == "ranked",
            "p1": {"id": user.id, "name": user.first_name, "tag": user.username or user.first_name, "team": p1_team, "active": 0, "dm_chat_id": query.message.chat_id, "dm_msg_id": dm_msg.message_id, "damage_dealt": 0},
            "p2": {"id": -1, "name": f"{bot_personality} AI", "tag": "bot", "team": p2_team, "active": 0, "dm_chat_id": None, "dm_msg_id": None, "damage_dealt": 0, "is_bot": True, "personality": bot_personality},
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
        
        reset_timeout(context, battle_id)
        await query.message.delete()
        await sync_battle_state(battle_id, context)
        
    elif mode == "ranked":
        await query.edit_message_text(f"⚔️ Generating Ranked Match... (This may take a few seconds)")
        
        gen_choice = random.choice(["gen1", "gen2", "gen3", "gen4"])
        p1_team = await fetch_random_team(gen=gen_choice)
        p2_team = await fetch_random_team(gen=gen_choice)
        
        battle_id = f"bai_{query.message.message_id}"
        
        bot_personalities = {
            "Aggressive": ["Rival Blue", "Rival Silver", "Paul", "Champion Lance", "Boss Giovanni", "Champion Leon"],
            "Defensive": ["Gym Leader Brock", "Gym Leader Whitney", "Gym Leader Jasmine", "Elite Four Bertha", "Gym Leader Roxanne"],
            "Balanced": ["Pokemon Trainer Red", "Champion Cynthia", "Champion Steven", "Pokemon Trainer Ash", "Professor Oak", "Pokemon Trainer Dawn"]
        }
        bot_personality = random.choice(list(bot_personalities.keys()))
        bot_name = random.choice(bot_personalities[bot_personality])
        
        user_db = await db.get_user(user.id)
        if not user_db:
            user_db = await db.create_user(user.id, user.username or user.first_name)
        user_db["first_name"] = user.first_name
        
        card_bytes = generate_trainer_card(
            user_db, 
            team=p1_team, 
            card_type="BATTLE"
        )
        dm_msg = await query.message.reply_photo(photo=card_bytes, caption="Entering the arena...")
        
        active_battles[battle_id] = {
            "group_chat_id": query.message.chat_id,
            "group_msg_id": dm_msg.message_id,
            "action_text": "",
            "is_ranked": True,
            "p1": {"id": user.id, "name": user.first_name, "tag": user.username or user.first_name, "team": p1_team, "active": 0, "dm_chat_id": query.message.chat_id, "dm_msg_id": dm_msg.message_id, "damage_dealt": 0},
            "p2": {"id": -1, "name": bot_name, "tag": "bot", "team": p2_team, "active": 0, "dm_chat_id": None, "dm_msg_id": None, "damage_dealt": 0, "is_bot": True, "personality": bot_personality},
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
        
        reset_timeout(context, battle_id)
        await query.message.delete()
        await sync_battle_state(battle_id, context)

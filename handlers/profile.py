from telegram import Update
from telegram.ext import ContextTypes
from database import db
from utils.card_generator import generate_trainer_card

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    user = await db.get_user(user_id)
    if not user:
        user = await db.create_user(user_id, update.effective_user.username or update.effective_user.first_name)
            
    # Generate the custom trainer card image
    user['first_name'] = update.effective_user.first_name
    card_bytes = generate_trainer_card(user)
    
    await update.message.reply_photo(photo=card_bytes)

async def rank_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    user = await db.get_user(user_id)
    if not user:
        user = await db.create_user(user_id, update.effective_user.username or update.effective_user.first_name)
        
    elo = user.get("elo", 1000)
    
    msg = (
        f"📊 <b>Your Rank Stats</b>\n"
        f"Current Elo: <b>{elo}</b>\n\n"
        "🏆 <b>Elo Brackets & Rewards</b>\n"
        "<b>< 1100:</b> Poké Ball Rank (Default)\n"
        "<b>1100 - 1199:</b> Great Ball Rank <i>(Unlocks Great Ball Emblem)</i>\n"
        "<b>1200 - 1299:</b> Ultra Ball Rank <i>(Unlocks Ultra Ball Emblem)</i>\n"
        "<b>1300 - 1499:</b> Master Ball Rank <i>(Unlocks Master Ball Emblem)</i>\n"
        "<b>1500+:</b> Pokémon Champion <i>(Unlocks Red Sprite)</i>\n\n"
        "<i>Keep battling in /showdown and /match to increase your Elo and unlock these exclusive emblems for your Trainer Card!</i>"
    )
    
    await update.message.reply_text(msg, parse_mode="HTML")

from telegram import Update
from telegram.ext import ContextTypes
from database import db

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Try getting user from args if they tagged someone
    target_username = None
    if context.args:
        target_username = context.args[0].replace("@", "")
    elif update.message.reply_to_message:
        target_username = update.message.reply_to_message.from_user.username
        
    if target_username:
        # Search db by username
        user = await db.users.find_one({"username": target_username})
        if not user:
            await update.message.reply_text(f"Could not find a trainer named @{target_username}.")
            return
    else:
        user = await db.get_user(user_id)
        if not user:
            user = await db.create_user(user_id, update.effective_user.username or update.effective_user.first_name)
            
    stats = f"👤 **Trainer Profile: {user.get('username', 'Unknown')}**\n\n"
    stats += f"🏆 Elo Rating: {user.get('elo', 1000)}\n"
    stats += f"⚔️ Battles Played: {user.get('battles_played', 0)}\n"
    stats += f"✅ Wins: {user.get('wins', 0)} | ❌ Losses: {user.get('losses', 0)}\n"
    stats += f"💥 Total Damage Dealt: {user.get('total_damage', 0)}\n"
    
    total = user.get('battles_played', 0)
    if total > 0:
        winrate = (user.get('wins', 0) / total) * 100
        stats += f"📊 Win Rate: {winrate:.1f}%\n"
        
    await update.message.reply_text(stats)

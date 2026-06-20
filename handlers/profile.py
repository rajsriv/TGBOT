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
    card_bytes = generate_trainer_card(user)
    
    # Calculate win rate for caption
    total = user.get('battles_played', 0)
    winrate = (user.get('wins', 0) / total * 100) if total > 0 else 0
    
    caption = f"📊 Win Rate: {winrate:.1f}%\n"
    
    await update.message.reply_photo(photo=card_bytes, caption=caption)

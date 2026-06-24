from telegram import Update
from telegram.ext import ContextTypes
from database import db
from utils.card_generator import generate_team_card

async def team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    user = await db.get_user(user_id)
    if not user:
        await update.message.reply_text("You haven't started your journey yet! Use /start.")
        return
        
    team = user.get('team', [])
    if not team:
        await update.message.reply_text("You don't have any Pokémon in your team!")
        return
            
    # Generate the custom team card image
    card_bytes = generate_team_card(team)
    
    await update.message.reply_photo(photo=card_bytes)

from telegram import Update
from telegram.ext import ContextTypes
from database import db

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, username)
        await update.message.reply_text(
            f"Welcome to the Pokémon world, {username}! \n\n"
            "Go in groups and cook with your friends using /showdown (tag them)!"
        )
    else:
        await update.message.reply_text(
            f"Welcome back, {username}!"
        )

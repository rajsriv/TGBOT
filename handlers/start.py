from telegram import Update
from telegram.ext import ContextTypes
from database import db
from handlers.battle import join_battle

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name

    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id, username)

    # Check for deep links (e.g. t.me/bot?start=b_1234)
    if context.args and context.args[0].startswith("b_"):
        await join_battle(update, context, context.args[0])
        return

    if not user:
        await update.message.reply_text(
            f"Welcome to the Pokémon world, {username}! \n\n"
            "Go in groups and cook with your friends using /showdown (tag them)!"
        )
    else:
        await update.message.reply_text(
            f"Welcome back, {username}!"
        )

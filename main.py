import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from game_logic import game_manager
import leaderboard

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def get_hp_bar(current_hp, max_hp, length=10):
    if max_hp <= 0: return "💔" * length
    ratio = current_hp / max_hp
    hearts = int(ratio * length)
    broken = length - hearts
    return "❤️" * hearts + "💔" * broken

def build_battle_message(match):
    # p1_hp vs p2_hp
    p1_bar = get_hp_bar(match['p1_hp'], match['p1_max_hp'])
    p2_bar = get_hp_bar(match['p2_hp'], match['p2_max_hp'])
    
    text = (
        f"⚔️ **ANIME DUEL** ⚔️\n\n"
        f"**{match['p1_name']}**\nHP: {match['p1_hp']}/{match['p1_max_hp']}\n{p1_bar}\n\n"
        f"**{match['p2_name']}**\nHP: {match['p2_hp']}/{match['p2_max_hp']}\n{p2_bar}\n\n"
        f"📝 **Battle Log:**\n{match['log']}\n\n"
    )
    
    if match['status'] == 'ACTIVE':
        current_player = match['p1_name'] if match['current_turn'] == match['p1_id'] else match['p2_name']
        text += f"👉 **It's {current_player}'s turn!**"
        
    return text

def build_battle_keyboard(match_id, match):
    if match['status'] != 'ACTIVE':
        return InlineKeyboardMarkup([])
        
    keyboard = [
        [
            InlineKeyboardButton("🗡️ Quick (100%)", callback_data=f"move_{match_id}_quick"),
            InlineKeyboardButton("🔥 Power (70%)", callback_data=f"move_{match_id}_power")
        ],
        [
            InlineKeyboardButton("⚡ Ultimate (40%, HP<30%)", callback_data=f"move_{match_id}_ultimate")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚔️ Welcome to Anime Duel Bot! ⚔️\n\nUse /duel @username to challenge someone in a group chat!\nUse /leaderboard to view top players.")

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top_players = leaderboard.get_top_players(10)
    if not top_players:
        await update.message.reply_text("🏆 **Leaderboard is empty!** Be the first to win a duel!")
        return
        
    text = "🏆 **ANIME DUEL LEADERBOARD** 🏆\n\n"
    for i, p in enumerate(top_players, 1):
        text += f"{i}. {p['username']} - {p['wins']} wins\n"
        
    await update.message.reply_text(text)

async def duel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please specify an opponent! Example: /duel @username")
        return
        
    opponent_username = context.args[0]
    challenger = update.effective_user
    
    if challenger.id in game_manager.active_players:
        await update.message.reply_text("You are already in an active duel!")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"accept_duel_{challenger.id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"decline_duel_{challenger.id}")
        ]
    ]
    
    await update.message.reply_text(
        f"⚔️ {challenger.first_name} has challenged {opponent_username} to an Anime Duel! ⚔️\n\n"
        f"{opponent_username}, will you accept?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    if data.startswith("accept_duel_"):
        challenger_id = int(data.split("_")[2])
        if user.id == challenger_id:
            await query.answer("You cannot accept your own challenge!", show_alert=True)
            return
            
        if challenger_id in game_manager.active_players or user.id in game_manager.active_players:
            await query.answer("One of the players is already in a duel!", show_alert=True)
            return

        # Fetch challenger info from message text
        msg_text = query.message.text
        try:
            challenger_name = msg_text.split(" has challenged ")[0].replace("⚔️ ", "")
        except:
            challenger_name = "Player 1"
            
        opponent_name = user.first_name
        
        match = game_manager.create_match(challenger_id, challenger_name, user.id, opponent_name)
        
        text = build_battle_message(match)
        keyboard = build_battle_keyboard(match['match_id'], match)
        
        await query.edit_message_text(text=text, reply_markup=keyboard)
        
    elif data.startswith("decline_duel_"):
        challenger_id = int(data.split("_")[2])
        if user.id == challenger_id:
            await query.answer("You cannot decline your own challenge!", show_alert=True)
            return
            
        await query.edit_message_text(text=f"The duel was declined by {user.first_name}.")
        
    elif data.startswith("move_"):
        parts = data.split("_")
        match_id = parts[1]
        move_type = parts[2]
        
        match = game_manager.get_match(match_id)
        if not match:
            await query.answer("Match not found or expired.", show_alert=True)
            return
            
        if match['status'] != 'ACTIVE':
            await query.answer("This match is already finished.", show_alert=True)
            return
            
        if match['current_turn'] != user.id:
            await query.answer("It is not your turn!", show_alert=True)
            return
            
        success, msg = game_manager.process_move(match_id, user.id, move_type)
        if not success:
            await query.answer(msg, show_alert=True)
            return
            
        # Update UI
        text = build_battle_message(match)
        keyboard = build_battle_keyboard(match_id, match)
        
        await query.edit_message_text(text=text, reply_markup=keyboard)


def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is not set. Please copy .env.example to .env and set it.")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("duel", duel_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    logger.info("Starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()

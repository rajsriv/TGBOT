import logging
from telegram.ext import Application, CommandHandler
import config
from handlers.start import start_command
from handlers.battle import showdown_command, handle_move_callback
from handlers.profile import profile_command
from handlers.matchmaking import match_command, handle_match_callback
from telegram.ext import CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    if config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please set your BOT_TOKEN in the .env file!")
        return

    import os
    proxy_url = os.environ.get("BOT_PROXY_URL")
    
    # Create the Application and pass it your bot's token.
    builder = Application.builder().token(config.BOT_TOKEN)
    if proxy_url:
        builder = builder.proxy_url(proxy_url).get_updates_proxy_url(proxy_url)
    application = builder.build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("showdown", showdown_command))
    application.add_handler(CommandHandler("match", match_command))
    application.add_handler(CommandHandler("profile", profile_command))
    from handlers.vault import handle_vault_command, handle_equip_callback, handle_reward_command
    application.add_handler(CommandHandler("vault", handle_vault_command))
    application.add_handler(CommandHandler("reward", handle_reward_command))
    application.add_handler(CallbackQueryHandler(handle_move_callback, pattern="^btn_"))
    application.add_handler(CallbackQueryHandler(handle_match_callback, pattern="^match_"))
    application.add_handler(CallbackQueryHandler(handle_equip_callback, pattern="^equip_"))

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

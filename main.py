import logging
from telegram.ext import Application, CommandHandler
import config
from handlers.start import start_command
from handlers.battle import showdown_command, handle_move_callback
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

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(config.BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("showdown", showdown_command))
    application.add_handler(CallbackQueryHandler(handle_move_callback, pattern="^btn_"))

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == "__main__":
    main()

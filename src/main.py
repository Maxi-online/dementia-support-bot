import logging

from .bot.telegram_bot import DementiaSupportBot
from .core.config import settings


def main():
    # Logging setup
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    try:
        # Initialize and start the bot
        logger.info("Starting DementiaSupportBot...")
        bot = DementiaSupportBot()
        bot.run()
    except Exception as e:
        logger.error(f"Error while starting the bot: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

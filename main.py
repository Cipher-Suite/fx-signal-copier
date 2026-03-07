import asyncio
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def main():
    from bot.main import Bot
    bot = Bot()
    try:
        await bot.start()
    finally:
        await bot.stop()


if __name__ == '__main__':
    logger.info("Starting FX Signal Copier v2.0.0")
    asyncio.run(main())
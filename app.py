import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from aiogram import Bot
from config import (
    API_ID, API_HASH, BOT_TOKEN, GROUP_ID, POLL_INTERVAL, SESSION_NAME,
    GIFT_IDS, SEED_EXISTING, MAX_PAGES_PER_GIFT, LOG_LEVEL
)
from database import init_db, listing_exists, add_listing
from parser import get_gift_types, iter_listings
from publisher import publish

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
log = logging.getLogger("gift-tracker")

async def main():
    await init_db()
    bot = Bot(BOT_TOKEN)
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    try:
        await client.start()
        me = await client.get_me()
        log.info("MTProto session connected as %s", getattr(me, "username", None) or me.id)
        log.warning("First start may require interactive phone/code login. Complete it in a terminal before deploying headlessly.")

        while True:
            try:
                gift_types = await get_gift_types(client, GIFT_IDS)
                log.info("Gift types to scan: %d", len(gift_types))
                for gift_type in gift_types:
                    try:
                        async for listing in iter_listings(client, gift_type, MAX_PAGES_PER_GIFT):
                            exists = await listing_exists(listing["listing_key"])
                            if exists:
                                continue
                            # Seed first-run listings without flooding the group, if configured.
                            status = "seen" if SEED_EXISTING and not getattr(main, "_seed_complete", False) else "pending"
                            inserted = await add_listing(
                                listing["listing_key"], listing["gift_id"], listing["title"],
                                listing["price"], listing["slug"], status=status
                            )
                            if not inserted or status == "seen":
                                continue
                            await publish(bot, GROUP_ID, listing)
                    except FloodWaitError as e:
                        log.warning("Telegram FloodWait: sleeping %s seconds", e.seconds)
                        await asyncio.sleep(e.seconds)
                    except (RPCError, Exception):
                        log.exception("Error scanning gift type %s", getattr(gift_type, "id", "?"))
                        await asyncio.sleep(3)
                main._seed_complete = True
            except Exception:
                log.exception("Scan cycle failed")
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        await client.disconnect()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())

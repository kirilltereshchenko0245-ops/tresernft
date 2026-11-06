import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from aiogram import Bot
from config import (
    API_ID, API_HASH, BOT_TOKEN, PHONE_NUMBER, GROUP_ID, POLL_INTERVAL, SESSION_NAME,
    GIFT_IDS, SEED_EXISTING, MAX_PAGES_PER_GIFT, LOG_LEVEL
)
from database import init_db, listing_exists, add_listing, update_owner_metadata
from gift_parser import get_gift_types, iter_listings
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
        if STRING_SESSION:
            log.info("Starting with Telethon StringSession...")
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(
                    "STRING_SESSION is invalid, expired, or revoked. "
                    "Create a fresh StringSession and update the environment variable."
                )
        elif PHONE_NUMBER:
            log.info("Starting as userbot with phone number...")
            await client.start(phone=PHONE_NUMBER)
        else:
            log.info("Starting with existing .session file...")
            await client.connect()
            if not await client.is_user_authorized():
                raise RuntimeError(
                    f"No authorized Telegram session found. Upload {SESSION_NAME}.session "
                    "or set STRING_SESSION. Do not set PHONE_NUMBER on a non-interactive host."
                )

        me = await client.get_me()
        log.info("MTProto session connected as %s", getattr(me, "username", None) or me.id)

        while True:
            try:
                gift_types = await get_gift_types(client, GIFT_IDS)
                log.info("Gift types to scan: %d", len(gift_types))
                for gift_type in gift_types:
                    try:
                        async for listing in iter_listings(client, gift_type, MAX_PAGES_PER_GIFT):
                            exists = await listing_exists(listing["listing_key"])
                            if exists:
                                # Refresh only the public owner/host fields returned by Telegram.
                                await update_owner_metadata(listing["listing_key"], listing)
                                continue
                            # Seed first-run listings without flooding the group, if configured.
                            status = "seen" if SEED_EXISTING and not getattr(main, "_seed_complete", False) else "pending"
                            inserted = await add_listing(
                                listing["listing_key"], listing["gift_id"], listing["title"],
                                listing["price"], listing["slug"], status=status, owner=listing
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

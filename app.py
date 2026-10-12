import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from aiogram import Bot
from config import (
    API_ID, API_HASH, BOT_TOKEN, PHONE_NUMBER, GROUP_ID, POLL_INTERVAL, SESSION_NAME,
    GIFT_IDS, SEED_EXISTING, MAX_PAGES_PER_GIFT, LOG_LEVEL,
    TRACK_NON_UPGRADED, NON_UPGRADED_TOPIC_NAME
)
from database import init_db, listing_exists, add_listing
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
        # Проверяем, указан ли номер телефона для userbot
        if PHONE_NUMBER:
            # Режим userbot - авторизация через номер телефона
            log.info("Starting as userbot with phone number...")
            await client.start(phone=PHONE_NUMBER)
        else:
            # Попытка автоматической авторизации через существующую сессию
            log.info("Starting with existing session...")
            try:
                await client.start()
            except Exception as e:
                log.error("Failed to start with existing session: %s", e)
                log.error("РЕШЕНИЕ: Вам нужно:")
                log.error("1. Локально запустить: python app.py")
                log.error("2. Ввести номер телефона и код подтверждения")
                log.error("3. Загрузить созданный файл %s.session на сервер", SESSION_NAME)
                log.error("ИЛИ добавить PHONE_NUMBER в .env (но это требует интерактивного ввода кода)")
                raise
        
        me = await client.get_me()
        log.info("MTProto session connected as %s", getattr(me, "username", None) or me.id)

        while True:
            try:
                gift_types = await get_gift_types(client, GIFT_IDS)
                log.info("Gift types to scan: %d", len(gift_types))
                
                # Сканируем улучшенные подарки (за Stars)
                for gift_type in gift_types:
                    try:
                        async for listing in iter_listings(client, gift_type, MAX_PAGES_PER_GIFT, upgraded_only=True):
                            exists = await listing_exists(listing["listing_key"])
                            if exists:
                                continue
                            status = "seen" if SEED_EXISTING and not getattr(main, "_seed_complete", False) else "pending"
                            inserted = await add_listing(
                                listing["listing_key"], listing["gift_id"], listing["title"],
                                listing["price"], listing["slug"], status=status
                            )
                            if not inserted or status == "seen":
                                continue
                            await publish(bot, GROUP_ID, listing, NON_UPGRADED_TOPIC_NAME)
                    except FloodWaitError as e:
                        log.warning("Telegram FloodWait: sleeping %s seconds", e.seconds)
                        await asyncio.sleep(e.seconds)
                    except (RPCError, Exception):
                        log.exception("Error scanning upgraded gift type %s", getattr(gift_type, "id", "?"))
                        await asyncio.sleep(3)
                
                # Сканируем неулучшенные подарки (если включено)
                if TRACK_NON_UPGRADED:
                    log.info("Scanning non-upgraded gifts...")
                    for gift_type in gift_types:
                        try:
                            async for listing in iter_listings(client, gift_type, MAX_PAGES_PER_GIFT, upgraded_only=False):
                                exists = await listing_exists(listing["listing_key"])
                                if exists:
                                    continue
                                status = "seen" if SEED_EXISTING and not getattr(main, "_seed_complete", False) else "pending"
                                inserted = await add_listing(
                                    listing["listing_key"], listing["gift_id"], listing["title"],
                                    listing["price"], listing["slug"], status=status
                                )
                                if not inserted or status == "seen":
                                    continue
                                await publish(bot, GROUP_ID, listing, NON_UPGRADED_TOPIC_NAME)
                        except FloodWaitError as e:
                            log.warning("Telegram FloodWait: sleeping %s seconds", e.seconds)
                            await asyncio.sleep(e.seconds)
                        except (RPCError, Exception):
                            log.exception("Error scanning non-upgraded gift type %s", getattr(gift_type, "id", "?"))
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

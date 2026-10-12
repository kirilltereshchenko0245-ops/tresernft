import html
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from database import get_topic, save_topic, set_listing_status

log = logging.getLogger(__name__)

async def get_or_create_topic(bot: Bot, group_id: int, gift_id: str, title: str) -> int:
    thread_id = await get_topic(gift_id)
    if thread_id is not None:
        return thread_id
    topic = await bot.create_forum_topic(chat_id=group_id, name=title[:128])
    await save_topic(gift_id, title[:128], topic.message_thread_id)
    return topic.message_thread_id

async def publish(bot: Bot, group_id: int, listing: dict, non_upgraded_topic_name: str = "🎁 Неулучшенные подарки"):
    title = listing["title"]
    is_upgraded = listing.get("is_upgraded", True)
    
    # Для неулучшенных подарков используем общую тему
    if not is_upgraded:
        thread_id = await get_or_create_topic(
            bot, group_id, "non_upgraded_gifts", non_upgraded_topic_name
        )
        price_text = "💎 <b>Неулучшенный подарок</b>"
    else:
        # Для улучшенных - отдельная тема для каждого типа
        thread_id = await get_or_create_topic(
            bot, group_id, listing["gift_id"], title
        )
        price_text = f"⭐ <b>{listing['price']:,} Stars</b>".replace(",", " ") if listing["price"] is not None else "⭐ Цена недоступна"
    
    slug = listing.get("slug")
    link_line = f'🔗 <a href="https://t.me/nft/{html.escape(slug, quote=True)}">Открыть подарок</a>' if slug else "🔗 Ссылка на объявление недоступна"
    
    emoji = "💎" if not is_upgraded else "🎁"
    text = f"{emoji} <b>{html.escape(title)}</b>\n{price_text}\n{link_line}\n\n<i>Новое объявление</i>"
    
    try:
        await bot.send_message(
            chat_id=group_id,
            message_thread_id=thread_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        await set_listing_status(listing["listing_key"], "sent")
    except TelegramAPIError:
        log.exception("Failed to publish listing %s", listing["listing_key"])
        await set_listing_status(listing["listing_key"], "failed")
        raise

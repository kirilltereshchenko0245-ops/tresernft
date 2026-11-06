import html
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from database import get_topic, save_topic, set_listing_status

log = logging.getLogger(__name__)


def _owner_line(listing):
    username = listing.get("owner_username")
    owner_name = listing.get("owner_name")
    owner_id = listing.get("owner_id")
    owner_address = listing.get("owner_address")

    if username:
        label = f"@{username}"
        return f'👤 <b>Владелец:</b> <a href="https://t.me/{html.escape(username, quote=True)}">{html.escape(label)}</a>'
    if owner_name:
        return f"👤 <b>Владелец:</b> {html.escape(str(owner_name))}"
    if owner_id is not None:
        return f"👤 <b>Владелец:</b> ID {html.escape(str(owner_id))} (публичный username не предоставлен)"
    if owner_address:
        address = str(owner_address)
        return f"👛 <b>TON-адрес владельца:</b> <code>{html.escape(address)}</code>"
    return "👤 <b>Владелец:</b> Telegram не раскрыл данные"


def _host_line(listing):
    username = listing.get("host_username")
    host_name = listing.get("host_name")
    host_id = listing.get("host_id")
    if username:
        return f'🏷 <b>Профиль размещения:</b> <a href="https://t.me/{html.escape(username, quote=True)}">@{html.escape(username)}</a>'
    if host_name:
        return f"🏷 <b>Профиль размещения:</b> {html.escape(str(host_name))}"
    if host_id is not None:
        return f"🏷 <b>Профиль размещения:</b> ID {html.escape(str(host_id))}"
    return None


async def get_or_create_topic(bot: Bot, group_id: int, gift_id: str, title: str) -> int:
    thread_id = await get_topic(gift_id)
    if thread_id is not None:
        return thread_id
    topic = await bot.create_forum_topic(chat_id=group_id, name=title[:128])
    await save_topic(gift_id, title[:128], topic.message_thread_id)
    return topic.message_thread_id


async def publish(bot: Bot, group_id: int, listing: dict):
    title = listing["title"]
    thread_id = await get_or_create_topic(bot, group_id, listing["gift_id"], title)
    price_text = f"⭐ <b>{listing['price']:,} Stars</b>".replace(",", " ") if listing["price"] is not None else "⭐ Цена недоступна"
    slug = listing.get("slug")
    link_line = f'🔗 <a href="https://t.me/nft/{html.escape(slug, quote=True)}">Открыть подарок</a>' if slug else "🔗 Ссылка на объявление недоступна"
    lines = [f"🎁 <b>{html.escape(title)}</b>", price_text, _owner_line(listing)]
    # Show a blockchain owner address separately when Telegram provides one.
    if listing.get("owner_address") and listing.get("owner_id") is not None:
        lines.append(f"👛 <b>TON-адрес владельца:</b> <code>{html.escape(str(listing['owner_address']))}</code>")
    host_line = _host_line(listing)
    if host_line:
        lines.append(host_line)
    lines.extend([link_line, "", "<i>Новое объявление за Stars</i>"])
    text = "\n".join(lines)
    try:
        await bot.send_message(
            chat_id=group_id, message_thread_id=thread_id, text=text,
            parse_mode="HTML", disable_web_page_preview=True,
        )
        await set_listing_status(listing["listing_key"], "sent")
    except TelegramAPIError:
        log.exception("Failed to publish listing %s", listing["listing_key"])
        await set_listing_status(listing["listing_key"], "failed")
        raise

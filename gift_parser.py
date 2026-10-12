import logging
from telethon import functions, types

log = logging.getLogger(__name__)

def _get(obj, *names, default=None):
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default

async def get_gift_types(client, configured_ids: list[int]):
    # Explicit IDs are the most predictable fallback when Telegram's catalog schema changes.
    if configured_ids:
        return [types.StarGift(id=gift_id, sticker=None, stars=0) for gift_id in configured_ids]

    # Telethon's generated TL schema may change as Telegram updates its API.
    result = await client(functions.payments.GetStarGiftsRequest(hash=0))
    gifts = _get(result, "gifts", default=[]) or []
    return [g for g in gifts if _get(g, "id") is not None]

def gift_type_title(gift_type) -> str:
    title = _get(gift_type, "title", "name")
    if title:
        return str(title)[:128]
    gift_id = _get(gift_type, "id", default="unknown")
    return f"Gift {gift_id}"[:128]

def gift_type_id(gift_type):
    return _get(gift_type, "id")

async def scan_resale_page(client, gift_id: int, offset: str, upgraded_only: bool = True):
    """
    Сканирует страницу объявлений о продаже подарков
    
    Args:
        client: Telethon клиент
        gift_id: ID типа подарка
        offset: Смещение для пагинации
        upgraded_only: True = только улучшенные (stars_only), False = только неулучшенные
    """
    return await client(functions.payments.GetResaleStarGiftsRequest(
        gift_id=gift_id,
        offset=offset,
        limit=100,
        stars_only=upgraded_only,  # True = улучшенные за Stars, False = неулучшенные
    ))

def normalize_listing(item, gift_id: int, type_title: str, is_upgraded: bool = True):
    # TL object field names can differ by listing type/API layer; keep this tolerant.
    unique_gift = _get(item, "gift")
    slug = _get(item, "slug")
    title = type_title
    if unique_gift:
        title = str(_get(unique_gift, "title", "name", default=title))
        slug = slug or _get(unique_gift, "slug")
    price_obj = _get(item, "resell_amount", "price", "amount")
    price = _get(price_obj, "amount", default=price_obj)
    try:
        price = int(price) if price is not None else None
    except (TypeError, ValueError):
        price = None

    # Prefer a stable unique collectible identifier if exposed by the current API layer.
    unique_id = _get(unique_gift, "id", "slug") or slug
    if unique_id is None:
        unique_id = _get(item, "id", "gift_id")
    if unique_id is None:
        # Last-resort fingerprint. This is less reliable than a true listing ID.
        unique_id = f"{gift_id}:{price}:{repr(item)[:180]}"
    listing_key = f"{gift_id}:{unique_id}"
    return {
        "listing_key": str(listing_key),
        "gift_id": str(gift_id),
        "title": title[:128],
        "price": price,
        "slug": str(slug) if slug else None,
        "is_upgraded": is_upgraded,  # Флаг: улучшенный или нет
    }

async def iter_listings(client, gift_type, max_pages: int, upgraded_only: bool = True):
    """
    Итератор по объявлениям подарков
    
    Args:
        client: Telethon клиент
        gift_type: Тип подарка
        max_pages: Максимум страниц для сканирования
        upgraded_only: True = только улучшенные, False = только неулучшенные
    """
    gift_id = gift_type_id(gift_type)
    if gift_id is None:
        return
    title = gift_type_title(gift_type)
    offset = ""
    seen_offsets = set()
    for _ in range(max_pages):
        page = await scan_resale_page(client, int(gift_id), offset, upgraded_only)
        items = _get(page, "gifts", default=[]) or []
        for item in items:
            yield normalize_listing(item, int(gift_id), title, is_upgraded=upgraded_only)
        next_offset = _get(page, "next_offset", default="") or ""
        if not next_offset or next_offset == offset or next_offset in seen_offsets:
            break
        seen_offsets.add(next_offset)
        offset = next_offset

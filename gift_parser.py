import asyncio
import logging
from telethon import functions, types


log = logging.getLogger(__name__)


def _get(obj, *names, default=None):
    """Return the first non-None attribute from a Telethon TL object."""
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _peer_id(peer):
    """Return a typed peer identifier without trying to identify hidden users."""
    if peer is None:
        return None, None
    for attr, kind in (("user_id", "user"), ("channel_id", "channel"), ("chat_id", "chat")):
        value = getattr(peer, attr, None)
        if value is not None:
            return kind, int(value)
    # Some callers may already pass a User/Channel entity.
    value = getattr(peer, "id", None)
    if value is not None:
        return "peer", int(value)
    return None, None


def _public_profile(peer, users=None, chats=None):
    """Resolve only from entities Telegram included in this response."""
    kind, peer_id = _peer_id(peer)
    if peer_id is None:
        return {"kind": None, "id": None, "name": None, "username": None}

    candidates = list(users or []) + list(chats or [])
    for entity in candidates:
        if getattr(entity, "id", None) != peer_id:
            continue
        # Avoid matching a user and channel that happen to share a numeric ID.
        class_name = entity.__class__.__name__.lower()
        if class_name.startswith("user"):
            entity_kind = "user"
        elif class_name.startswith("channel"):
            entity_kind = "channel"
        elif class_name.startswith("chat"):
            entity_kind = "chat"
        else:
            entity_kind = "peer"
        if kind != "peer" and entity_kind != kind:
            continue
        username = _get(entity, "username")
        first = _get(entity, "first_name", default="") or ""
        last = _get(entity, "last_name", default="") or ""
        title = _get(entity, "title", default="") or ""
        name = (f"{first} {last}".strip() or title or None)
        return {"kind": kind, "id": peer_id, "name": name,
                "username": str(username) if username else None}
    return {"kind": kind, "id": peer_id, "name": None, "username": None}


def _owner_fields(unique_gift, users=None, chats=None):
    owner_peer = _get(unique_gift, "owner_id")
    host_peer = _get(unique_gift, "host_id")
    owner = _public_profile(owner_peer, users, chats)
    host = _public_profile(host_peer, users, chats)
    owner_name = _get(unique_gift, "owner_name")
    owner_address = _get(unique_gift, "owner_address")

    # owner_name is explicitly supplied by Telegram when no owner peer/address is exposed.
    if not owner["name"] and owner_name:
        owner["name"] = str(owner_name)

    return {
        "owner_kind": owner["kind"],
        "owner_id": owner["id"],
        "owner_name": owner["name"],
        "owner_username": owner["username"],
        "owner_address": str(owner_address) if owner_address else None,
        "host_kind": host["kind"],
        "host_id": host["id"],
        "host_name": host["name"],
        "host_username": host["username"],
    }


async def _call_with_reconnect(client, request, *, attempts: int = 5):
    """Retry a Telegram request after transient disconnects."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            if not client.is_connected():
                log.warning("MTProto is disconnected; reconnecting (attempt %s/%s)", attempt, attempts)
                await client.connect()
                if not await client.is_user_authorized():
                    raise RuntimeError("Telethon session is no longer authorized; check STRING_SESSION.")
            return await client(request)
        except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
            last_error = exc
            log.warning(
                "Telegram connection error on attempt %s/%s: %s",
                attempt, attempts, exc
            )
            try:
                await client.disconnect()
            except Exception:
                log.debug("Error while closing broken MTProto connection", exc_info=True)
            if attempt < attempts:
                await asyncio.sleep(min(2 ** attempt, 15))
    raise ConnectionError(
        f"Telegram connection failed after {attempts} attempts"
    ) from last_error


async def get_gift_types(client, configured_ids: list[int]):
    if configured_ids:
        return [types.StarGift(id=gift_id, sticker=None, stars=0) for gift_id in configured_ids]
    result = await _call_with_reconnect(
        client, functions.payments.GetStarGiftsRequest(hash=0)
    )
    gifts = _get(result, "gifts", default=[]) or []
    return [g for g in gifts if _get(g, "id") is not None]


def gift_type_title(gift_type) -> str:
    title = _get(gift_type, "title", "name")
    if title:
        return str(title)[:128]
    return f"Gift {_get(gift_type, 'id', default='unknown')}"[:128]


def gift_type_id(gift_type):
    return _get(gift_type, "id")


async def scan_resale_page(client, gift_id: int, offset: str):
    request = functions.payments.GetResaleStarGiftsRequest(
        gift_id=gift_id, offset=offset, limit=100, stars_only=True,
    )
    return await _call_with_reconnect(client, request)


def _price_amount(price_obj):
    if isinstance(price_obj, (list, tuple)):
        price_obj = next((p for p in price_obj if _get(p, "amount") is not None), None)
    value = _get(price_obj, "amount", default=price_obj)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def normalize_listing(item, gift_id: int, type_title: str, users=None, chats=None):
    # In current Telegram schema the resale vector can contain StarGiftUnique directly.
    # Keep support for wrappers used by older Telethon/API layers too.
    nested_gift = _get(item, "gift")
    unique_gift = nested_gift or item
    slug = _get(item, "slug") or _get(unique_gift, "slug")
    title = str(_get(unique_gift, "title", "name", default=type_title))
    price_obj = _get(item, "resell_amount", "price", "amount")
    if price_obj is None:
        price_obj = _get(unique_gift, "resell_amount", "price", "amount")
    price = _price_amount(price_obj)

    unique_id = _get(unique_gift, "id", "slug") or slug
    if unique_id is None:
        unique_id = _get(item, "id", "gift_id")
    if unique_id is None:
        unique_id = f"{gift_id}:{price}:{repr(item)[:180]}"

    result = {
        "listing_key": f"{gift_id}:{unique_id}",
        "gift_id": str(gift_id),
        "title": title[:128],
        "price": price,
        "slug": str(slug) if slug else None,
    }
    result.update(_owner_fields(unique_gift, users=users, chats=chats))
    return result


async def iter_listings(client, gift_type, max_pages: int):
    gift_id = gift_type_id(gift_type)
    if gift_id is None:
        return
    title = gift_type_title(gift_type)
    offset = ""
    seen_offsets = set()
    for _ in range(max_pages):
        page = await scan_resale_page(client, int(gift_id), offset)
        items = _get(page, "gifts", default=[]) or []
        users = _get(page, "users", default=[]) or []
        chats = _get(page, "chats", default=[]) or []
        for item in items:
            listing = normalize_listing(item, int(gift_id), title, users=users, chats=chats)
            if listing.get("owner_id") is None and not listing.get("owner_name") and not listing.get("owner_address"):
                log.debug("Telegram did not expose owner fields for collectible %s", listing.get("slug"))
            yield listing
        next_offset = _get(page, "next_offset", default="") or ""
        if not next_offset or next_offset == offset or next_offset in seen_offsets:
            break
        seen_offsets.add(next_offset)
        offset = next_offset

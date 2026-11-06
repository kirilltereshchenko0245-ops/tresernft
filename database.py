import os
import aiosqlite
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "data/gifts.db")


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                listing_key TEXT PRIMARY KEY,
                gift_id TEXT NOT NULL,
                title TEXT NOT NULL,
                price INTEGER,
                slug TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'seen',
                owner_kind TEXT,
                owner_id INTEGER,
                owner_name TEXT,
                owner_username TEXT,
                owner_address TEXT,
                host_kind TEXT,
                host_id INTEGER,
                host_name TEXT,
                host_username TEXT
            )
        """)
        # Safe migration for databases created by older releases.
        cur = await db.execute("PRAGMA table_info(listings)")
        existing = {row[1] for row in await cur.fetchall()}
        additions = {
            "owner_kind": "TEXT", "owner_id": "INTEGER", "owner_name": "TEXT",
            "owner_username": "TEXT", "owner_address": "TEXT", "host_kind": "TEXT",
            "host_id": "INTEGER", "host_name": "TEXT", "host_username": "TEXT",
        }
        for column, sql_type in additions.items():
            if column not in existing:
                await db.execute(f"ALTER TABLE listings ADD COLUMN {column} {sql_type}")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                gift_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                thread_id INTEGER NOT NULL
            )
        """)
        await db.commit()


async def listing_exists(listing_key: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM listings WHERE listing_key=?", (listing_key,))
        return await cur.fetchone() is not None


async def add_listing(listing_key: str, gift_id: str, title: str, price: Optional[int], slug: Optional[str], status="pending", owner=None):
    owner = owner or {}
    fields = ("owner_kind", "owner_id", "owner_name", "owner_username", "owner_address",
              "host_kind", "host_id", "host_name", "host_username")
    values = [owner.get(field) for field in fields]
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO listings(listing_key,gift_id,title,price,slug,status," +
            ",".join(fields) + ") VALUES(?,?,?,?,?,? ,?,?,?,?,?,?,?,?,?)",
            (listing_key, str(gift_id), title, price, slug, status, *values)
        )
        await db.commit()
        return cur.rowcount == 1


async def update_owner_metadata(listing_key: str, owner: dict):
    fields = ("owner_kind", "owner_id", "owner_name", "owner_username", "owner_address",
              "host_kind", "host_id", "host_name", "host_username")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE listings SET " + ",".join(f"{field}=COALESCE(?,{field})" for field in fields) + " WHERE listing_key=?",
            tuple(owner.get(field) for field in fields) + (listing_key,)
        )
        await db.commit()


async def set_listing_status(listing_key: str, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE listings SET status=? WHERE listing_key=?", (status, listing_key))
        await db.commit()


async def get_topic(gift_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT thread_id FROM topics WHERE gift_id=?", (str(gift_id),))
        row = await cur.fetchone()
        return row[0] if row else None


async def save_topic(gift_id: str, title: str, thread_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO topics(gift_id,title,thread_id) VALUES(?,?,?) "
            "ON CONFLICT(gift_id) DO UPDATE SET title=excluded.title, thread_id=excluded.thread_id",
            (str(gift_id), title, thread_id)
        )
        await db.commit()


async def mark_existing_as_seen(listing_key: str, gift_id: str, title: str, price: Optional[int], slug: Optional[str]):
    return await add_listing(listing_key, gift_id, title, price, slug, status="seen")

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
                status TEXT NOT NULL DEFAULT 'seen'
            )
        """)
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

async def add_listing(listing_key: str, gift_id: str, title: str, price: Optional[int], slug: Optional[str], status="pending"):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO listings(listing_key,gift_id,title,price,slug,status) VALUES(?,?,?,?,?,?)",
            (listing_key, str(gift_id), title, price, slug, status)
        )
        await db.commit()
        return cur.rowcount == 1

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

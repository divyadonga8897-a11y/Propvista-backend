"""Quick DB connectivity test."""
import asyncio
import asyncpg


async def test():
    try:
        conn = await asyncpg.connect(
            "postgresql://postgres:Divya%40120531@db.svdcrgmpqoicxlfqmxxc.supabase.co:5432/postgres",
            timeout=1,
        )
        rows = await conn.fetch("SELECT id, name FROM apartments LIMIT 5")
        print("Connected! Apartments found:", len(rows))
        for r in rows:
            print("  -", r["id"], r["name"])
        await conn.close()
    except Exception as e:
        print("ERROR:", type(e).__name__, str(e))


asyncio.run(test())

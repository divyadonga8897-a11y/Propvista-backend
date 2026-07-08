import asyncio
import os

os.environ['DATABASE_URL'] = 'postgresql+asyncpg://postgres:Divya%40120531@db.svdcrgmpqoicxlfqmxxc.supabase.co:5432/postgres'

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test_connection():
    engine = create_async_engine(os.environ['DATABASE_URL'], pool_pre_ping=True, echo=False)
    try:
        async with engine.connect() as conn:
            # Test 1: Basic connectivity
            result = await conn.execute(text("SELECT version()"))
            row = result.fetchone()
            print("SUCCESS: Connected to Supabase PostgreSQL!")
            print(f"DB Version: {row[0][:60]}...")

            # Test 2: Check tables
            q = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            result2 = await conn.execute(text(q))
            tables = [r[0] for r in result2.fetchall()]
            print(f"\nTables in DB ({len(tables)} total):")
            for t in tables:
                print(f"  - {t}")

            # Test 3: Row counts for key tables
            print("\nKey table row counts:")
            for tbl in ['apartments', 'floors', 'flats', 'users', 'bookings', 'payments']:
                if tbl in tables:
                    cnt = await conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                    print(f"  {tbl}: {cnt.scalar()} rows")
                else:
                    print(f"  {tbl}: TABLE NOT FOUND")

    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
    finally:
        await engine.dispose()

asyncio.run(test_connection())

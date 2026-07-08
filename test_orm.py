"""Test SQLAlchemy async query against Supabase."""
import asyncio
import sys
sys.path.insert(0, ".")

async def test():
    try:
        from app.database.session import AsyncSessionLocal
        from app.models.models import Apartment
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Apartment).limit(5))
            apts = result.scalars().all()
            print(f"SQLAlchemy OK — found {len(apts)} apartments")
            for a in apts:
                print(f"  - {a.id}  {a.name}")
    except Exception as e:
        import traceback
        print("ERROR:", type(e).__name__)
        traceback.print_exc()


asyncio.run(test())

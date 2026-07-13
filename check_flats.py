import asyncio
import sys
sys.path.insert(0, ".")

async def main():
    from app.database.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.models import Flat
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Flat).limit(10))
        flats = result.scalars().all()
        print("FLATS IN DATABASE:")
        for f in flats:
            print(f"ID: {f.id} | Flat Number: {f.flat_number}")

if __name__ == "__main__":
    asyncio.run(main())

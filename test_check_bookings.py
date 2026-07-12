import asyncio
import sys
sys.path.insert(0, ".")

async def test():
    try:
        from app.database.session import AsyncSessionLocal
        from app.models.models import User, Booking, Document, ResidentAccessRequest, Flat
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async with AsyncSessionLocal() as session:
            # Get user details for target users
            res = await session.execute(
                select(User).where(User.email.in_(["divyause@gmail.com", "deepikadunga6666@gmail.com"]))
            )
            users = res.scalars().all()
            print(f"Checking {len(users)} users:")
            for u in users:
                print(f"\nUser: {u.email} (ID: {u.id}) Role: {u.role}")
                
                # Get bookings
                bk_res = await session.execute(
                    select(Booking).where(Booking.user_id == u.id).options(selectinload(Booking.flat))
                )
                bookings = bk_res.scalars().all()
                print(f"  Bookings count: {len(bookings)}")
                for b in bookings:
                    print(f"    - Booking ID: {b.id} | Flat: {b.flat.flat_number if b.flat else 'None'} | Status: {b.status} | Type: {b.booking_type}")
                    
                    # Get documents for booking
                    doc_res = await session.execute(
                        select(Document).where(Document.booking_id == b.id)
                    )
                    docs = doc_res.scalars().all()
                    print(f"      Documents count: {len(docs)}")
                    for d in docs:
                        print(f"        * Doc ID: {d.id} | Type: {d.doc_type} | Name: {d.name}")
                        
                    # Get resident access requests for booking
                    req_res = await session.execute(
                        select(ResidentAccessRequest).where(ResidentAccessRequest.booking_id == b.id)
                    )
                    reqs = req_res.scalars().all()
                    print(f"      Resident Access Requests count: {len(reqs)}")
                    for r in reqs:
                        print(f"        * Request ID: {r.id} | Status: {r.status} | Remarks: {r.remarks} | Rejection: {r.rejection_reason}")
                        
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())

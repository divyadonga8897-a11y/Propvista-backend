import asyncio
import sys
import uuid
from datetime import datetime
sys.path.insert(0, ".")

async def test():
    try:
        from app.database.session import AsyncSessionLocal
        from app.models.models import Flat, User, Booking, Payment, Document, Resident, ResidentAccessRequest
        from app.services.booking_service import booking_service
        from sqlalchemy import select, delete
        from sqlalchemy.orm import joinedload
        
        async with AsyncSessionLocal() as session:
            # 1. Get or create test user
            user_uuid = uuid.uuid4()
            user = User(
                id=user_uuid,
                email=f"test_runner_{user_uuid.hex[:8]}@propvista.com",
                role="Customer",
                full_name="Test Runner User",
                phone="9999999999"
            )
            session.add(user)
            await session.commit()
            print(f"Created test user: {user.email} (ID: {user.id})")
            
            # 2. Get an available flat
            flat_res = await session.execute(select(Flat).where(Flat.status == "Available").limit(1))
            flat = flat_res.scalar_one_or_none()
            if not flat:
                # If no flat is available, set one to Available
                flat_res = await session.execute(select(Flat).limit(1))
                flat = flat_res.scalar_one_or_none()
                flat.status = "Available"
                await session.commit()
            
            print(f"Using Flat: {flat.flat_number} (ID: {flat.id})")
            
            # 3. Create a test booking
            booking = Booking(
                id=uuid.uuid4(),
                flat_id=flat.id,
                user_id=user.id,
                booking_type="BUY",
                amount_paid=0.0,
                status="Pending"
            )
            session.add(booking)
            await session.commit()
            print(f"Created booking: {booking.id}")
            
            # 4. Complete local payment and generate documents
            print("Completing local payment...")
            result = await booking_service.complete_payment_local(
                session,
                user.id,
                booking.id,
                50000.0,
                "Purchase Booking"
            )
            print("Payment completed successfully!")
            print("Result:", result)
            
            # Refresh session to see generated documents
            # Let's query documents for this booking
            doc_res = await session.execute(select(Document).where(Document.booking_id == booking.id))
            docs = doc_res.scalars().all()
            print(f"Found {len(docs)} documents generated for this booking:")
            for d in docs:
                print(f"  - [{d.doc_type}] {d.name}: {d.file_url}")
                
            # Verify required documents
            types = [d.doc_type for d in docs]
            required_types = ["Invoice", "Receipt", "Booking Confirmation", "Sale Agreement", "QR Verification Code", "Ownership Certificate"]
            for req in required_types:
                if req in types:
                    print(f"  ✓ {req} generated.")
                else:
                    print(f"  ❌ {req} MISSING!")
                    
            # 5. Clean up the database
            print("Cleaning up database...")
            # Delete resident profile
            await session.execute(delete(Resident).where(Resident.booking_id == booking.id))
            # Delete access request
            await session.execute(delete(ResidentAccessRequest).where(ResidentAccessRequest.booking_id == booking.id))
            # Delete documents
            await session.execute(delete(Document).where(Document.booking_id == booking.id))
            # Delete payments
            await session.execute(delete(Payment).where(Payment.booking_id == booking.id))
            # Delete booking
            await session.execute(delete(Booking).where(Booking.id == booking.id))
            # Delete user
            await session.execute(delete(User).where(User.id == user.id))
            # Restore flat status
            flat.status = "Available"
            await session.commit()
            print("Cleanup done!")
            
    except Exception as e:
        import traceback
        print("ERROR:", type(e).__name__)
        traceback.print_exc()

asyncio.run(test())

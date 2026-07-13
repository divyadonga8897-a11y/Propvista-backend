import asyncio
import asyncpg

async def query_bookings_docs():
    try:
        conn = await asyncpg.connect(
            "postgresql://postgres:Divya%40120531@db.svdcrgmpqoicxlfqmxxc.supabase.co:5432/postgres",
            timeout=5,
        )
        bookings = await conn.fetch("SELECT id, user_id, status, booking_type, amount_paid FROM bookings")
        print("Bookings:")
        for b in bookings:
            print(f"  - Booking ID: {b['id']} | User: {b['user_id']} | Status: {b['status']} | Type: {b['booking_type']} | Paid: {b['amount_paid']}")
            
        docs = await conn.fetch("SELECT id, booking_id, doc_type, name, file_url FROM documents")
        print("\nDocuments:")
        for d in docs:
            print(f"  - Doc ID: {d['id']} | Booking: {d['booking_id']} | Type: {d['doc_type']} | Name: {d['name']} | URL: {d['file_url']}")
            
        await conn.close()
    except Exception as e:
        print("ERROR:", type(e).__name__, str(e))

asyncio.run(query_bookings_docs())

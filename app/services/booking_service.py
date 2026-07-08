import uuid
import json
import httpx
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, update, and_, or_, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from app.models.models import (
    City, Apartment, Floor, Flat, FlatImage, Wishlist, Booking, Payment, Document, User
)
from app.core.config import settings
from app.core.exceptions import EntityNotFoundException, APIException
from app.utils.logging import logger
from app.services.supabase_storage import storage_service

class BookingService:
    # ── Hold Flat ──
    async def hold_flat(self, db: AsyncSession, user_id: uuid.UUID, flat_id: uuid.UUID) -> Booking:
        # Check flat existence
        res_flat = await db.execute(select(Flat).where(Flat.id == flat_id))
        flat = res_flat.scalar_one_or_none()
        if not flat:
            raise EntityNotFoundException("Flat", str(flat_id))

        # Check hold/double booking rules
        # Expiry cleanups are done on the fly here to prevent stale holds
        await self.release_expired_holds(db)
        await db.refresh(flat)

        if flat.status != "Available":
            raise APIException(status_code=400, detail=f"Flat {flat.flat_number} is already {flat.status}.")

        # Mark flat as Held
        flat.status = "Held"
        
        # Create hold booking record
        hold_expiry = datetime.utcnow() + timedelta(hours=24)
        booking = Booking(
            flat_id=flat_id,
            user_id=user_id,
            booking_type="HOLD",
            amount_paid=0.0,
            status="Held",
            hold_expiry=hold_expiry
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        return booking

    # ── Release Expired Holds ──
    async def release_expired_holds(self, db: AsyncSession) -> None:
        now = datetime.utcnow()
        expired_holds_query = select(Booking).where(
            and_(
                Booking.booking_type == "HOLD",
                Booking.status == "Held",
                Booking.hold_expiry < now
            )
        )
        res = await db.execute(expired_holds_query)
        expired_bookings = res.scalars().all()

        for b in expired_bookings:
            b.status = "Cancelled"
            # Return flat status to Available
            flat_res = await db.execute(select(Flat).where(Flat.id == b.flat_id))
            flat = flat_res.scalar_one_or_none()
            if flat and flat.status == "Held":
                flat.status = "Available"

        if expired_bookings:
            await db.commit()
            logger.info(f"Released {len(expired_bookings)} expired flat holds.")

    # ── Create Booking (BUY or RENT) ──
    async def create_booking(self, db: AsyncSession, user_id: uuid.UUID, flat_id: uuid.UUID, booking_type: str) -> Booking:
        await self.release_expired_holds(db)
        
        res_flat = await db.execute(select(Flat).where(Flat.id == flat_id).options(joinedload(Flat.floor).joinedload(Floor.apartment)))
        flat = res_flat.scalar_one_or_none()
        if not flat:
            raise EntityNotFoundException("Flat", str(flat_id))

        # Check availability
        # Can only book if flat is Available, OR if it's Held by the SAME customer.
        if flat.status == "Held":
            hold_res = await db.execute(
                select(Booking).where(
                    and_(
                        Booking.flat_id == flat_id,
                        Booking.status == "Held",
                        Booking.booking_type == "HOLD"
                    )
                ).order_by(desc(Booking.created_at))
            )
            active_hold = hold_res.scalars().first()
            if active_hold and active_hold.user_id != user_id:
                raise APIException(status_code=400, detail="Flat is held by another customer.")
        elif flat.status != "Available":
            raise APIException(status_code=400, detail=f"Flat {flat.flat_number} is already {flat.status}.")

        # Set flat status to Payment Pending
        flat.status = "Held" # Block it from others

        booking = Booking(
            flat_id=flat_id,
            user_id=user_id,
            booking_type=booking_type.upper(), # BUY or RENT
            amount_paid=0.0,
            status="Payment Pending"
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        return booking

    # ── Get Bookings ──
    async def get_bookings(self, db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> List[Booking]:
        await self.release_expired_holds(db)
        query = select(Booking).options(
            joinedload(Booking.flat).joinedload(Flat.images),
            joinedload(Booking.payments),
            joinedload(Booking.documents),
            joinedload(Booking.user)
        ).order_by(desc(Booking.created_at))
        if user_id:
            query = query.where(Booking.user_id == user_id)
        result = await db.execute(query)
        return list(result.scalars().unique().all())

    async def get_booking_by_id(self, db: AsyncSession, booking_id: uuid.UUID) -> Booking:
        query = select(Booking).where(Booking.id == booking_id).options(
            joinedload(Booking.flat).joinedload(Flat.images),
            joinedload(Booking.payments),
            joinedload(Booking.documents)
        )
        result = await db.execute(query)
        booking = result.scalar_one_or_none()
        if not booking:
            raise EntityNotFoundException("Booking", str(booking_id))
        return booking

    # ── Cancel Booking ──
    async def cancel_booking(self, db: AsyncSession, booking_id: uuid.UUID) -> Booking:
        booking = await self.get_booking_by_id(db, booking_id)
        booking.status = "Cancelled"
        
        flat_res = await db.execute(select(Flat).where(Flat.id == booking.flat_id))
        flat = flat_res.scalar_one_or_none()
        if flat:
            flat.status = "Available"
            
        await db.commit()
        await db.refresh(booking)
        return booking

    # ── Create Payment Order ──
    async def create_payment_order(self, db: AsyncSession, user_id: uuid.UUID, booking_id: uuid.UUID, amount: float, payment_type: str) -> Dict[str, Any]:
        booking = await self.get_booking_by_id(db, booking_id)
        
        # If Razorpay keys are configured, make actual call
        razorpay_order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
        if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            try:
                url = "https://api.razorpay.com/v1/orders"
                auth_data = (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
                payload = {
                    "amount": int(amount * 100), # Razorpay accepts amount in paise
                    "currency": "INR",
                    "receipt": str(booking_id),
                    "notes": {
                        "booking_id": str(booking_id),
                        "payment_type": payment_type
                    }
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, auth=auth_data)
                    if resp.status_code in [200, 201]:
                        razorpay_order_id = resp.json().get("id")
            except Exception as e:
                logger.error(f"Error calling Razorpay API: {e}. Falling back to mock order.")

        # Create local pending payment record
        payment = Payment(
            booking_id=booking_id,
            user_id=user_id,
            amount=amount,
            currency="INR",
            payment_type=payment_type,
            payment_status="Pending",
            razorpay_order_id=razorpay_order_id
        )
        db.add(payment)
        await db.commit()
        
        return {
            "order_id": razorpay_order_id,
            "booking_id": str(booking_id),
            "amount": amount,
            "currency": "INR",
            "razorpay_key_id": settings.RAZORPAY_KEY_ID or "rzp_test_mock_keys"
        }

    # ── Verify Payment Signature & Finalize Booking ──
    async def verify_payment(self, db: AsyncSession, order_id: str, payment_id: str, signature: str = "", bypass_signature: bool = False) -> bool:
        # Check payment record
        pay_res = await db.execute(select(Payment).where(Payment.razorpay_order_id == order_id))
        payment = pay_res.scalar_one_or_none()
        if not payment:
            raise EntityNotFoundException("Payment Order", order_id)

        # Signature verification
        verified = False
        if bypass_signature:
            verified = True
        elif settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            try:
                # Generate signature comparison string
                msg = f"{order_id}|{payment_id}"
                generated_sig = hmac.new(
                    settings.RAZORPAY_KEY_SECRET.encode(),
                    msg.encode(),
                    hashlib.sha256
                ).hexdigest()
                verified = hmac.compare_digest(generated_sig, signature)
            except Exception as e:
                logger.error(f"Signature verify exception: {e}")
        else:
            # Sandbox mock mode automatically verifies
            verified = True

        if not verified:
            payment.status = "Failed"
            await db.commit()
            return False

        # Update Payment Record
        payment.status = "Successful"
        payment.razorpay_payment_id = payment_id
        payment.payment_method = "Razorpay Checkout"
        
        # Update Booking Status
        booking = await self.get_booking_by_id(db, payment.booking_id)
        booking.amount_paid += payment.amount
        
        # Determine final flat status based on booking type
        is_buy = booking.booking_type == "BUY"
        booking.status = "Sold" if is_buy else "Rented"
        
        # Update Flat Status
        flat_res = await db.execute(select(Flat).where(Flat.id == booking.flat_id).options(joinedload(Flat.floor).joinedload(Floor.apartment)))
        flat = flat_res.scalar_one_or_none()
        if flat:
            flat.status = "Sold" if is_buy else "Rented"

        # ── Activate Resident Profile ──
        user_res = await db.execute(select(User).where(User.id == booking.user_id))
        user = user_res.scalar_one_or_none()
        if user:
            user.role = "Resident" # Upgrade User Role

        await db.commit()

        # ── Document & QR Generation ──
        if flat:
            apt_name = flat.floor.apartment.name
            flat_num = flat.flat_number
            
            # Auto-generate Invoice
            invoice_content = f"INVOICE\nPropVista AI\nCommunity: {apt_name}\nFlat No: {flat_num}\nAmount Paid: INR {payment.amount}\nDate: {datetime.utcnow().isoformat()}"
            invoice_url = await storage_service.upload_file("documents", invoice_content.encode(), f"invoice_{booking.id}.txt", "text/plain")
            doc_inv = Document(flat_id=flat.id, booking_id=booking.id, name=f"Invoice Flat {flat_num}", file_url=invoice_url, doc_type="Invoice")
            db.add(doc_inv)

            # Auto-generate Receipt
            receipt_content = f"RECEIPT\nTransaction ID: {payment_id}\nOrder ID: {order_id}\nAmount: INR {payment.amount}\nStatus: SUCCESS"
            receipt_url = await storage_service.upload_file("receipts", receipt_content.encode(), f"receipt_{booking.id}.txt", "text/plain")
            doc_rec = Document(flat_id=flat.id, booking_id=booking.id, name=f"Receipt Flat {flat_num}", file_url=receipt_url, doc_type="Receipt")
            db.add(doc_rec)

            # Sale / Rental Agreement
            agreement_type = "Sale Agreement" if is_buy else "Rental Agreement"
            agreement_content = f"AGREEMENT\nThis agreement is made between PropVista Developers and Resident for flat {flat_num} in {apt_name}."
            agreement_url = await storage_service.upload_file("agreements", agreement_content.encode(), f"agreement_{booking.id}.txt", "text/plain")
            doc_agr = Document(flat_id=flat.id, booking_id=booking.id, name=f"{agreement_type} Flat {flat_num}", file_url=agreement_url, doc_type=agreement_type)
            db.add(doc_agr)

            # Ownership Certificate (only for BUY)
            # Ownership Certificate (only for BUY)
            if is_buy:
                cert_content = f"OWNERSHIP CERTIFICATE\nThis certifies that User {booking.user_id} is the legal owner of Flat {flat_num} in {apt_name}."
                cert_url = await storage_service.upload_file("documents", cert_content.encode(), f"ownership_cert_{booking.id}.txt", "text/plain")
                doc_cert = Document(flat_id=flat.id, booking_id=booking.id, name=f"Ownership Certificate Flat {flat_num}", file_url=cert_url, doc_type="Ownership Certificate")
                db.add(doc_cert)

            # Auto-create Resident profile record
            resident = Resident(
                user_id=booking.user_id,
                apartment_id=flat.apartment_id or flat.floor.apartment_id,
                floor_id=flat.floor_id,
                flat_id=flat.id,
                booking_id=booking.id,
                resident_type="Owner" if is_buy else "Tenant",
                move_in_date=date.today(),
                status="Active",
                agreement_number=f"AGR-{booking.id.hex[:8].upper()}"
            )
            db.add(resident)
            await db.commit()

        return True

    # ── List Payments History ──
    async def get_payments(self, db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> List[Payment]:
        query = select(Payment).options(joinedload(Payment.booking)).order_by(desc(Payment.payment_date))
        if user_id:
            query = query.where(Payment.user_id == user_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    # ── List Generated Documents ──
    async def get_documents(self, db: AsyncSession, user_id: uuid.UUID) -> List[Document]:
        query = select(Document).join(Flat).join(Booking, isouter=True).where(
            or_(
                Booking.user_id == user_id,
                # Fallback check if user matches in associated relation
                Document.booking.has(Booking.user_id == user_id)
            )
        ).order_by(desc(Document.created_at))
        result = await db.execute(query)
        return list(result.scalars().all())

# Singleton
booking_service = BookingService()

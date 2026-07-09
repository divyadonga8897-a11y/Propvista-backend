import uuid
import io
import json
import httpx
import hmac
import hashlib
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from fpdf import FPDF
from sqlalchemy import select, delete, update, and_, or_, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
from app.models.models import (
    City, Apartment, Floor, Flat, FlatImage, Wishlist, Booking, Payment, Document, User, Resident
)
from app.core.config import settings
from app.core.exceptions import EntityNotFoundException, APIException
from app.utils.logging import logger
from app.services.supabase_storage import storage_service
from app.services.ai.groq_service import groq_service

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
            joinedload(Booking.documents),
            joinedload(Booking.user)
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

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise APIException(status_code=503, detail="Payment gateway is not configured. Please contact support.")

        razorpay_order_id: str
        try:
            url = "https://api.razorpay.com/v1/orders"
            auth_data = (settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            payload = {
                "amount": int(amount * 100),  # Razorpay accepts amount in paise
                "currency": "INR",
                "receipt": str(booking_id),
                "notes": {
                    "booking_id": str(booking_id),
                    "payment_type": payment_type
                }
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, auth=auth_data)
                resp.raise_for_status()
                razorpay_order_id = resp.json()["id"]
        except Exception as e:
            logger.error(f"Razorpay order creation failed: {e}")
            raise APIException(status_code=502, detail="Failed to create payment order with Razorpay. Please try again.")

        # Create local pending payment record
        payment = Payment(
            booking_id=booking_id,
            user_id=user_id,
            amount=amount,
            payment_type=payment_type,
            status="Pending",
            razorpay_order_id=razorpay_order_id
        )
        db.add(payment)
        await db.commit()

        return {
            "order_id": razorpay_order_id,
            "booking_id": str(booking_id),
            "amount": amount,
            "currency": "INR",
            "razorpay_key_id": settings.RAZORPAY_KEY_ID
        }

    # ── Verify Payment Signature & Finalize Booking ──
    async def verify_payment(self, db: AsyncSession, order_id: str, payment_id: str, signature: str) -> bool:
        # Fetch payment record by order ID
        pay_res = await db.execute(select(Payment).where(Payment.razorpay_order_id == order_id))
        payment = pay_res.scalar_one_or_none()
        if not payment:
            raise EntityNotFoundException("Payment Order", order_id)

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            raise APIException(status_code=503, detail="Payment gateway credentials not configured on server.")

        # HMAC-SHA256 signature verification (Razorpay standard)
        try:
            msg = f"{order_id}|{payment_id}"
            generated_sig = hmac.new(
                settings.RAZORPAY_KEY_SECRET.encode(),
                msg.encode(),
                hashlib.sha256
            ).hexdigest()
            verified = hmac.compare_digest(generated_sig, signature)
        except Exception as e:
            logger.error(f"Signature verification exception: {e}")
            verified = False

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
            # Disable automatic Resident role upgrade for now, handled via ResidentAccessRequest
            pass # user.role = "Resident" 

        # Create Resident Access Request automatically
        
        # ── Document & PDF Generation ──
        if flat:
            apt_name = flat.floor.apartment.name
            flat_num = flat.flat_number
            user_email = user.email if user else "N/A"
            user_name = (user.full_name if hasattr(user, 'full_name') and user.full_name else None) or user_email.split("@")[0] if user else "Customer"
            agreement_number = f"AGR-{booking.id.hex[:8].upper()}"
            payment_date_str = datetime.utcnow().strftime("%d %B %Y")

            # ── Helper: Generate a styled PDF ──
            def _make_pdf(title: str, lines: list[str]) -> bytes:
                pdf = FPDF()
                pdf.add_page()
                # Header
                pdf.set_fill_color(15, 23, 42)  # slate-900
                pdf.rect(0, 0, 210, 30, 'F')
                pdf.set_font("Helvetica", 'B', 16)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(0, 10, "PropVista AI", ln=True, align='C')
                pdf.set_font("Helvetica", '', 9)
                pdf.cell(0, 10, title, ln=True, align='C')
                pdf.set_text_color(0, 0, 0)
                pdf.ln(10)
                # Body lines
                pdf.set_font("Helvetica", '', 10)
                for line in lines:
                    if line.startswith("## "):
                        pdf.set_font("Helvetica", 'B', 11)
                        pdf.set_text_color(30, 64, 175)  # blue
                        pdf.cell(0, 8, line[3:], ln=True)
                        pdf.set_text_color(0, 0, 0)
                        pdf.set_font("Helvetica", '', 10)
                    elif line.startswith("**") and line.endswith("**"):
                        pdf.set_font("Helvetica", 'B', 10)
                        pdf.cell(0, 6, line[2:-2], ln=True)
                        pdf.set_font("Helvetica", '', 10)
                    elif line == "---":
                        pdf.set_draw_color(200, 200, 200)
                        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                        pdf.ln(3)
                    elif line.strip():
                        pdf.multi_cell(0, 6, line)
                    else:
                        pdf.ln(3)
                # Footer
                pdf.set_y(-20)
                pdf.set_font("Helvetica", 'I', 8)
                pdf.set_text_color(150, 150, 150)
                pdf.cell(0, 10, f"Generated by PropVista AI on {payment_date_str} | {agreement_number}", align='C')
                return bytes(pdf.output())

            # ── Invoice PDF ──
            invoice_lines = [
                f"## PAYMENT INVOICE",
                "---",
                f"Invoice Number: INV-{booking.id.hex[:8].upper()}",
                f"Agreement Number: {agreement_number}",
                f"Date: {payment_date_str}",
                "",
                f"## Billed To",
                f"Name: {user_name}",
                f"Email: {user_email}",
                "",
                f"## Property Details",
                f"Apartment Community: {apt_name}",
                f"Flat Number: {flat_num}",
                f"Floor: {flat.floor.floor_name or flat.floor.floor_number}",
                f"Transaction Type: {booking.booking_type}",
                "",
                f"## Payment Details",
                f"Booking ID: {booking.id}",
                f"Payment ID: {payment_id}",
                f"Order ID: {order_id}",
                f"Amount Paid: INR {payment.amount:,.2f}",
                f"Status: SUCCESSFUL",
                f"Payment Method: Demo Payment",
                "---",
                "Thank you for choosing PropVista AI.",
            ]
            invoice_bytes = _make_pdf(f"Invoice – Flat {flat_num}, {apt_name}", invoice_lines)
            invoice_url = await storage_service.upload_file("documents", invoice_bytes, f"invoice_{booking.id}.pdf", "application/pdf")
            db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"Invoice – Flat {flat_num}", file_url=invoice_url, doc_type="Invoice"))

            # ── Receipt PDF ──
            receipt_lines = [
                f"## PAYMENT RECEIPT",
                "---",
                f"Receipt Number: RCP-{booking.id.hex[:8].upper()}",
                f"Date: {payment_date_str}",
                "",
                f"Customer: {user_name} ({user_email})",
                f"Property: Flat {flat_num}, {apt_name}",
                f"Booking ID: {booking.id}",
                f"Payment ID: {payment_id}",
                f"Order ID: {order_id}",
                f"Amount Received: INR {payment.amount:,.2f}",
                f"Payment Status: PAID",
                "---",
                "This is a computer-generated receipt. No signature required.",
            ]
            receipt_bytes = _make_pdf(f"Receipt – Flat {flat_num}, {apt_name}", receipt_lines)
            receipt_url = await storage_service.upload_file("receipts", receipt_bytes, f"receipt_{booking.id}.pdf", "application/pdf")
            db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"Receipt – Flat {flat_num}", file_url=receipt_url, doc_type="Receipt"))

            # ── Legal Agreement (AI + Default Fallback) ──
            agreement_type = "Sale Agreement" if is_buy else "Rental Agreement"
            try:
                prompt = (
                    f"Generate a formal {agreement_type} for real estate. "
                    f"Agreement Number: {agreement_number}. "
                    f"Parties: PropVista Developers (Developer) and {user_name} (Customer, email: {user_email}). "
                    f"Property: Flat {flat_num}, {apt_name}. "
                    f"Amount: INR {payment.amount:,.2f}. "
                    f"Booking ID: {booking.id}. Payment ID: {payment_id}. Date: {payment_date_str}. "
                    f"Include: Agreement Number, Parties, Property Details, Consideration, Payment Terms, "
                    f"Covenants, Default clause, Governing Law (India), Dispute Resolution, "
                    f"Signature Section for both parties. Format with clear section headers using ##."
                )
                messages = [
                    {"role": "system", "content": "You are a professional real estate legal document generator for India. Return only the formal agreement text with ## section headers."},
                    {"role": "user", "content": prompt}
                ]
                groq_response = await groq_service.get_chat_completion(messages=messages, temperature=0.2)
                agreement_text = groq_response.get("reply", "")
            except Exception as e:
                logger.error(f"Groq failed, using default agreement template: {e}")
                agreement_text = ""

            if not agreement_text or len(agreement_text) < 200:
                # Robust default template
                agreement_text = (
                    f"## {agreement_type.upper()}\n"
                    f"Agreement Number: {agreement_number}\n\n"
                    f"## PARTIES\n"
                    f"Developer: PropVista Developers Pvt. Ltd., registered under the Companies Act, India.\n"
                    f"Customer: {user_name} (Email: {user_email})\n\n"
                    f"## PROPERTY DETAILS\n"
                    f"Apartment Community: {apt_name}\n"
                    f"Flat Number: {flat_num}\n"
                    f"Type: {booking.booking_type}\n\n"
                    f"## CONSIDERATION\n"
                    f"The Customer agrees to pay INR {payment.amount:,.2f} as the {'purchase price' if is_buy else 'rental deposit'}.\n"
                    f"Booking ID: {booking.id}\nPayment ID: {payment_id}\nDate: {payment_date_str}\n\n"
                    f"## TERMS & CONDITIONS\n"
                    f"1. The property is transferred to the Customer as described above.\n"
                    f"2. The Customer shall comply with all society rules and regulations.\n"
                    f"3. This agreement is governed by the laws of India.\n"
                    f"4. Any disputes shall be resolved through arbitration in the jurisdiction of the property.\n"
                    f"5. This agreement constitutes the entire understanding between the parties.\n\n"
                    f"## SIGNATURES\n"
                    f"Developer: PropVista Developers Pvt. Ltd.\n"
                    f"Signature: ___________________________  Date: {payment_date_str}\n\n"
                    f"Customer: {user_name}\n"
                    f"Signature: ___________________________  Date: {payment_date_str}\n"
                )

            agreement_lines = []
            for line in agreement_text.split("\n"):
                agreement_lines.append(line)

            agreement_bytes = _make_pdf(f"{agreement_type} – Flat {flat_num}, {apt_name}", agreement_lines)
            agreement_url = await storage_service.upload_file("agreements", agreement_bytes, f"agreement_{booking.id}.pdf", "application/pdf")
            doc_agr = Document(flat_id=flat.id, booking_id=booking.id, name=f"{agreement_type} – Flat {flat_num}", file_url=agreement_url, doc_type=agreement_type)
            db.add(doc_agr)
            await db.flush()  # get doc_agr.id

            # ── Ownership Certificate (BUY only) ──
            if is_buy:
                cert_lines = [
                    f"## OWNERSHIP CERTIFICATE",
                    "---",
                    f"Certificate No: OWN-{booking.id.hex[:8].upper()}",
                    f"Date: {payment_date_str}",
                    "",
                    f"This is to certify that {user_name} ({user_email}) is the legal owner of:",
                    "",
                    f"Flat No: {flat_num}",
                    f"Apartment Community: {apt_name}",
                    f"Booking ID: {booking.id}",
                    f"Agreement Number: {agreement_number}",
                    "",
                    "Issued by PropVista AI – Official Property Management Platform.",
                    "---",
                    "PropVista Developers Pvt. Ltd.",
                    "Authorised Signatory: _______________________",
                ]
                cert_bytes = _make_pdf(f"Ownership Certificate – Flat {flat_num}", cert_lines)
                cert_url = await storage_service.upload_file("documents", cert_bytes, f"ownership_cert_{booking.id}.pdf", "application/pdf")
                db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"Ownership Certificate – Flat {flat_num}", file_url=cert_url, doc_type="Ownership Certificate"))

            # ── Resident Access Request (auto-created after payment) ──
            from app.models.models import ResidentAccessRequest
            # Avoid duplicates
            dup_res = await db.execute(
                select(ResidentAccessRequest).where(
                    ResidentAccessRequest.customer_id == booking.user_id,
                    ResidentAccessRequest.booking_id == booking.id,
                )
            )
            if not dup_res.scalar_one_or_none():
                access_request = ResidentAccessRequest(
                    customer_id=booking.user_id,
                    booking_id=booking.id,
                    flat_id=booking.flat_id,
                    document_id=doc_agr.id,
                    status="Pending"
                )
                db.add(access_request)

            # ── Resident Profile ──
            resident = Resident(
                user_id=booking.user_id,
                apartment_id=flat.apartment_id or flat.floor.apartment_id,
                floor_id=flat.floor_id,
                flat_id=flat.id,
                booking_id=booking.id,
                resident_type="Owner" if is_buy else "Tenant",
                move_in_date=date.today(),
                status="Active",
                agreement_number=agreement_number
            )
            db.add(resident)
            await db.commit()

            # ── Notify all Admin users about new booking ──
            try:
                from app.models.models import Notification
                admin_res = await db.execute(
                    select(User).where(User.role == "Admin")
                )
                admin_users = admin_res.scalars().all()
                for admin in admin_users:
                    notif = Notification(
                        user_id=admin.id,
                        title="New Booking Completed",
                        message=(
                            f"A new {'purchase' if is_buy else 'rental'} booking has been confirmed for "
                            f"Flat {flat_num}, {apt_name}. "
                            f"Customer: {user_name} ({user_email}). "
                            f"Amount: INR {payment.amount:,.2f}. "
                            f"Booking ID: {booking.id}. Resident Access Request is pending your approval."
                        )
                    )
                    db.add(notif)
                await db.commit()
                logger.info(f"Admin notification sent for booking {booking.id}")
            except Exception as notify_err:
                logger.warning(f"Admin notification failed (non-critical): {notify_err}")

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

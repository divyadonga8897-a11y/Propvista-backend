import uuid
import io
import json
import httpx
import hmac
import hashlib
import asyncio
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

# Reusable HTTP client to prevent connection overhead and TCP port exhaustion
_http_client = httpx.AsyncClient(timeout=10.0)

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

        if expired_bookings:
            flat_ids = [b.flat_id for b in expired_bookings]
            flats_res = await db.execute(select(Flat).where(Flat.id.in_(flat_ids)))
            flats_map = {f.id: f for f in flats_res.scalars().all()}
            for b in expired_bookings:
                b.status = "Cancelled"
                flat = flats_map.get(b.flat_id)
                if flat and flat.status == "Held":
                    flat.status = "Available"

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
        booking = result.unique().scalar_one_or_none()
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

    # ── Complete Local Payment ──
    async def complete_payment_local(self, db: AsyncSession, user_id: uuid.UUID, booking_id: uuid.UUID, amount: float, payment_type: str) -> Dict[str, Any]:
        from fastapi import HTTPException
        try:
            booking = await self.get_booking_by_id(db, booking_id)
            if not booking:
                raise EntityNotFoundException("Booking", str(booking_id))

            flat_res = await db.execute(
                select(Flat)
                .where(Flat.id == booking.flat_id)
                .options(joinedload(Flat.floor).joinedload(Floor.apartment))
            )
            flat = flat_res.scalar_one_or_none()
            if not flat:
                raise EntityNotFoundException("Flat", str(booking.flat_id))

            if flat.status == "SOLD":
                raise APIException(status_code=400, detail="This flat has already been purchased.")

            # Update statuses
            from decimal import Decimal
            booking.status = "Completed"
            booking.amount_paid += Decimal(str(amount))
            flat.status = "SOLD" if booking.booking_type == "BUY" else "RENTED"

            payment_id = f"PAY-{uuid.uuid4().hex[:12].upper()}"
            tx_ref = f"TXN-{uuid.uuid4().hex[:14].upper()}"
            order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
            
            payment = Payment(
                booking_id=booking_id,
                user_id=user_id,
                amount=Decimal(str(amount)),
                payment_type=payment_type,
                status="Success",
                payment_method="Local Payment",
                razorpay_order_id=order_id,
                razorpay_payment_id=payment_id,
                transaction_id=tx_ref
            )
            db.add(payment)
            await db.flush()

            user_res = await db.execute(select(User).where(User.id == booking.user_id))
            user = user_res.scalar_one_or_none()
            user_email = user.email if user else "N/A"
            user_name = (user.full_name if (user and user.full_name) else None) or user_email.split("@")[0] if user else "Customer"
            user_phone = user.phone if (user and hasattr(user, 'phone') and user.phone) else "N/A"

            apt_name = flat.floor.apartment.name
            flat_num = flat.flat_number
            agreement_number = f"AGR-{booking.id.hex[:8].upper()}"
            
            now = datetime.utcnow()
            payment_date_str = now.strftime("%d %B %Y")
            payment_time_str = now.strftime("%H:%M:%S UTC")
            generated_ts = now.strftime("%Y-%m-%d %H:%M:%S UTC")

            # Fetch QR Code bytes from free QR code generator API
            qr_bytes = None
            try:
                qr_resp = await _http_client.get(
                    f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=Booking:{booking.id}",
                    timeout=5.0
                )
                if qr_resp.status_code == 200:
                    qr_bytes = qr_resp.content
            except Exception as qr_err:
                logger.warning(f"Could not retrieve QR code from API: {qr_err}")

            # Save QR bytes to a temporary file
            import tempfile
            import os
            qr_temp_path = None
            if qr_bytes:
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_qr:
                        temp_qr.write(qr_bytes)
                        qr_temp_path = temp_qr.name
                except Exception as temp_err:
                    logger.error(f"Failed to create temp QR file: {temp_err}")

            # Define professional PDF generator function
            def _make_professional_pdf(title: str, doc_specific_lines: list[str]) -> bytes:
                pdf = FPDF()
                pdf.add_page()
                
                # 1. Header Banner
                pdf.set_fill_color(15, 23, 42) # Slate 900
                pdf.rect(0, 0, 210, 40, 'F')
                
                # Logo text
                pdf.set_font("Helvetica", 'B', 22)
                pdf.set_text_color(255, 255, 255)
                pdf.text(15, 22, "PropVista AI")
                
                # Subtitle
                pdf.set_font("Helvetica", 'I', 8)
                pdf.set_text_color(147, 197, 253) # blue-300
                pdf.text(15, 30, "Intelligent Real Estate & Society Hub")
                
                # Document Title inside header
                pdf.set_font("Helvetica", 'B', 14)
                pdf.set_text_color(255, 255, 255)
                pdf.text(110, 22, title.upper())
                
                # 2. Add QR Code on the top right
                if qr_temp_path:
                    pdf.image(qr_temp_path, x=160, y=48, w=35, h=35)
                else:
                    # Draw a nice placeholder border
                    pdf.set_draw_color(148, 163, 184) # Slate 400
                    pdf.rect(160, 48, 35, 35)
                    pdf.set_font("Helvetica", 'I', 7)
                    pdf.text(168, 66, "QR Code")
                    
                # 3. Metadata fields (Left side)
                pdf.set_y(48)
                pdf.set_left_margin(15)
                
                pdf.set_font("Helvetica", 'B', 11)
                pdf.set_text_color(30, 41, 59) # Slate 800
                pdf.cell(135, 8, "REGISTRY METADATA", ln=True)
                pdf.set_draw_color(226, 232, 240) # Slate 200
                pdf.line(15, pdf.get_y(), 150, pdf.get_y())
                pdf.ln(2)
                
                # Helper to draw grid rows
                def draw_row(label, val):
                    pdf.set_font("Helvetica", 'B', 8)
                    pdf.set_text_color(100, 116, 139) # Slate 500
                    pdf.cell(40, 5.5, label + ":", ln=False)
                    pdf.set_font("Helvetica", '', 8)
                    pdf.set_text_color(15, 23, 42) # Slate 900
                    pdf.cell(95, 5.5, str(val), ln=True)
                    
                draw_row("Booking ID", str(booking.id))
                draw_row("Customer Name", user_name)
                draw_row("Customer Email", user_email)
                draw_row("Apartment Name", apt_name)
                draw_row("Floor & Flat", f"Floor {flat.floor.floor_number} - Flat {flat_num}")
                draw_row("Flat Type", flat.flat_type)
                draw_row("Booking Type", booking.booking_type)
                draw_row("Booking Date", payment_date_str)
                draw_row("Amount Paid", f"INR {amount:,.2f}")
                draw_row("Payment Status", "SUCCESSFUL")
                draw_row("Property Status", "SOLD" if booking.booking_type == "BUY" else "RENTED")
                draw_row("Resident Type", "Owner" if booking.booking_type == "BUY" else "Tenant")
                
                pdf.ln(10)
                pdf.set_y(125)
                
                # 4. Document-Specific Content
                pdf.set_font("Helvetica", 'B', 12)
                pdf.set_text_color(30, 64, 175) # Blue 800
                pdf.cell(0, 8, "DOCUMENT TERMS & AGREEMENTS", ln=True)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(4)
                
                pdf.set_font("Helvetica", '', 9.5)
                pdf.set_text_color(51, 65, 85) # Slate 700
                for line in doc_specific_lines:
                    if line.startswith("## "):
                        pdf.set_font("Helvetica", 'B', 11)
                        pdf.set_text_color(30, 64, 175)
                        pdf.cell(0, 8, line[3:], ln=True)
                        pdf.set_font("Helvetica", '', 9.5)
                        pdf.set_text_color(51, 65, 85)
                    elif line.startswith("**") and line.endswith("**"):
                        pdf.set_font("Helvetica", 'B', 9.5)
                        pdf.cell(0, 6, line[2:-2], ln=True)
                        pdf.set_font("Helvetica", '', 9.5)
                    elif line == "---":
                        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                        pdf.ln(3)
                    elif line.strip():
                        pdf.multi_cell(180, 5.5, line)
                    else:
                        pdf.ln(2)
                        
                # 5. Footer
                pdf.set_y(-25)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(2)
                pdf.set_font("Helvetica", 'I', 8)
                pdf.set_text_color(148, 163, 184) # Slate 400
                pdf.cell(0, 6, f"PropVista AI Developers Pvt. Ltd. | Official Security Verification Code: {agreement_number}", align='C', ln=True)
                pdf.cell(0, 4, "This is an electronically generated legal document secured with QR cryptography.", align='C')
                
                return bytes(pdf.output())

            try:
                # 1. Generate Invoice PDF
                invoice_lines = [
                    "## TAX INVOICE",
                    f"Invoice Number: INV-{booking.id.hex[:8].upper()}",
                    f"Agreement Number: {agreement_number}",
                    "",
                    "## BILLED TO",
                    f"Customer Name: {user_name}",
                    f"Customer Email: {user_email}",
                    f"Customer Phone: {user_phone}",
                    "",
                    "## DESCRIPTION OF SERVICES / ACQUISITION",
                    "Flat Acquisition Booking - " + booking.booking_type,
                    f"Community: {apt_name} | Flat No: {flat_num} | Floor: Floor {flat.floor.floor_number}",
                    f"Base Price / Deposit: INR {amount:,.2f}",
                    "Taxes & GST (18% / 5% included): Inclusive",
                    f"Total Amount Due: INR {amount:,.2f}",
                    f"Total Amount Paid: INR {amount:,.2f}",
                    "Balance Due: INR 0.00",
                    "",
                    "Thank you for choosing PropVista AI.",
                ]
                invoice_bytes = _make_professional_pdf(f"Invoice - Flat {flat_num}", invoice_lines)

                # 2. Generate Receipt PDF
                receipt_lines = [
                    "## PAYMENT RECEIPT",
                    f"Receipt Number: RCP-{booking.id.hex[:8].upper()}",
                    f"Transaction Reference: {tx_ref}",
                    f"Razorpay Order ID: {order_id}",
                    f"Razorpay Payment ID: {payment_id}",
                    "",
                    "## PAYMENT SUMMARY",
                    f"Billed To: {user_name} ({user_email})",
                    f"Amount Paid: INR {amount:,.2f}",
                    f"Payment Status: SUCCESSFUL",
                    f"Payment Date: {payment_date_str} at {payment_time_str}",
                    "",
                    "Thank you for your payment. This receipt confirms the successful transfer of funds.",
                ]
                receipt_bytes = _make_professional_pdf(f"Receipt - Flat {flat_num}", receipt_lines)

                # 3. Generate Booking Confirmation
                confirmation_lines = [
                    "## CONGRATULATIONS!",
                    "We are pleased to confirm that your booking for Flat " + flat_num + " at " + apt_name + " is successfully confirmed.",
                    "PropVista AI has registered this transaction in the official land registry database.",
                    "",
                    "## NEXT STEPS",
                    "1. Your resident access request has been sent to the society administrator.",
                    "2. Once approved, your account will be upgraded to 'Resident'.",
                    "3. You will gain access to society management features including Maintenance Payments, visitor passes, and facility bookings.",
                    "",
                    "Please retain this document for your records.",
                ]
                confirmation_bytes = _make_professional_pdf(f"Booking Confirmation - Flat {flat_num}", confirmation_lines)

                # 4. Generate Agreement PDF
                agreement_type = "Sale Agreement" if booking.booking_type == "BUY" else "Rental Agreement"
                agreement_lines = [
                    f"## {agreement_type.upper()}",
                    f"Agreement ID: {agreement_number}",
                    "",
                    "## PARTIES",
                    "DEVELOPER: PropVista Developers Pvt. Ltd., registered under the Companies Act, India.",
                    f"CUSTOMER: {user_name} (Email: {user_email}, Phone: {user_phone})",
                    "",
                    "## TERMS OF AGREEMENT",
                    f"1. The Developer hereby agrees to sell/lease and the Customer agrees to purchase/rent the Flat Number {flat_num} located on the Floor {flat.floor.floor_number} of the {apt_name} community.",
                    f"2. The total consideration amount is INR {amount:,.2f}, which has been paid in full via digital transaction {tx_ref}.",
                    "3. The Customer agrees to follow all society rules and guidelines set forth by the PropVista management board.",
                    "4. Any modifications, lease transfers, or ownership disputes will be governed by the laws of Andhra Pradesh, India.",
                    "",
                    "## SIGNATURES",
                    "PropVista Developers Pvt. Ltd. (Authorised Signatory)",
                    "Signature: ___________________________",
                    "",
                    f"Customer: {user_name}",
                    "Signature: ___________________________",
                ]
                agreement_bytes = _make_professional_pdf(f"{agreement_type} - Flat {flat_num}", agreement_lines)

                # 5. Generate Ownership Certificate PDF (BUY only)
                cert_bytes = None
                if booking.booking_type == "BUY":
                    cert_lines = [
                        "## TITLE DEED & OWNERSHIP CERTIFICATE",
                        f"Certificate Number: CERT-{booking.id.hex[:8].upper()}",
                        "",
                        "This is to officially certify that:",
                        f"CUSTOMER: {user_name} ({user_email})",
                        "is registered as the absolute legal owner of the property specified below:",
                        "",
                        "## PROPERTY SPECIFICATION",
                        f"Community: {apt_name}",
                        f"Flat Number: {flat_num}",
                        f"Floor Level: Floor {flat.floor.floor_number}",
                        f"Super Built-up Area: {flat.area_sqft} sqft",
                        "",
                        f"Registered under Booking ID: {booking.id} and Agreement Number: {agreement_number}.",
                        "This certificate is signed under the seal of PropVista Developers Pvt. Ltd.",
                        "",
                        "Authorised Seal & Signatory",
                        "PropVista Developers Pvt. Ltd.",
                        "Signature: ___________________________",
                    ]
                    cert_bytes = _make_professional_pdf(f"Ownership Certificate - Flat {flat_num}", cert_lines)

                # 6. Generate QR Verification Code Document
                qr_doc_lines = [
                    "## DIGITAL VERIFICATION REPORT",
                    "This is the official cryptographic verification certificate for your real estate acquisition.",
                    "Scan the QR code printed on the top right of this page using any mobile camera or scanner to verify the authenticity of this booking.",
                    "",
                    "## CRYPTOGRAPHIC METADATA",
                    f"Blockchain Ledger ID: {booking.id}",
                    f"Transaction Hash: {tx_ref}",
                    f"Authority Registry ID: {agreement_number}",
                    f"Registered Timestamp: {generated_ts}",
                    "",
                    "If scanned, this QR code will resolve directly to our secure cloud document registry to verify that this property booking is authentic and fully paid.",
                ]
                qr_doc_bytes = _make_professional_pdf(f"QR Verification Code - Flat {flat_num}", qr_doc_lines)

                # Create concurrent upload tasks
                upload_tasks = [
                    storage_service.upload_file("documents", invoice_bytes, f"invoice_{booking.id}.pdf", "application/pdf"),
                    storage_service.upload_file("documents", receipt_bytes, f"receipt_{booking.id}.pdf", "application/pdf"),
                    storage_service.upload_file("documents", confirmation_bytes, f"booking_confirmation_{booking.id}.pdf", "application/pdf"),
                    storage_service.upload_file("documents", agreement_bytes, f"agreement_{booking.id}.pdf", "application/pdf")
                ]
                
                if booking.booking_type == "BUY" and cert_bytes:
                    upload_tasks.append(
                        storage_service.upload_file("documents", cert_bytes, f"ownership_cert_{booking.id}.pdf", "application/pdf")
                    )
                
                upload_tasks.append(
                    storage_service.upload_file("documents", qr_doc_bytes, f"qr_verification_{booking.id}.pdf", "application/pdf")
                )

                # Execute all uploads in parallel
                urls = await asyncio.gather(*upload_tasks)

                invoice_url = urls[0]
                receipt_url = urls[1]
                confirmation_url = urls[2]
                agreement_url = urls[3]

                db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"Invoice - Flat {flat_num}", file_url=invoice_url, doc_type="Invoice"))
                db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"Receipt - Flat {flat_num}", file_url=receipt_url, doc_type="Receipt"))
                db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"Booking Confirmation - Flat {flat_num}", file_url=confirmation_url, doc_type="Booking Confirmation"))
                
                doc_agr = Document(flat_id=flat.id, booking_id=booking.id, name=f"{agreement_type} - Flat {flat_num}", file_url=agreement_url, doc_type=agreement_type)
                db.add(doc_agr)
                await db.flush()

                idx = 4
                if booking.booking_type == "BUY":
                    cert_url = urls[idx]
                    db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"Ownership Certificate - Flat {flat_num}", file_url=cert_url, doc_type="Ownership Certificate"))
                    idx += 1

                qr_doc_url = urls[idx]
                db.add(Document(flat_id=flat.id, booking_id=booking.id, name=f"QR Verification Code - Flat {flat_num}", file_url=qr_doc_url, doc_type="QR Verification Code"))

            finally:
                # Clean up temporary QR code file
                if qr_temp_path and os.path.exists(qr_temp_path):
                    try:
                        os.remove(qr_temp_path)
                    except Exception:
                        pass

            # Create Resident Access Request
            from app.models.models import ResidentAccessRequest
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

            # Create Resident Profile
            resident = Resident(
                user_id=booking.user_id,
                apartment_id=flat.apartment_id or flat.floor.apartment_id,
                floor_id=flat.floor_id,
                flat_id=flat.id,
                booking_id=booking.id,
                resident_type="Owner" if booking.booking_type == "BUY" else "Tenant",
                move_in_date=date.today(),
                status="Active",
                agreement_number=agreement_number
            )
            db.add(resident)
            
            # Commit the transaction
            await db.commit()

        except Exception as err:
            await db.rollback()
            logger.error(f"Error in complete_payment_local transaction: {err}")
            raise HTTPException(
                status_code=500,
                detail="Unable to generate your booking documents. Please contact the administrator."
            )

        # Notify Admin
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
                        f"A new {'purchase' if booking.booking_type == 'BUY' else 'rental'} booking has been confirmed for "
                        f"Flat {flat_num}, {apt_name}. "
                        f"Customer: {user_name} ({user_email}). "
                        f"Amount: INR {amount:,.2f}. "
                        f"Booking ID: {booking.id}. Resident Access Request is pending your approval."
                    )
                )
                db.add(notif)
            await db.commit()
        except Exception as notify_err:
            logger.warning(f"Admin notification failed (non-critical): {notify_err}")

        return {
            "status": "success",
            "payment_id": payment_id,
            "booking_id": str(booking_id),
            "amount": amount,
            "transaction_reference": tx_ref
        }

    # ── List Payments History ──
    async def get_payments(self, db: AsyncSession, user_id: Optional[uuid.UUID] = None) -> List[Payment]:
        query = select(Payment).options(joinedload(Payment.booking)).order_by(desc(Payment.payment_date))
        if user_id:
            query = query.where(Payment.user_id == user_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    # ── List Generated Documents ──
    async def get_documents(self, db: AsyncSession, user_id: uuid.UUID) -> List[Document]:
        query = select(Document).options(
            joinedload(Document.flat).joinedload(Flat.floor).joinedload(Floor.apartment),
            joinedload(Document.booking)
        ).join(Flat).join(Booking, isouter=True).where(
            or_(
                Booking.user_id == user_id,
                # Fallback check if user matches in associated relation
                Document.booking.has(Booking.user_id == user_id)
            )
        ).order_by(desc(Document.created_at))
        result = await db.execute(query)
        docs = list(result.scalars().all())
        for doc in docs:
            doc.apartment_name = doc.flat.floor.apartment.name if (doc.flat and doc.flat.floor and doc.flat.floor.apartment) else "N/A"
            doc.floor_name = doc.flat.floor.floor_name or f"Floor {doc.flat.floor.floor_number}" if (doc.flat and doc.flat.floor) else "N/A"
            doc.flat_number = doc.flat.flat_number if doc.flat else "N/A"
            doc.booking_type = doc.booking.booking_type if doc.booking else "N/A"
            doc.status = doc.booking.status if doc.booking else "Completed"
        return docs

# Singleton
booking_service = BookingService()

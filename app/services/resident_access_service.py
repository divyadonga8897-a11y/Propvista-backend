import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import ResidentAccessRequest, User, Resident, Booking
from app.core.exceptions import EntityNotFoundException, APIException

class ResidentAccessService:
    async def create_request(
        self, db: AsyncSession, user_id: uuid.UUID, booking_id: uuid.UUID, flat_id: uuid.UUID, document_id: Optional[uuid.UUID] = None
    ) -> ResidentAccessRequest:
        # Check if booking belongs to user
        booking_res = await db.execute(select(Booking).where(Booking.id == booking_id, Booking.user_id == user_id))
        booking = booking_res.scalar_one_or_none()
        if not booking:
            raise EntityNotFoundException("Booking", str(booking_id))
            
        # Check if there is an existing pending request
        existing_res = await db.execute(
            select(ResidentAccessRequest)
            .where(
                ResidentAccessRequest.customer_id == user_id,
                ResidentAccessRequest.booking_id == booking_id,
                ResidentAccessRequest.status == "Pending"
            )
        )
        if existing_res.scalar_one_or_none():
            raise APIException(status_code=400, detail="A pending resident access request already exists for this booking.")

        new_req = ResidentAccessRequest(
            customer_id=user_id,
            booking_id=booking_id,
            flat_id=flat_id,
            document_id=document_id,
            status="Pending"
        )
        db.add(new_req)
        await db.commit()
        await db.refresh(new_req)
        return new_req

    async def get_my_requests(self, db: AsyncSession, user_id: uuid.UUID) -> List[ResidentAccessRequest]:
        result = await db.execute(
            select(ResidentAccessRequest)
            .where(ResidentAccessRequest.customer_id == user_id)
            .options(
                selectinload(ResidentAccessRequest.flat),
                selectinload(ResidentAccessRequest.document)
            )
        )
        return list(result.scalars().all())

    async def get_pending_requests(self, db: AsyncSession) -> List[ResidentAccessRequest]:
        result = await db.execute(
            select(ResidentAccessRequest)
            .where(ResidentAccessRequest.status == "Pending")
            .options(
                selectinload(ResidentAccessRequest.customer),
                selectinload(ResidentAccessRequest.flat),
                selectinload(ResidentAccessRequest.document),
                selectinload(ResidentAccessRequest.booking).selectinload(Booking.payments)
            )
        )
        return list(result.scalars().all())

    async def get_all_requests(self, db: AsyncSession) -> List[ResidentAccessRequest]:
        result = await db.execute(
            select(ResidentAccessRequest)
            .order_by(ResidentAccessRequest.created_at.desc())
            .options(
                selectinload(ResidentAccessRequest.customer),
                selectinload(ResidentAccessRequest.flat),
                selectinload(ResidentAccessRequest.document),
                selectinload(ResidentAccessRequest.booking).selectinload(Booking.payments)
            )
        )
        return list(result.scalars().all())

    async def approve_request(self, db: AsyncSession, request_id: uuid.UUID, remarks: Optional[str] = None) -> ResidentAccessRequest:
        res = await db.execute(select(ResidentAccessRequest).where(ResidentAccessRequest.id == request_id).options(selectinload(ResidentAccessRequest.booking)))
        req = res.scalar_one_or_none()
        if not req:
            raise EntityNotFoundException("ResidentAccessRequest", str(request_id))
        
        if req.status != "Pending":
            raise APIException(status_code=400, detail=f"Request is already {req.status}")
 
        req.status = "Approved"
        req.remarks = remarks
        
        # Update booking status to Approved
        if req.booking:
            req.booking.status = "Approved"
        
        # Upgrade user role
        user_res = await db.execute(select(User).where(User.id == req.customer_id))
        user = user_res.scalar_one_or_none()
        if user:
            user.role = "Resident"
            
        # Get floor_id and apartment_id from flat
        from app.models.models import Flat, Notification
        flat_res = await db.execute(select(Flat).where(Flat.id == req.flat_id).options(selectinload(Flat.floor)))
        flat = flat_res.scalar_one_or_none()
        if flat:
            # Create Resident profile
            resident = Resident(
                user_id=req.customer_id,
                apartment_id=flat.apartment_id or flat.floor.apartment_id,
                floor_id=flat.floor_id,
                flat_id=req.flat_id,
                booking_id=req.booking_id,
                resident_type="Owner" if req.booking.booking_type == "BUY" else "Tenant",
                status="Active"
            )
            db.add(resident)
 
            # Create Notification
            notification = Notification(
                user_id=req.customer_id,
                title="Resident Access Approved",
                message=f"Your resident access request for Flat {flat.flat_number} has been approved and your resident account has been activated."
            )
            db.add(notification)
 
        await db.commit()
        await db.refresh(req)
        return req

    async def reject_request(self, db: AsyncSession, request_id: uuid.UUID, remarks: str) -> ResidentAccessRequest:
        res = await db.execute(select(ResidentAccessRequest).where(ResidentAccessRequest.id == request_id))
        req = res.scalar_one_or_none()
        if not req:
            raise EntityNotFoundException("ResidentAccessRequest", str(request_id))
            
        if req.status != "Pending":
            raise APIException(status_code=400, detail=f"Request is already {req.status}")

        req.status = "Rejected"
        req.remarks = remarks

        # Create Notification
        from app.models.models import Notification
        notification = Notification(
            user_id=req.customer_id,
            title="Resident Access Rejected",
            message=f"Your resident access request has been rejected. Reason: {remarks}"
        )
        db.add(notification)

        await db.commit()
        await db.refresh(req)
        return req

resident_access_service = ResidentAccessService()

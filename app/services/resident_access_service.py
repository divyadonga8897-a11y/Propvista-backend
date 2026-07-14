import uuid
import httpx
from typing import List, Optional, Any, Union
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.models.models import ResidentAccessRequest, User, Resident, Booking, Flat, Floor
from app.core.exceptions import EntityNotFoundException, APIException
from app.core.config import settings
from app.utils.logging import logger

async def update_supabase_user_role(user_id: str, role: str):
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning("Supabase URL or Service Role Key not set. Cannot update Supabase user role.")
        return
    
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/admin/users/{user_id}"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "user_metadata": {
            "role": role
        },
        "app_metadata": {
            "role": role
        }
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=payload, headers=headers, timeout=15.0)
            if response.status_code != 200:
                logger.error(f"Failed to update user role in Supabase auth: {response.status_code} - {response.text}")
            else:
                logger.info(f"Successfully updated user role in Supabase auth to {role} for user {user_id}")
    except Exception as e:
        logger.error(f"Error calling Supabase auth to update user role: {e}")

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

        # Eagerly look up the booking PDF if not provided
        if not document_id:
            from app.models.models import Document
            doc_res = await db.execute(
                select(Document).where(
                    Document.booking_id == booking_id,
                    Document.doc_type.in_(["Sale Agreement", "Rental Agreement"])
                )
            )
            document = doc_res.scalar_one_or_none()
            if document:
                document_id = document.id

        new_req = ResidentAccessRequest(
            customer_id=user_id,
            booking_id=booking_id,
            flat_id=flat_id,
            document_id=document_id,
            status="Pending"
        )
        db.add(new_req)
        await db.commit()

        # Eagerly load the relations for the response to prevent N+1 query overhead
        res = await db.execute(
            select(ResidentAccessRequest)
            .where(ResidentAccessRequest.id == new_req.id)
            .options(
                selectinload(ResidentAccessRequest.customer),
                selectinload(ResidentAccessRequest.flat).selectinload(Flat.floor).selectinload(Floor.apartment),
                selectinload(ResidentAccessRequest.document),
                selectinload(ResidentAccessRequest.booking).selectinload(Booking.payments)
            )
        )
        return res.scalar_one()

    async def get_my_requests(self, db: AsyncSession, user_id: uuid.UUID) -> List[ResidentAccessRequest]:
        result = await db.execute(
            select(ResidentAccessRequest)
            .where(ResidentAccessRequest.customer_id == user_id)
            .options(
                selectinload(ResidentAccessRequest.customer),
                selectinload(ResidentAccessRequest.flat).selectinload(Flat.floor).selectinload(Floor.apartment),
                selectinload(ResidentAccessRequest.document),
                selectinload(ResidentAccessRequest.booking).selectinload(Booking.payments)
            )
        )
        return list(result.scalars().all())

    async def get_pending_requests(self, db: AsyncSession) -> List[ResidentAccessRequest]:
        result = await db.execute(
            select(ResidentAccessRequest)
            .where(ResidentAccessRequest.status == "Pending")
            .options(
                selectinload(ResidentAccessRequest.customer),
                selectinload(ResidentAccessRequest.flat).selectinload(Flat.floor).selectinload(Floor.apartment),
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
                selectinload(ResidentAccessRequest.flat).selectinload(Flat.floor).selectinload(Floor.apartment),
                selectinload(ResidentAccessRequest.document),
                selectinload(ResidentAccessRequest.booking).selectinload(Booking.payments)
            )
        )
        return list(result.scalars().all())

    async def approve_request(self, db: AsyncSession, request_id: uuid.UUID, remarks: Optional[str] = None) -> Any:
        res = await db.execute(select(ResidentAccessRequest).where(ResidentAccessRequest.id == request_id).options(selectinload(ResidentAccessRequest.booking)))
        req = res.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Approval request not found")
        
        if req.status == "Approved":
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Request already approved",
                    "status": "Approved"
                }
            )
            
        if req.status == "Rejected":
            raise HTTPException(status_code=400, detail="Resident approval request already completed")
 
        req.status = "Approved"
        req.remarks = remarks
        req.approval_date = datetime.utcnow()
        
        # Update booking status to Approved
        if req.booking:
            req.booking.status = "Approved"
        
        # Upgrade user role
        user_res = await db.execute(select(User).where(User.id == req.customer_id))
        user = user_res.scalar_one_or_none()
        if user:
            user.role = "Resident"
            await update_supabase_user_role(str(user.id), "Resident")
            
        # Get floor_id and apartment_id from flat
        from app.models.models import Flat, Notification
        flat_res = await db.execute(select(Flat).where(Flat.id == req.flat_id).options(selectinload(Flat.floor)))
        flat = flat_res.scalar_one_or_none()
        if flat:
            # Check if resident profile already exists
            existing_res_query = await db.execute(select(Resident).where(Resident.user_id == req.customer_id))
            resident = existing_res_query.scalar_one_or_none()
            if resident:
                resident.apartment_id = flat.apartment_id or flat.floor.apartment_id
                resident.floor_id = flat.floor_id
                resident.flat_id = req.flat_id
                resident.booking_id = req.booking_id
                resident.resident_type = "Owner" if req.booking.booking_type == "BUY" else "Tenant"
                resident.status = "Active"
            else:
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
 
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Error during resident access approval: {e}")
            raise HTTPException(status_code=500, detail=f"Database error during approval: {str(e)}")

        # Reload complete object with all relationships eagerly loaded
        loaded_res = await db.execute(
            select(ResidentAccessRequest)
            .where(ResidentAccessRequest.id == request_id)
            .options(
                selectinload(ResidentAccessRequest.customer),
                selectinload(ResidentAccessRequest.flat).selectinload(Flat.floor).selectinload(Floor.apartment),
                selectinload(ResidentAccessRequest.document),
                selectinload(ResidentAccessRequest.booking).selectinload(Booking.payments)
            )
        )
        return loaded_res.scalar_one()

    async def reject_request(self, db: AsyncSession, request_id: uuid.UUID, remarks: str) -> Any:
        res = await db.execute(select(ResidentAccessRequest).where(ResidentAccessRequest.id == request_id))
        req = res.scalar_one_or_none()
        if not req:
            raise HTTPException(status_code=404, detail="Approval request not found")
            
        if req.status != "Pending":
            raise HTTPException(status_code=400, detail="Resident approval request already completed")
 
        req.status = "Rejected"
        req.remarks = remarks
        req.rejection_reason = remarks
 
        # Create Notification
        from app.models.models import Notification
        notification = Notification(
            user_id=req.customer_id,
            title="Resident Access Rejected",
            message=f"Your resident access request has been rejected. Reason: {remarks}"
        )
        db.add(notification)
 
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Error during resident access rejection: {e}")
            raise HTTPException(status_code=500, detail=f"Database error during rejection: {str(e)}")

        # Reload complete object with all relationships eagerly loaded
        loaded_res = await db.execute(
            select(ResidentAccessRequest)
            .where(ResidentAccessRequest.id == request_id)
            .options(
                selectinload(ResidentAccessRequest.customer),
                selectinload(ResidentAccessRequest.flat).selectinload(Flat.floor).selectinload(Floor.apartment),
                selectinload(ResidentAccessRequest.document),
                selectinload(ResidentAccessRequest.booking).selectinload(Booking.payments)
            )
        )
        return loaded_res.scalar_one()

resident_access_service = ResidentAccessService()

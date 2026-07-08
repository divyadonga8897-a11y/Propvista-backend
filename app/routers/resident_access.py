import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.middleware.auth import get_current_user, get_admin_user
from app.models.models import User
from app.schemas.resident_access import (
    ResidentAccessRequestCreate, 
    ResidentAccessRequestResponse,
    ResidentAccessApproval,
    ResidentAccessRejection
)
from app.services.resident_access_service import resident_access_service

router = APIRouter(prefix="/resident-access", tags=["Resident Access"])

@router.post("/", response_model=ResidentAccessRequestResponse)
async def create_access_request(
    request: ResidentAccessRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Customer requests resident access after booking/uploading documents"""
    return await resident_access_service.create_request(
        db=db,
        user_id=current_user.id,
        booking_id=request.booking_id,
        flat_id=request.flat_id,
        document_id=request.document_id
    )

@router.get("/me", response_model=List[ResidentAccessRequestResponse])
async def get_my_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Customer gets their access requests"""
    return await resident_access_service.get_my_requests(db=db, user_id=current_user.id)

@router.get("/pending", response_model=List[ResidentAccessRequestResponse])
async def get_pending_requests(
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin views all pending access requests"""
    return await resident_access_service.get_pending_requests(db=db)

@router.post("/{request_id}/approve", response_model=ResidentAccessRequestResponse)
async def approve_request(
    request_id: uuid.UUID,
    approval: ResidentAccessApproval,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin approves resident access request"""
    return await resident_access_service.approve_request(db=db, request_id=request_id, remarks=approval.remarks)

@router.post("/{request_id}/reject", response_model=ResidentAccessRequestResponse)
async def reject_request(
    request_id: uuid.UUID,
    rejection: ResidentAccessRejection,
    admin_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin rejects resident access request"""
    return await resident_access_service.reject_request(db=db, request_id=request_id, remarks=rejection.remarks)

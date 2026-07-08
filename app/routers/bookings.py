import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.services.booking_service import booking_service
from app.schemas.schemas import BookingCreate, BookingHold, BookingResponse

router = APIRouter(prefix="/booking", tags=["Bookings"])


@router.post("/hold", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def hold_flat(
    body: BookingHold,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Temporarily reserve a flat for 24 hours."""
    user_id = uuid.UUID(current_user.user_id)
    booking = await booking_service.hold_flat(db, user_id, body.flat_id)
    return await booking_service.get_booking_by_id(db, booking.id)


@router.post("/create", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    body: BookingCreate,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Initiate flat booking (BUY or RENT). Flat status is locked as Payment Pending."""
    user_id = uuid.UUID(current_user.user_id)
    booking = await booking_service.create_booking(db, user_id, body.flat_id, body.booking_type)
    return await booking_service.get_booking_by_id(db, booking.id)


@router.get("/history", response_model=List[BookingResponse])
async def get_booking_history(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all bookings. Customers see only theirs; Admins see all."""
    if current_user.role == "Admin":
        return await booking_service.get_bookings(db)
    else:
        user_id = uuid.UUID(current_user.user_id)
        return await booking_service.get_bookings(db, user_id)


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_details(
    booking_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get single booking details."""
    booking = await booking_service.get_booking_by_id(db, booking_id)
    if current_user.role != "Admin" and str(booking.user_id) != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this booking.")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel booking and release flat."""
    booking = await booking_service.get_booking_by_id(db, booking_id)
    if current_user.role != "Admin" and str(booking.user_id) != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking.")
    return await booking_service.cancel_booking(db, booking_id)

"""
facilities.py - Facility Booking endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import uuid
import datetime
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import FacilityBooking, Resident, Apartment

router = APIRouter(prefix="/facilities", tags=["Facilities"])

# --- Schemas ---

class FacilityBookingOut(BaseModel):
    id: str
    apartment_name: str
    facility_name: str
    booking_date: str
    booking_time: str
    duration_hours: int
    notes: Optional[str] = None
    status: str            # Pending | Approved | Cancelled
    created_at: str

class BookFacilityRequest(BaseModel):
    facility_name: str     # Club House, Gym, Meeting Hall, Community Hall, Indoor Games Room, Children Play Area
    booking_date: str      # YYYY-MM-DD
    booking_time: str      # HH:MM
    duration_hours: int = 1
    notes: Optional[str] = None

class BookingListResponse(BaseModel):
    bookings: List[FacilityBookingOut]
    total: int

# --- Endpoints ---

@router.get(
    "/",
    response_model=BookingListResponse,
    summary="List facility bookings",
    description="Residents see their own bookings. Admins see all.",
)
async def list_bookings(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(FacilityBooking).options(
        joinedload(FacilityBooking.apartment)
    )
    
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        # Filter by current user
        query = query.where(FacilityBooking.user_id == uid)
        
    query = query.order_by(FacilityBooking.booking_date.desc(), FacilityBooking.booking_time.desc())
    res = await db.execute(query)
    bookings = res.scalars().all()
    
    output = [
        FacilityBookingOut(
            id=str(b.id),
            apartment_name=b.apartment.name if b.apartment else "",
            facility_name=b.facility_name,
            booking_date=str(b.booking_date) if b.booking_date else "",
            booking_time=b.booking_time or "",
            duration_hours=b.duration_hours,
            notes=b.notes,
            status=b.status,
            created_at=str(b.created_at)
        )
        for b in bookings
    ]
    return BookingListResponse(bookings=output, total=len(output))


@router.post(
    "/book",
    response_model=FacilityBookingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Book a community facility (Resident)",
)
async def book_facility(
    body: BookFacilityRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    res_profile = await db.execute(select(Resident).where(Resident.user_id == uid).options(joinedload(Resident.apartment)))
    resident = res_profile.scalar_one_or_none()
    if not resident:
        raise HTTPException(status_code=400, detail="Only active residents can book community facilities.")
        
    b_date = datetime.date.fromisoformat(body.booking_date)
    
    # Check double booking rules (check if facility is already booked at that date/time in the same apartment)
    double_q = select(FacilityBooking).where(
        and_(
            FacilityBooking.apartment_id == resident.apartment_id,
            FacilityBooking.facility_name == body.facility_name,
            FacilityBooking.booking_date == b_date,
            FacilityBooking.booking_time == body.booking_time,
            FacilityBooking.status == "Approved"
        )
    )
    double_res = await db.execute(double_q)
    if double_res.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"{body.facility_name} is already booked at {body.booking_time} on {body.booking_date}."
        )
        
    booking = FacilityBooking(
        apartment_id=resident.apartment_id,
        user_id=uid,
        resident_id=resident.id,
        facility_name=body.facility_name,
        booking_date=b_date,
        booking_time=body.booking_time,
        duration_hours=body.duration_hours,
        notes=body.notes,
        status="Approved"  # Auto approved in this flow
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    
    return FacilityBookingOut(
        id=str(booking.id),
        apartment_name=resident.apartment.name,
        facility_name=booking.facility_name,
        booking_date=str(booking.booking_date),
        booking_time=booking.booking_time,
        duration_hours=booking.duration_hours,
        notes=booking.notes,
        status=booking.status,
        created_at=str(booking.created_at)
    )


@router.put(
    "/{booking_id}/status",
    summary="Update facility booking status (Admin)",
)
async def update_booking_status(
    booking_id: str,
    status: str,  # Approved, Cancelled
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    bid = uuid.UUID(booking_id)
    booking = await db.get(FacilityBooking, bid)
    if not booking:
        raise HTTPException(status_code=404, detail="Facility booking not found")
        
    booking.status = status
    await db.commit()
    return {"status": "success", "booking_status": status}

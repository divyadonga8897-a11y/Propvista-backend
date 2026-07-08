from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.models.models import User, Apartment, Booking, Complaint, Payment

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard", response_model=dict)
async def get_admin_dashboard_metrics(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Basic Counts
    users_count = await db.scalar(select(func.count()).select_from(User))
    apartments_count = await db.scalar(select(func.count()).select_from(Apartment))
    bookings_count = await db.scalar(select(func.count()).select_from(Booking))

    # Revenue (Sum of successful payments)
    revenue_result = await db.execute(select(func.sum(Payment.amount)).where(Payment.status == "Successful"))
    total_revenue = revenue_result.scalar() or 0.0

    # Complaints status breakdown
    complaints_result = await db.execute(select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status))
    complaints_breakdown = {status: count for status, count in complaints_result.all()}

    # Booking status breakdown
    bookings_result = await db.execute(select(Booking.status, func.count(Booking.id)).group_by(Booking.status))
    bookings_breakdown = {status: count for status, count in bookings_result.all()}

    return {
        "overview": {
            "total_users": users_count,
            "total_apartments": apartments_count,
            "total_bookings": bookings_count,
            "total_revenue": total_revenue
        },
        "complaints": complaints_breakdown,
        "bookings": bookings_breakdown
    }

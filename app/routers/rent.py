"""
rent.py - Monthly Rent management endpoints for Tenants.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import date
import datetime
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import Resident, Flat, RentRecord

router = APIRouter(prefix="/rent", tags=["Rent"])

# --- Schemas ---

class RentRecordOut(BaseModel):
    id: str
    resident_id: str
    flat_id: str
    flat_number: str
    month: int
    year: int
    amount: float
    due_date: str
    payment_status: str            # Paid | Pending | Overdue
    payment_date: Optional[str] = None
    outstanding_balance: float
    created_at: str

class RentListResponse(BaseModel):
    records: List[RentRecordOut]
    outstanding_total: float
    total: int

class GenerateRentRequest(BaseModel):
    apartment_id: str
    month: int
    year: int
    due_date: str          # YYYY-MM-DD

class CreateRentRecordRequest(BaseModel):
    resident_id: str
    flat_id: str
    month: int
    year: int
    amount: float
    due_date: str          # YYYY-MM-DD

class MarkRentPaidRequest(BaseModel):
    payment_date: Optional[str] = None

# --- Endpoints ---

@router.get(
    "/",
    response_model=RentListResponse,
    summary="List rent records",
    description="Tenants see their own rent history. Admins see all.",
)
async def list_rent(
    payment_status: Optional[str] = Query(None),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(RentRecord).options(
        joinedload(RentRecord.resident),
        joinedload(RentRecord.flat)
    )
    
    # Check if user is a tenant
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident or resident.resident_type != "Tenant":
            return RentListResponse(records=[], outstanding_total=0.0, total=0)
        query = query.where(RentRecord.resident_id == resident.id)
    
    if payment_status:
        query = query.where(RentRecord.payment_status == payment_status)
        
    query = query.order_by(RentRecord.year.desc(), RentRecord.month.desc())
    res = await db.execute(query)
    records = res.scalars().all()
    
    # Auto-flag overdue rent records
    today = date.today()
    updated = False
    outstanding_total = 0.0
    
    for r in records:
        if r.payment_status == "Pending" and r.due_date < today:
            r.payment_status = "Overdue"
            updated = True
        if r.payment_status in ["Pending", "Overdue"]:
            outstanding_total += float(r.amount)
            
    if updated:
        await db.commit()
        
    output = [
        RentRecordOut(
            id=str(r.id),
            resident_id=str(r.resident_id),
            flat_id=str(r.flat_id),
            flat_number=r.flat.flat_number if r.flat else "",
            month=r.month,
            year=r.year,
            amount=float(r.amount),
            due_date=str(r.due_date),
            payment_status=r.payment_status,
            payment_date=str(r.payment_date) if r.payment_date else None,
            outstanding_balance=float(r.amount) if r.payment_status in ["Pending", "Overdue"] else 0.0,
            created_at=str(r.created_at)
        )
        for r in records
    ]
    
    return RentListResponse(records=output, outstanding_total=outstanding_total, total=len(output))


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate monthly rent records for all Tenants of an apartment (Admin)"
)
async def generate_rent_records(
    body: GenerateRentRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    apt_id = uuid.UUID(body.apartment_id)
    # Get all active Tenants of the apartment
    res_query = select(Resident).where(
        and_(
            Resident.apartment_id == apt_id,
            Resident.status == "Active",
            Resident.resident_type == "Tenant"
        )
    ).options(joinedload(Resident.flat))
    res_exec = await db.execute(res_query)
    tenants = res_exec.scalars().all()
    
    created_count = 0
    due_d = date.fromisoformat(body.due_date)
    
    for t in tenants:
        # Check if rent record already exists for this month/year
        check_q = select(RentRecord).where(
            and_(
                RentRecord.resident_id == t.id,
                RentRecord.month == body.month,
                RentRecord.year == body.year
            )
        )
        check_res = await db.execute(check_q)
        if check_res.scalar_one_or_none():
            continue
            
        rent_amount = float(t.flat.price_rent or 0.0)
        if rent_amount <= 0.0:
            continue
            
        rent_record = RentRecord(
            resident_id=t.id,
            flat_id=t.flat_id,
            month=body.month,
            year=body.year,
            amount=rent_amount,
            due_date=due_d,
            payment_status="Pending"
        )
        db.add(rent_record)
        created_count += 1
        
    await db.commit()
    return {"status": "success", "message": f"Generated {created_count} rent records."}


@router.post(
    "/",
    response_model=RentRecordOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom rent record (Admin)",
)
async def create_rent_record(
    body: CreateRentRecordRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    due_d = date.fromisoformat(body.due_date)
    record = RentRecord(
        resident_id=uuid.UUID(body.resident_id),
        flat_id=uuid.UUID(body.flat_id),
        month=body.month,
        year=body.year,
        amount=body.amount,
        due_date=due_d,
        payment_status="Pending"
    )
    db.add(record)
    await db.commit()
    
    # Query back
    res = await db.execute(
        select(RentRecord).where(RentRecord.id == record.id).options(
            joinedload(RentRecord.flat)
        )
    )
    r = res.scalar_one()
    return RentRecordOut(
        id=str(r.id),
        resident_id=str(r.resident_id),
        flat_id=str(r.flat_id),
        flat_number=r.flat.flat_number if r.flat else "",
        month=r.month,
        year=r.year,
        amount=float(r.amount),
        due_date=str(r.due_date),
        payment_status=r.payment_status,
        payment_date=str(r.payment_date) if r.payment_date else None,
        outstanding_balance=float(r.amount),
        created_at=str(r.created_at)
    )


@router.post(
    "/{record_id}/pay",
    summary="Mark rent record as paid (Tenant/Admin)"
)
async def pay_rent(
    record_id: str,
    body: MarkRentPaidRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    rid = uuid.UUID(record_id)
    rec_res = await db.execute(select(RentRecord).where(RentRecord.id == rid).options(joinedload(RentRecord.resident)))
    record = rec_res.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Rent record not found")
        
    # Check security: Tenant must own this record
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        if record.resident.user_id != uid:
            raise HTTPException(status_code=403, detail="You are not authorized to pay this rent record.")
            
    record.payment_status = "Paid"
    p_date = date.fromisoformat(body.payment_date) if body.payment_date else date.today()
    record.payment_date = datetime.datetime.combine(p_date, datetime.time.min)
    await db.commit()
    return {"status": "success", "message": "Rent marked as paid."}

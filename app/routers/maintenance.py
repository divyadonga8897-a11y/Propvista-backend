"""
maintenance.py - Maintenance dues and service request endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import date
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import Resident, Flat, Apartment, Floor, MaintenanceBill

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])

# --- Schemas ---

class MaintenanceBillOut(BaseModel):
    id: str
    resident_id: str
    flat_id: str
    flat_number: str
    apartment_name: str
    month: int
    year: int
    amount: float
    due_date: str
    late_fee: float
    payment_status: str            # Paid | Pending | Overdue
    payment_date: Optional[str] = None
    created_at: str

class MaintenanceListResponse(BaseModel):
    records: List[MaintenanceBillOut]
    total: int

class GenerateBillsRequest(BaseModel):
    apartment_id: str
    month: int
    year: int
    due_date: str          # YYYY-MM-DD
    amount: Optional[float] = None

class CreateMaintenanceBillRequest(BaseModel):
    resident_id: str
    flat_id: str
    month: int
    year: int
    amount: float
    due_date: str          # YYYY-MM-DD
    late_fee: Optional[float] = 0.0

class UpdateBillAmountRequest(BaseModel):
    amount: float

class ApplyLateFeeRequest(BaseModel):
    late_fee: float

class PayBillRequest(BaseModel):
    bill_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = "pay_mock_maintenance"

# --- Endpoints ---

@router.get(
    "/",
    response_model=MaintenanceListResponse,
    summary="List maintenance bills",
    description="Residents see their own bills. Admins see all.",
)
async def list_maintenance(
    flat_id: Optional[str] = Query(None),
    payment_status: Optional[str] = Query(None),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(MaintenanceBill).options(
        joinedload(MaintenanceBill.resident).joinedload(Resident.apartment),
        joinedload(MaintenanceBill.flat)
    )
    
    # If not Admin, restrict to current user's resident ID
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident:
            return MaintenanceListResponse(records=[], total=0)
        query = query.where(MaintenanceBill.resident_id == resident.id)
    else:
        if flat_id:
            query = query.where(MaintenanceBill.flat_id == uuid.UUID(flat_id))
            
    if payment_status:
        query = query.where(MaintenanceBill.payment_status == payment_status)
        
    query = query.order_by(MaintenanceBill.year.desc(), MaintenanceBill.month.desc())
    res = await db.execute(query)
    records = res.scalars().all()
    
    # Auto-flag overdue bills on read
    today = date.today()
    updated = False
    for r in records:
        if r.payment_status == "Pending" and r.due_date < today:
            r.payment_status = "Overdue"
            updated = True
    if updated:
        await db.commit()
        
    output = [
        MaintenanceBillOut(
            id=str(r.id),
            resident_id=str(r.resident_id),
            flat_id=str(r.flat_id),
            flat_number=r.flat.flat_number if r.flat else "",
            apartment_name=r.resident.apartment.name if r.resident and r.resident.apartment else "",
            month=r.month,
            year=r.year,
            amount=float(r.amount),
            due_date=str(r.due_date),
            late_fee=float(r.late_fee or 0),
            payment_status=r.payment_status,
            payment_date=str(r.payment_date) if r.payment_date else None,
            created_at=str(r.created_at)
        )
        for r in records
    ]
    return MaintenanceListResponse(records=output, total=len(output))


@router.post(
    "/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Generate monthly maintenance bills for all residents of an apartment (Admin)"
)
async def generate_bills(
    body: GenerateBillsRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    apt_id = uuid.UUID(body.apartment_id)
    # Get all active residents of the apartment
    res_query = select(Resident).where(and_(Resident.apartment_id == apt_id, Resident.status == "Active")).options(joinedload(Resident.flat))
    res_exec = await db.execute(res_query)
    residents = res_exec.scalars().all()
    
    created_count = 0
    due_d = date.fromisoformat(body.due_date)
    
    for r in residents:
        # Check if already exists for this month/year
        check_q = select(MaintenanceBill).where(
            and_(
                MaintenanceBill.resident_id == r.id,
                MaintenanceBill.month == body.month,
                MaintenanceBill.year == body.year
            )
        )
        check_res = await db.execute(check_q)
        if check_res.scalar_one_or_none():
            continue
            
        bill_amount = body.amount if body.amount is not None else float(r.flat.maintenance_fee or 0.0)
        
        bill = MaintenanceBill(
            resident_id=r.id,
            flat_id=r.flat_id,
            month=body.month,
            year=body.year,
            amount=bill_amount,
            due_date=due_d,
            late_fee=0.0,
            payment_status="Pending"
        )
        db.add(bill)
        created_count += 1
        
    await db.commit()
    return {"status": "success", "message": f"Generated {created_count} maintenance bills."}


@router.post(
    "/",
    response_model=MaintenanceBillOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create custom maintenance bill (Admin)",
)
async def create_maintenance(
    body: CreateMaintenanceBillRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    due_d = date.fromisoformat(body.due_date)
    bill = MaintenanceBill(
        resident_id=uuid.UUID(body.resident_id),
        flat_id=uuid.UUID(body.flat_id),
        month=body.month,
        year=body.year,
        amount=body.amount,
        due_date=due_d,
        late_fee=body.late_fee or 0.0,
        payment_status="Pending"
    )
    db.add(bill)
    await db.commit()
    
    # Query back to load relationships
    res = await db.execute(
        select(MaintenanceBill).where(MaintenanceBill.id == bill.id).options(
            joinedload(MaintenanceBill.resident).joinedload(Resident.apartment),
            joinedload(MaintenanceBill.flat)
        )
    )
    r = res.scalar_one()
    return MaintenanceBillOut(
        id=str(r.id),
        resident_id=str(r.resident_id),
        flat_id=str(r.flat_id),
        flat_number=r.flat.flat_number if r.flat else "",
        apartment_name=r.resident.apartment.name if r.resident and r.resident.apartment else "",
        month=r.month,
        year=r.year,
        amount=float(r.amount),
        due_date=str(r.due_date),
        late_fee=float(r.late_fee or 0),
        payment_status=r.payment_status,
        payment_date=str(r.payment_date) if r.payment_date else None,
        created_at=str(r.created_at)
    )


@router.put(
    "/{bill_id}/amount",
    summary="Update maintenance bill amount (Admin)"
)
async def update_bill_amount(
    bill_id: str,
    body: UpdateBillAmountRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    bid = uuid.UUID(bill_id)
    bill_res = await db.execute(select(MaintenanceBill).where(MaintenanceBill.id == bid))
    bill = bill_res.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Maintenance bill not found")
    bill.amount = body.amount
    await db.commit()
    return {"status": "success", "amount": body.amount}


@router.put(
    "/{bill_id}/late-fee",
    summary="Apply late fee to a bill (Admin)"
)
async def apply_late_fee(
    bill_id: str,
    body: ApplyLateFeeRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    bid = uuid.UUID(bill_id)
    bill_res = await db.execute(select(MaintenanceBill).where(MaintenanceBill.id == bid))
    bill = bill_res.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Maintenance bill not found")
    bill.late_fee = body.late_fee
    await db.commit()
    return {"status": "success", "late_fee": body.late_fee}


@router.post(
    "/pay",
    summary="Pay a maintenance bill (Resident)",
    description="Pay a maintenance bill by passing the bill ID in the request body.",
)
async def pay_maintenance_bill_alias(
    body: PayBillRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    bill_id = getattr(body, "bill_id", None)
    if not bill_id:
        raise HTTPException(status_code=400, detail="Missing bill_id in request body.")
    return await pay_maintenance_bill(bill_id=bill_id, body=body, current_user=current_user, db=db)


@router.post(
    "/{bill_id}/pay",
    summary="Pay a maintenance bill (Resident)"
)
async def pay_maintenance_bill(
    bill_id: str,
    body: PayBillRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    bid = uuid.UUID(bill_id)
    bill_res = await db.execute(select(MaintenanceBill).where(MaintenanceBill.id == bid).options(joinedload(MaintenanceBill.resident)))
    bill = bill_res.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Maintenance bill not found")
        
    # Check security: Resident must own this bill
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        if bill.resident.user_id != uid:
            raise HTTPException(status_code=403, detail="You are not authorized to pay this bill.")
            
    bill.payment_status = "Paid"
    import datetime
    bill.payment_date = datetime.datetime.utcnow()
    bill.razorpay_payment_id = body.razorpay_payment_id
    await db.commit()
    return {"status": "success", "message": "Bill marked as paid."}

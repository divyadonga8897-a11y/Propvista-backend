"""
visitors.py - Visitor management endpoints for resident flats.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
import uuid
import datetime
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import Visitor, Resident, Flat

router = APIRouter(prefix="/visitors", tags=["Visitors"])

# --- Schemas ---

class VisitorOut(BaseModel):
    id: str
    resident_id: str
    visitor_name: str
    phone: Optional[str] = None
    purpose: Optional[str] = None
    visit_date: str
    visit_time: str
    approval_status: str       # Pending | Approved | Rejected
    qr_code: Optional[str] = None
    flat_number: str
    check_in: Optional[str] = None
    check_out: Optional[str] = None

class RegisterVisitorRequest(BaseModel):
    visitor_name: str
    phone: Optional[str] = None
    purpose: Optional[str] = None
    visit_date: str          # YYYY-MM-DD
    visit_time: str          # HH:MM

class UpdateApprovalStatusRequest(BaseModel):
    approval_status: str     # Approved | Rejected

class VisitorListResponse(BaseModel):
    visitors: List[VisitorOut]
    total: int

# --- Endpoints ---

@router.get(
    "/",
    response_model=VisitorListResponse,
    summary="List visitors",
    description="Residents see visitors to their flat. Admins see all visitors across apartments.",
)
async def list_visitors(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Visitor).options(
        joinedload(Visitor.resident),
        joinedload(Visitor.flat)
    )
    
    # Check security scope
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident:
            return VisitorListResponse(visitors=[], total=0)
        query = query.where(Visitor.resident_id == resident.id)
        
    query = query.order_by(Visitor.visit_date.desc(), Visitor.visit_time.desc())
    
    total_q = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(total_q)
    total = total_res.scalar() or 0
    
    query = query.limit(page_size).offset((page - 1) * page_size)
    res = await db.execute(query)
    db_visitors = res.scalars().all()
    
    output = [
        VisitorOut(
            id=str(v.id),
            resident_id=str(v.resident_id) if v.resident_id else "",
            visitor_name=v.name,
            phone=v.phone,
            purpose=v.purpose,
            visit_date=str(v.visit_date) if v.visit_date else "",
            visit_time=v.visit_time or "",
            approval_status=v.approval_status or "Pending",
            qr_code=v.qr_code,
            flat_number=v.flat.flat_number if v.flat else "",
            check_in=str(v.check_in) if v.check_in else None,
            check_out=str(v.check_out) if v.check_out else None
        )
        for v in db_visitors
    ]
    return VisitorListResponse(visitors=output, total=total)


@router.post(
    "/",
    response_model=VisitorOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a visitor entry (Resident)",
    description="Registers a visitor and returns a pass containing a mock QR code.",
)
async def log_visitor(
    body: RegisterVisitorRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    res_profile = await db.execute(select(Resident).where(Resident.user_id == uid).options(joinedload(Resident.flat)))
    resident = res_profile.scalar_one_or_none()
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only registered residents can pre-register visitors."
        )
        
    vis_date = datetime.date.fromisoformat(body.visit_date)
    vis_id = uuid.uuid4()
    qr_data = f"PROPVISTA-PASS-{vis_id.hex[:8].upper()}-{body.visitor_name.replace(' ', '_')}"
    
    visitor = Visitor(
        id=vis_id,
        flat_id=resident.flat_id,
        resident_id=resident.id,
        name=body.visitor_name,
        phone=body.phone,
        purpose=body.purpose,
        visit_date=vis_date,
        visit_time=body.visit_time,
        approval_status="Pending",
        qr_code=qr_data
    )
    db.add(visitor)
    await db.commit()
    
    # Query back to get relations
    res = await db.execute(select(Visitor).where(Visitor.id == vis_id).options(joinedload(Visitor.flat)))
    v = res.scalar_one()
    
    return VisitorOut(
        id=str(v.id),
        resident_id=str(v.resident_id),
        visitor_name=v.name,
        phone=v.phone,
        purpose=v.purpose,
        visit_date=str(v.visit_date),
        visit_time=v.visit_time,
        approval_status=v.approval_status,
        qr_code=v.qr_code,
        flat_number=v.flat.flat_number if v.flat else "",
        check_in=str(v.check_in) if v.check_in else None,
        check_out=str(v.check_out) if v.check_out else None
    )


@router.put(
    "/{visitor_id}/status",
    response_model=VisitorOut,
    summary="Approve/Reject visitor entry (Admin/Security)",
)
async def update_visitor_status(
    visitor_id: str,
    body: UpdateApprovalStatusRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    vid = uuid.UUID(visitor_id)
    visitor = await db.get(Visitor, vid, options=[joinedload(Visitor.flat)])
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor pass not found")
        
    visitor.approval_status = body.approval_status
    if body.approval_status == "Approved":
        visitor.check_in = datetime.datetime.utcnow()
    await db.commit()
    
    return VisitorOut(
        id=str(visitor.id),
        resident_id=str(visitor.resident_id) if visitor.resident_id else "",
        visitor_name=visitor.name,
        phone=visitor.phone,
        purpose=visitor.purpose,
        visit_date=str(visitor.visit_date) if visitor.visit_date else "",
        visit_time=visitor.visit_time or "",
        approval_status=visitor.approval_status,
        qr_code=visitor.qr_code,
        flat_number=visitor.flat.flat_number if visitor.flat else "",
        check_in=str(visitor.check_in) if visitor.check_in else None,
        check_out=str(visitor.check_out) if visitor.check_out else None
    )


@router.patch(
    "/{visitor_id}/checkout",
    response_model=VisitorOut,
    summary="Mark visitor as checked out (Resident/Admin)",
)
async def checkout_visitor(
    visitor_id: str,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    vid = uuid.UUID(visitor_id)
    visitor = await db.get(Visitor, vid, options=[joinedload(Visitor.flat), joinedload(Visitor.resident)])
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor record not found")
        
    # Check security: Resident must own this visitor
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        if visitor.resident.user_id != uid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not own this flat's visitors.")
            
    visitor.check_out = datetime.datetime.utcnow()
    await db.commit()
    
    return VisitorOut(
        id=str(visitor.id),
        resident_id=str(visitor.resident_id) if visitor.resident_id else "",
        visitor_name=visitor.name,
        phone=visitor.phone,
        purpose=visitor.purpose,
        visit_date=str(visitor.visit_date) if visitor.visit_date else "",
        visit_time=visitor.visit_time or "",
        approval_status=visitor.approval_status,
        qr_code=visitor.qr_code,
        flat_number=visitor.flat.flat_number if visitor.flat else "",
        check_in=str(visitor.check_in) if visitor.check_in else None,
        check_out=str(visitor.check_out) if visitor.check_out else None
    )


@router.get(
    "/{visitor_id}",
    response_model=VisitorOut,
    summary="Get visitor by ID",
)
async def get_visitor(
    visitor_id: str,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    vid = uuid.UUID(visitor_id)
    visitor = await db.get(Visitor, vid, options=[joinedload(Visitor.flat), joinedload(Visitor.resident)])
    if not visitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visitor record not found")
        
    # Security check
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        if visitor.resident.user_id != uid:
            raise HTTPException(status_code=403, detail="Access denied.")
            
    return VisitorOut(
        id=str(visitor.id),
        resident_id=str(visitor.resident_id) if visitor.resident_id else "",
        visitor_name=visitor.name,
        phone=visitor.phone,
        purpose=visitor.purpose,
        visit_date=str(visitor.visit_date) if visitor.visit_date else "",
        visit_time=visitor.visit_time or "",
        approval_status=visitor.approval_status,
        qr_code=visitor.qr_code,
        flat_number=visitor.flat.flat_number if visitor.flat else "",
        check_in=str(visitor.check_in) if visitor.check_in else None,
        check_out=str(visitor.check_out) if visitor.check_out else None
    )

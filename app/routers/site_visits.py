import uuid
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.models.models import SiteVisit, Apartment, Flat
from app.services.audit_service import log_audit_action

router = APIRouter(prefix="/site-visits", tags=["Site Visits"])

class SiteVisitCreate(BaseModel):
    apartment_id: str
    flat_id: Optional[str] = None
    visit_date: date
    visit_time: str
    purpose: str
    contact_number: str
    notes: Optional[str] = None

class SiteVisitOut(BaseModel):
    id: str
    apartment_id: str
    flat_id: Optional[str]
    customer_id: str
    visit_date: str
    visit_time: str
    purpose: str
    contact_number: str
    status: str
    notes: Optional[str]
    created_at: str
    apartment_name: Optional[str] = None
    flat_number: Optional[str] = None

@router.post("/", response_model=SiteVisitOut)
async def create_site_visit(
    data: SiteVisitCreate,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    aid = uuid.UUID(data.apartment_id)
    fid = uuid.UUID(data.flat_id) if data.flat_id else None

    visit = SiteVisit(
        customer_id=uid,
        apartment_id=aid,
        flat_id=fid,
        visit_date=data.visit_date,
        visit_time=data.visit_time,
        purpose=data.purpose,
        contact_number=data.contact_number,
        notes=data.notes
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)

    return SiteVisitOut(
        id=str(visit.id),
        apartment_id=str(visit.apartment_id),
        flat_id=str(visit.flat_id) if visit.flat_id else None,
        customer_id=str(visit.customer_id),
        visit_date=str(visit.visit_date),
        visit_time=visit.visit_time,
        purpose=visit.purpose,
        contact_number=visit.contact_number,
        status=visit.status,
        notes=visit.notes,
        created_at=str(visit.created_at)
    )

@router.get("/", response_model=List[SiteVisitOut])
async def get_site_visits(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        select(SiteVisit, Apartment.name, Flat.flat_number)
        .outerjoin(Apartment, SiteVisit.apartment_id == Apartment.id)
        .outerjoin(Flat, SiteVisit.flat_id == Flat.id)
        .order_by(SiteVisit.created_at.desc())
    )
    rows = result.all()

    out = []
    for row in rows:
        visit, apt_name, flat_num = row
        out.append(SiteVisitOut(
            id=str(visit.id),
            apartment_id=str(visit.apartment_id),
            flat_id=str(visit.flat_id) if visit.flat_id else None,
            customer_id=str(visit.customer_id),
            visit_date=str(visit.visit_date),
            visit_time=visit.visit_time,
            purpose=visit.purpose,
            contact_number=visit.contact_number,
            status=visit.status,
            notes=visit.notes,
            created_at=str(visit.created_at),
            apartment_name=apt_name,
            flat_number=flat_num
        ))
    return out

@router.patch("/{visit_id}/status", response_model=dict)
async def update_site_visit_status(
    visit_id: str,
    status: str = Query(...),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    valid_statuses = ["Scheduled", "Completed", "Cancelled", "Pending", "Approved", "Rejected"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    vid = uuid.UUID(visit_id)
    visit = await db.get(SiteVisit, vid)
    if not visit:
        raise HTTPException(status_code=404, detail="Site visit not found")

    visit.status = status
    await db.commit()

    await log_audit_action(
        db, f"Updated Site Visit Status to {status}", "SiteVisits",
        f"Visit ID: {visit_id}", current_user.user_id
    )

    return {"status": "success", "message": f"Site visit marked as {status}"}

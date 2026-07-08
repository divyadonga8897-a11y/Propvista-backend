"""
complaints.py - Society complaint management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
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
from app.models.models import Complaint, Resident, Apartment

router = APIRouter(prefix="/complaints", tags=["Complaints"])

# --- Schemas ---

class ComplaintOut(BaseModel):
    id: str
    apartment_id: str
    apartment_name: str
    resident_id: str
    user_id: str
    category: str
    priority: str
    title: str
    description: str
    status: str         # Open | Assigned | In Progress | Resolved | Closed
    assigned_to: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: str
    updated_at: str

class CreateComplaintRequest(BaseModel):
    category: str      # Plumbing, Electrical, Security, Lift, Cleaning, Parking, Water Supply, Internet, Other
    priority: str = "Medium"   # Low, Medium, High
    title: str
    description: str

class UpdateComplaintRequest(BaseModel):
    category: Optional[str] = None
    priority: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None

class AdminUpdateComplaintRequest(BaseModel):
    status: str         # Open | Assigned | In Progress | Resolved | Closed
    assigned_to: Optional[str] = None
    resolution_note: Optional[str] = None

class ComplaintListResponse(BaseModel):
    complaints: List[ComplaintOut]
    total: int

# --- Endpoints ---

@router.get(
    "/",
    response_model=ComplaintListResponse,
    summary="List complaints",
    description="Residents see their own complaints. Admins see all across all apartments.",
)
async def list_complaints(
    apartment_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Complaint).options(
        joinedload(Complaint.apartment)
    )
    
    # SECURITY & ISOLATION CHECK
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        # Find resident profile
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident:
            return ComplaintListResponse(complaints=[], total=0)
        # Filter to the resident's specific resident profile
        query = query.where(Complaint.resident_id == resident.id)
    else:
        if apartment_id:
            query = query.where(Complaint.apartment_id == uuid.UUID(apartment_id))
            
    if status_filter:
        query = query.where(Complaint.status == status_filter)
        
    query = query.order_by(Complaint.created_at.desc())
    
    # Get total count
    total_q = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(total_q)
    total = total_res.scalar() or 0
    
    query = query.limit(page_size).offset((page - 1) * page_size)
    res = await db.execute(query)
    db_complaints = res.scalars().all()
    
    output = [
        ComplaintOut(
            id=str(c.id),
            apartment_id=str(c.apartment_id),
            apartment_name=c.apartment.name if c.apartment else "",
            resident_id=str(c.resident_id) if c.resident_id else "",
            user_id=str(c.user_id),
            category=c.category or "Other",
            priority=c.priority or "Medium",
            title=c.title,
            description=c.description,
            status=c.status,
            assigned_to=c.assigned_to,
            resolution_note=c.resolution_note,
            created_at=str(c.created_at),
            updated_at=str(c.updated_at)
        )
        for c in db_complaints
    ]
    return ComplaintListResponse(complaints=output, total=total)


@router.post(
    "/",
    response_model=ComplaintOut,
    status_code=status.HTTP_201_CREATED,
    summary="Raise a complaint (Resident)",
    description="Authenticated resident raises a complaint against their apartment/society.",
)
async def create_complaint(
    body: CreateComplaintRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    res_profile = await db.execute(select(Resident).where(Resident.user_id == uid).options(joinedload(Resident.apartment)))
    resident = res_profile.scalar_one_or_none()
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only registered residents with an active flat profile can raise complaints."
        )
        
    complaint = Complaint(
        apartment_id=resident.apartment_id,
        user_id=uid,
        resident_id=resident.id,
        category=body.category,
        priority=body.priority,
        title=body.title,
        description=body.description,
        status="Open"
    )
    db.add(complaint)
    await db.commit()
    await db.refresh(complaint)
    
    return ComplaintOut(
        id=str(complaint.id),
        apartment_id=str(complaint.apartment_id),
        apartment_name=resident.apartment.name,
        resident_id=str(complaint.resident_id),
        user_id=str(complaint.user_id),
        category=complaint.category or "Other",
        priority=complaint.priority or "Medium",
        title=complaint.title,
        description=complaint.description,
        status=complaint.status,
        assigned_to=complaint.assigned_to,
        resolution_note=complaint.resolution_note,
        created_at=str(complaint.created_at),
        updated_at=str(complaint.updated_at)
    )


@router.get(
    "/history",
    response_model=ComplaintListResponse,
    summary="Complaint history",
    description="Returns complaint history for the current resident or admin.",
)
async def complaint_history(
    apartment_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await list_complaints(
        apartment_id=apartment_id,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
        current_user=current_user,
        db=db,
    )


@router.get(
    "/{complaint_id}",
    response_model=ComplaintOut,
    summary="Get complaint by ID",
)
async def get_complaint(
    complaint_id: str,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    cid = uuid.UUID(complaint_id)
    complaint = await db.get(Complaint, cid, options=[joinedload(Complaint.apartment)])
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    # SECURITY & ISOLATION CHECK
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        if complaint.user_id != uid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this complaint.")
            
    return ComplaintOut(
        id=str(complaint.id),
        apartment_id=str(complaint.apartment_id),
        apartment_name=complaint.apartment.name if complaint.apartment else "",
        resident_id=str(complaint.resident_id) if complaint.resident_id else "",
        user_id=str(complaint.user_id),
        category=complaint.category or "Other",
        priority=complaint.priority or "Medium",
        title=complaint.title,
        description=complaint.description,
        status=complaint.status,
        assigned_to=complaint.assigned_to,
        resolution_note=complaint.resolution_note,
        created_at=str(complaint.created_at),
        updated_at=str(complaint.updated_at)
    )


@router.put(
    "/{complaint_id}",
    response_model=ComplaintOut,
    summary="Update complaint (Resident/Admin)",
)
async def update_complaint(
    complaint_id: str,
    body: UpdateComplaintRequest,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    cid = uuid.UUID(complaint_id)
    complaint = await db.get(Complaint, cid, options=[joinedload(Complaint.apartment)])
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    # SECURITY check
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        if complaint.user_id != uid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
            
    if body.category is not None:
        complaint.category = body.category
    if body.priority is not None:
        complaint.priority = body.priority
    if body.title is not None:
        complaint.title = body.title
    if body.description is not None:
        complaint.description = body.description
        
    complaint.updated_at = datetime.datetime.utcnow()
    await db.commit()
    await db.refresh(complaint)
    
    return ComplaintOut(
        id=str(complaint.id),
        apartment_id=str(complaint.apartment_id),
        apartment_name=complaint.apartment.name if complaint.apartment else "",
        resident_id=str(complaint.resident_id) if complaint.resident_id else "",
        user_id=str(complaint.user_id),
        category=complaint.category or "Other",
        priority=complaint.priority or "Medium",
        title=complaint.title,
        description=complaint.description,
        status=complaint.status,
        assigned_to=complaint.assigned_to,
        resolution_note=complaint.resolution_note,
        created_at=str(complaint.created_at),
        updated_at=str(complaint.updated_at)
    )


@router.patch(
    "/{complaint_id}/status",
    response_model=ComplaintOut,
    summary="Update complaint status (Admin)",
    description="Admin updates status, assignee, and notes: Open -> Assigned -> In Progress -> Resolved -> Closed.",
)
async def update_complaint_status(
    complaint_id: str,
    body: AdminUpdateComplaintRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    cid = uuid.UUID(complaint_id)
    complaint = await db.get(Complaint, cid, options=[joinedload(Complaint.apartment)])
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    valid_statuses = ["Open", "Assigned", "In Progress", "Resolved", "Closed"]
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
        
    complaint.status = body.status
    if body.assigned_to is not None:
        complaint.assigned_to = body.assigned_to
    if body.resolution_note is not None:
        complaint.resolution_note = body.resolution_note
        
    complaint.updated_at = datetime.datetime.utcnow()
    await db.commit()
    await db.refresh(complaint)
    
    return ComplaintOut(
        id=str(complaint.id),
        apartment_id=str(complaint.apartment_id),
        apartment_name=complaint.apartment.name if complaint.apartment else "",
        resident_id=str(complaint.resident_id) if complaint.resident_id else "",
        user_id=str(complaint.user_id),
        category=complaint.category or "Other",
        priority=complaint.priority or "Medium",
        title=complaint.title,
        description=complaint.description,
        status=complaint.status,
        assigned_to=complaint.assigned_to,
        resolution_note=complaint.resolution_note,
        created_at=str(complaint.created_at),
        updated_at=str(complaint.updated_at)
    )

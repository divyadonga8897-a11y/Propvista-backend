"""
announcements.py - Society announcements broadcast endpoints.
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
from app.models.models import Announcement, Resident

router = APIRouter(prefix="/announcements", tags=["Announcements"])

# --- Schemas ---

class AnnouncementOut(BaseModel):
    id: str
    apartment_id: str
    title: str
    content: str
    announcement_type: str        # General | Maintenance | Emergency | Event
    publish_date: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str

class CreateAnnouncementRequest(BaseModel):
    apartment_id: str
    title: str
    content: str
    announcement_type: str = "General"  # General, Maintenance, Emergency, Event, Alert
    publish_date: Optional[str] = None

class AnnouncementListResponse(BaseModel):
    announcements: List[AnnouncementOut]
    total: int

# --- Endpoints ---

@router.get(
    "/",
    response_model=AnnouncementListResponse,
    summary="List announcements",
    description="Returns announcements for the resident's apartment. Admins see all.",
)
async def list_announcements(
    apartment_id: Optional[str] = Query(None, description="Filter by apartment UUID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Announcement)
    
    # SECURITY & ISOLATION CHECK
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        # Find resident profile
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident:
            return AnnouncementListResponse(announcements=[], total=0)
        # Force filter to the resident's apartment
        query = query.where(Announcement.apartment_id == resident.apartment_id)
    else:
        # Admins can filter or see all
        if apartment_id:
            query = query.where(Announcement.apartment_id == uuid.UUID(apartment_id))
            
    query = query.order_by(Announcement.created_at.desc())
    
    # Get total count
    total_q = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(total_q)
    total = total_res.scalar() or 0
    
    query = query.limit(page_size).offset((page - 1) * page_size)
    res = await db.execute(query)
    db_announcements = res.scalars().all()
    
    output = [
        AnnouncementOut(
            id=str(a.id),
            apartment_id=str(a.apartment_id),
            title=a.title,
            content=a.content,
            announcement_type=a.announcement_type or "General",
            publish_date=str(a.publish_date) if a.publish_date else None,
            created_by=a.created_by,
            created_at=str(a.created_at)
        )
        for a in db_announcements
    ]
    return AnnouncementListResponse(announcements=output, total=total)


@router.post(
    "/",
    response_model=AnnouncementOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an announcement (Admin)",
    description="Admin broadcasts a society announcement to all residents of an apartment.",
)
async def create_announcement(
    body: CreateAnnouncementRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    pub_date = None
    if body.publish_date:
        pub_date = datetime.datetime.fromisoformat(body.publish_date)
    else:
        pub_date = datetime.datetime.utcnow()
        
    announcement = Announcement(
        apartment_id=uuid.UUID(body.apartment_id),
        title=body.title,
        content=body.content,
        announcement_type=body.announcement_type,
        publish_date=pub_date,
        created_by="Admin"
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    
    return AnnouncementOut(
        id=str(announcement.id),
        apartment_id=str(announcement.apartment_id),
        title=announcement.title,
        content=announcement.content,
        announcement_type=announcement.announcement_type or "General",
        publish_date=str(announcement.publish_date) if announcement.publish_date else None,
        created_by=announcement.created_by,
        created_at=str(announcement.created_at)
    )


@router.get(
    "/{announcement_id}",
    response_model=AnnouncementOut,
    summary="Get announcement by ID",
)
async def get_announcement(
    announcement_id: str,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    aid = uuid.UUID(announcement_id)
    announcement = await db.get(Announcement, aid)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
        
    # SECURITY & ISOLATION CHECK
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident or resident.apartment_id != announcement.apartment_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this announcement.")
            
    return AnnouncementOut(
        id=str(announcement.id),
        apartment_id=str(announcement.apartment_id),
        title=announcement.title,
        content=announcement.content,
        announcement_type=announcement.announcement_type or "General",
        publish_date=str(announcement.publish_date) if announcement.publish_date else None,
        created_by=announcement.created_by,
        created_at=str(announcement.created_at)
    )


@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete announcement (Admin)",
)
async def delete_announcement(
    announcement_id: str,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    aid = uuid.UUID(announcement_id)
    announcement = await db.get(Announcement, aid)
    if not announcement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
    await db.delete(announcement)
    await db.commit()
    return None

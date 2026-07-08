import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import CommunityEvent, EventRSVP, Resident
from app.schemas.schemas import CommunityEventCreate, CommunityEventResponse, EventRSVPCreate, EventRSVPResponse

from app.core.dependencies import verify_resident_access

router = APIRouter(prefix="/events", tags=["Community Events"])

@router.get("/{apartment_id}", response_model=List[CommunityEventResponse])
async def get_events(
    apartment_id: uuid.UUID,
    current_user: UserClaims = Depends(verify_resident_access),
    db: AsyncSession = Depends(get_db)
):
    query = select(CommunityEvent).where(
        CommunityEvent.apartment_id == apartment_id,
        CommunityEvent.is_active == True
    ).order_by(CommunityEvent.event_date)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=CommunityEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    apartment_id: uuid.UUID,
    event: CommunityEventCreate,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    new_event = CommunityEvent(
        apartment_id=apartment_id,
        created_by=current_user.email,
        **event.model_dump()
    )
    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)
    return new_event

@router.post("/{event_id}/rsvp", response_model=EventRSVPResponse)
async def rsvp_event(
    event_id: uuid.UUID,
    rsvp: EventRSVPCreate,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = uuid.UUID(current_user.user_id)
    
    # Get resident ID if they are a resident
    res_query = select(Resident).where(Resident.user_id == user_id)
    res_result = await db.execute(res_query)
    resident = res_result.scalar_one_or_none()
    
    query = select(EventRSVP).where(
        EventRSVP.event_id == event_id,
        EventRSVP.user_id == user_id
    )
    result = await db.execute(query)
    existing_rsvp = result.scalar_one_or_none()
    
    if existing_rsvp:
        existing_rsvp.status = rsvp.status
        await db.commit()
        await db.refresh(existing_rsvp)
        return existing_rsvp
    else:
        new_rsvp = EventRSVP(
            event_id=event_id,
            user_id=user_id,
            resident_id=resident.id if resident else None,
            status=rsvp.status
        )
        db.add(new_rsvp)
        await db.commit()
        await db.refresh(new_rsvp)
        return new_rsvp

@router.get("/{event_id}/attendees", response_model=List[EventRSVPResponse])
async def get_attendees(
    event_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(EventRSVP).where(
        EventRSVP.event_id == event_id,
        EventRSVP.status == 'going'
    )
    result = await db.execute(query)
    return result.scalars().all()

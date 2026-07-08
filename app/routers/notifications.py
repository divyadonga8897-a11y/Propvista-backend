import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.models.models import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class NotificationOut(BaseModel):
    id: str
    title: str
    message: str
    notification_type: str
    is_read: bool
    reference_id: str | None
    created_at: str

@router.get("/", response_model=List[NotificationOut])
async def get_notifications(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == uid)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()
    
    return [
        NotificationOut(
            id=str(n.id),
            title=n.title,
            message=n.message,
            notification_type=n.notification_type,
            is_read=n.is_read,
            reference_id=n.reference_id,
            created_at=str(n.created_at)
        )
        for n in notifications
    ]

@router.put("/{notification_id}/read", response_model=dict)
async def mark_notification_read(
    notification_id: str,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    nid = uuid.UUID(notification_id)
    
    result = await db.execute(
        select(Notification).where(Notification.id == nid, Notification.user_id == uid)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notification.is_read = True
    await db.commit()
    
    return {"status": "success", "message": "Notification marked as read"}

@router.put("/read-all", response_model=dict)
async def mark_all_read(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    uid = uuid.UUID(current_user.user_id)
    
    result = await db.execute(select(Notification).where(Notification.user_id == uid, Notification.is_read == False))
    unread = result.scalars().all()
    
    for n in unread:
        n.is_read = True
        
    await db.commit()
    return {"status": "success", "message": f"{len(unread)} notifications marked as read"}

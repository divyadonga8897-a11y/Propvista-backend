import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import Notification

async def create_notification(
    db: AsyncSession,
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "General",
    reference_id: Optional[str] = None
):
    try:
        uid = uuid.UUID(user_id)
        notification = Notification(
            user_id=uid,
            title=title,
            message=message,
            notification_type=notification_type,
            reference_id=reference_id
        )
        db.add(notification)
        await db.commit()
    except Exception as e:
        print(f"Notification creation failed: {e}")
        pass

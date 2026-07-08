import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AuditLog

async def log_audit_action(
    db: AsyncSession,
    action: str,
    module: str,
    details: Optional[str] = None,
    user_id: Optional[str] = None
):
    try:
        uid = uuid.UUID(user_id) if user_id else None
        audit = AuditLog(
            user_id=uid,
            action=action,
            module=module,
            details=details
        )
        db.add(audit)
        await db.commit()
    except Exception as e:
        # Don't fail the main transaction if audit fails, just print/log
        print(f"Audit log failed: {e}")
        pass

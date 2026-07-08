from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.models.models import AuditLog, User

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])

class AuditLogOut(BaseModel):
    id: str
    user_id: str | None
    user_name: str | None
    action: str
    module: str
    details: str | None
    created_at: str

@router.get("/", response_model=List[AuditLogOut])
async def get_audit_logs(
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(
        select(AuditLog, User.full_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    rows = result.all()

    out = []
    for row in rows:
        log, name = row
        out.append(AuditLogOut(
            id=str(log.id),
            user_id=str(log.user_id) if log.user_id else None,
            user_name=name,
            action=log.action,
            module=log.module,
            details=log.details,
            created_at=str(log.created_at)
        ))
    return out

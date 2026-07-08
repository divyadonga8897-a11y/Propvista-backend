import uuid
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.models.models import Resident

async def verify_resident_access(
    apartment_id: uuid.UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserClaims:
    """
    Dependency to verify that the current user is a resident of the requested apartment.
    Admins bypass this check.
    """
    if current_user.role == "Admin":
        return current_user
        
    user_id = uuid.UUID(current_user.user_id)
    
    query = select(Resident).where(
        Resident.user_id == user_id,
        Resident.apartment_id == apartment_id
    )
    result = await db.execute(query)
    resident = result.scalar_one_or_none()
    
    if not resident:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this community's data."
        )
        
    return current_user

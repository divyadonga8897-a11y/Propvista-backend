import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import NoticeBoard
from app.schemas.schemas import NoticeBoardCreate, NoticeBoardResponse

from app.core.dependencies import verify_resident_access

router = APIRouter(prefix="/notices", tags=["Notice Board"])

@router.get("/{apartment_id}", response_model=List[NoticeBoardResponse])
async def get_notices(
    apartment_id: uuid.UUID,
    current_user: UserClaims = Depends(verify_resident_access),
    db: AsyncSession = Depends(get_db)
):
    query = select(NoticeBoard).where(
        NoticeBoard.apartment_id == apartment_id,
        NoticeBoard.is_active == True
    ).order_by(
        desc(NoticeBoard.is_pinned), desc(NoticeBoard.created_at)
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/", response_model=NoticeBoardResponse, status_code=status.HTTP_201_CREATED)
async def create_notice(
    apartment_id: uuid.UUID,
    notice: NoticeBoardCreate,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    new_notice = NoticeBoard(
        apartment_id=apartment_id,
        created_by=current_user.email,
        **notice.model_dump()
    )
    db.add(new_notice)
    await db.commit()
    await db.refresh(new_notice)
    return new_notice

@router.put("/{notice_id}", response_model=NoticeBoardResponse)
async def update_notice(
    notice_id: uuid.UUID,
    notice_update: NoticeBoardCreate,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(NoticeBoard).where(NoticeBoard.id == notice_id)
    result = await db.execute(query)
    notice = result.scalar_one_or_none()
    
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
        
    for key, value in notice_update.model_dump().items():
        setattr(notice, key, value)
        
    await db.commit()
    await db.refresh(notice)
    return notice

@router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(
    notice_id: uuid.UUID,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    query = select(NoticeBoard).where(NoticeBoard.id == notice_id)
    result = await db.execute(query)
    notice = result.scalar_one_or_none()
    
    if not notice:
        raise HTTPException(status_code=404, detail="Notice not found")
        
    await db.delete(notice)
    await db.commit()
    return None

import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.schemas import WishlistResponse, WishlistCreate
from app.services.real_estate_service import real_estate_service
from app.core.auth import get_current_user, UserClaims

router = APIRouter(prefix="/wishlist", tags=["wishlist"])

@router.get("", response_model=List[WishlistResponse])
async def list_wishlist(
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user)
):
    """Retrieve all wishlisted properties for the currently authenticated user."""
    user_uuid = uuid.UUID(user.user_id)
    return await real_estate_service.get_user_wishlist(db, user_uuid)

@router.post("", response_model=WishlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    wish_in: WishlistCreate,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user)
):
    """Add a unit to the authenticated user's wishlist."""
    user_uuid = uuid.UUID(user.user_id)
    return await real_estate_service.add_to_wishlist(db, user_uuid, wish_in.unit_id)

@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    unit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: UserClaims = Depends(get_current_user)
):
    """Remove a unit from the authenticated user's wishlist."""
    user_uuid = uuid.UUID(user.user_id)
    await real_estate_service.remove_from_wishlist(db, user_uuid, unit_id)

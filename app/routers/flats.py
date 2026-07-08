import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.services.real_estate_service import real_estate_service
from app.schemas.schemas import FlatCreate, FlatUpdate, FlatResponse, WishlistResponse, FlatStatusUpdate, FlatDuplicateRequest, FlatMoveRequest

router = APIRouter(prefix="/flats", tags=["Flats"])


@router.get("/", response_model=List[dict])
async def list_flats(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    apartment_id: Optional[uuid.UUID] = Query(None),
    floor_id: Optional[uuid.UUID] = Query(None),
    flat_type: Optional[str] = Query(None, description="e.g. 2BHK, 3BHK"),
    facing_direction: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    status: Optional[str] = Query(None, description="Available, Held, Booked, Sold, Rented"),
    listing_type: Optional[str] = Query(None, description="buy or rent"),
    sort_by: Optional[str] = Query(None, description="price_low, price_high, area"),
    db: AsyncSession = Depends(get_db),
):
    """List flats with optional filtering. Returns rich flat objects with floor/apartment context."""
    flats = await real_estate_service.get_flats(
        db,
        skip=skip,
        limit=limit,
        apartment_id=apartment_id,
        floor_id=floor_id,
        flat_type=flat_type,
        facing_direction=facing_direction,
        min_price=min_price,
        max_price=max_price,
        status=status,
        listing_type=listing_type,
        sort_by=sort_by,
    )
    return flats


@router.get("/{flat_id}", response_model=dict)
async def get_flat(flat_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single flat with full details including apartment context."""
    flat = await real_estate_service.get_flat_by_id(db, flat_id)
    return flat


@router.post("/", response_model=FlatResponse, status_code=status.HTTP_201_CREATED)
async def create_flat(
    floor_id: uuid.UUID,
    obj_in: FlatCreate,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Create a new flat in a floor."""
    flat = await real_estate_service.create_flat(db, floor_id, obj_in)
    return flat


@router.put("/{flat_id}", response_model=dict)
async def update_flat(
    flat_id: uuid.UUID,
    obj_in: FlatUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Update flat details or status."""
    flat = await real_estate_service.update_flat(db, flat_id, obj_in)
    return flat


@router.delete("/{flat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flat(flat_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Admin: Delete a flat."""
    await real_estate_service.delete_flat(db, flat_id)


@router.patch("/{flat_id}/status", response_model=dict)
async def change_flat_status(
    flat_id: uuid.UUID,
    obj_in: FlatStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Quickly change flat status."""
    return await real_estate_service.change_flat_status(db, flat_id, obj_in.status)


@router.post("/{flat_id}/duplicate", response_model=dict)
async def duplicate_flat(
    flat_id: uuid.UUID,
    obj_in: FlatDuplicateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Duplicate flat to another floor or with new flat number."""
    new_flat = await real_estate_service.duplicate_flat(db, flat_id, obj_in.target_floor_id, obj_in.new_flat_number)
    return await real_estate_service.get_flat_by_id(db, new_flat.id)


@router.post("/{flat_id}/move", response_model=dict)
async def move_flat(
    flat_id: uuid.UUID,
    obj_in: FlatMoveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Move flat to another floor."""
    return await real_estate_service.move_flat(db, flat_id, obj_in.target_floor_id)


@router.post("/{flat_id}/images", status_code=status.HTTP_201_CREATED)
async def add_flat_image(
    flat_id: uuid.UUID,
    image_url: str,
    image_type: Optional[str] = None,
    caption: Optional[str] = None,
    display_order: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Add an image to a flat."""
    img = await real_estate_service.add_flat_image(db, flat_id, image_url, display_order, image_type, caption)
    return {"id": img.id, "image_url": img.image_url, "display_order": img.display_order, "image_type": img.image_type, "caption": img.caption}


@router.delete("/{flat_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flat_image(
    flat_id: uuid.UUID,
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Admin: Delete flat image."""
    await real_estate_service.delete_flat_image(db, flat_id, image_id)


# Wishlist sub-router (user-specific)
wishlist_router = APIRouter(prefix="/wishlist", tags=["Wishlist"])


@wishlist_router.post("/{flat_id}", status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    flat_id: uuid.UUID,
    user_id: uuid.UUID,  # TODO: replace with JWT current user
    db: AsyncSession = Depends(get_db),
):
    wish = await real_estate_service.add_to_wishlist(db, user_id, flat_id)
    return {"message": "Added to wishlist", "id": wish.id}


@wishlist_router.delete("/{flat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    flat_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    await real_estate_service.remove_from_wishlist(db, user_id, flat_id)


@wishlist_router.get("/user/{user_id}")
async def get_user_wishlist(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    items = await real_estate_service.get_user_wishlist(db, user_id)
    return items

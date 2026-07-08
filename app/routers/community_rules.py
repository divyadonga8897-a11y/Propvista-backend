"""
community_rules.py - Community Rules management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from app.database.session import get_db
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin
from app.models.models import CommunityRule, Resident

router = APIRouter(prefix="/community-rules", tags=["Community Rules"])

# --- Schemas ---

class CommunityRuleOut(BaseModel):
    id: str
    apartment_id: str
    title: str
    description: str
    category: str
    display_order: int
    is_active: bool

class CreateRuleRequest(BaseModel):
    apartment_id: str
    title: str
    description: str
    category: str = "General"
    display_order: int = 0

class UpdateRuleRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

# --- Endpoints ---

@router.get(
    "/",
    response_model=List[CommunityRuleOut],
    summary="Get community rules",
    description="Returns community rules for the resident's apartment. Admins see all.",
)
async def get_rules(
    apartment_id: Optional[str] = None,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(CommunityRule).where(CommunityRule.is_active == True)
    
    if current_user.role != "Admin":
        uid = uuid.UUID(current_user.user_id)
        res_profile = await db.execute(select(Resident).where(Resident.user_id == uid))
        resident = res_profile.scalar_one_or_none()
        if not resident:
            return []
        query = query.where(CommunityRule.apartment_id == resident.apartment_id)
    else:
        if apartment_id:
            query = query.where(CommunityRule.apartment_id == uuid.UUID(apartment_id))
            
    query = query.order_by(CommunityRule.category, CommunityRule.display_order)
    res = await db.execute(query)
    rules = res.scalars().all()
    
    return [
        CommunityRuleOut(
            id=str(r.id),
            apartment_id=str(r.apartment_id),
            title=r.title,
            description=r.description,
            category=r.category,
            display_order=r.display_order,
            is_active=r.is_active
        )
        for r in rules
    ]


@router.post(
    "/",
    response_model=CommunityRuleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a community rule (Admin)",
)
async def create_rule(
    body: CreateRuleRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    rule = CommunityRule(
        apartment_id=uuid.UUID(body.apartment_id),
        title=body.title,
        description=body.description,
        category=body.category,
        display_order=body.display_order,
        is_active=True
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    return CommunityRuleOut(
        id=str(rule.id),
        apartment_id=str(rule.apartment_id),
        title=rule.title,
        description=rule.description,
        category=rule.category,
        display_order=rule.display_order,
        is_active=rule.is_active
    )


@router.put(
    "/{rule_id}",
    response_model=CommunityRuleOut,
    summary="Update a rule (Admin)",
)
async def update_rule(
    rule_id: str,
    body: UpdateRuleRequest,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    rid = uuid.UUID(rule_id)
    rule = await db.get(CommunityRule, rid)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    if body.title is not None:
        rule.title = body.title
    if body.description is not None:
        rule.description = body.description
    if body.category is not None:
        rule.category = body.category
    if body.display_order is not None:
        rule.display_order = body.display_order
    if body.is_active is not None:
        rule.is_active = body.is_active
        
    await db.commit()
    await db.refresh(rule)
    
    return CommunityRuleOut(
        id=str(rule.id),
        apartment_id=str(rule.apartment_id),
        title=rule.title,
        description=rule.description,
        category=rule.category,
        display_order=rule.display_order,
        is_active=rule.is_active
    )


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete community rule (Admin)",
)
async def delete_rule(
    rule_id: str,
    current_user: UserClaims = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    rid = uuid.UUID(rule_id)
    rule = await db.get(CommunityRule, rid)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return None

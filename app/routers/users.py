"""
users.py — User management endpoints (Admin only for most operations).
Business logic deferred to Stage 2.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from app.core.auth import get_current_user, UserClaims
from app.core.roles import require_admin

router = APIRouter(prefix="/users", tags=["Users"])


# ── Response Schemas ───────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    email: str
    role: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    created_at: str

class UserListResponse(BaseModel):
    users: List[UserOut]
    total: int

class UpdateRoleRequest(BaseModel):
    role: str  # Admin | Customer | Resident


# ── Endpoints ─────────────────────────────────────────────────

@router.get(
    "/",
    response_model=UserListResponse,
    summary="List all users (Admin)",
    description="Returns a paginated list of all registered users. Requires Admin role.",
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None, description="Filter by role: Admin, Customer, Resident"),
    current_user: UserClaims = Depends(require_admin),
):
    """Placeholder — Stage 2 will query the users table from Supabase."""
    return UserListResponse(users=[], total=0)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Get user by ID (Admin)",
)
async def get_user(
    user_id: str,
    current_user: UserClaims = Depends(require_admin),
):
    """Placeholder — Stage 2 will fetch from DB."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.patch(
    "/{user_id}/role",
    response_model=UserOut,
    summary="Update user role (Admin)",
    description="Promotes or demotes a user to Admin, Customer, or Resident.",
)
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    current_user: UserClaims = Depends(require_admin),
):
    """Placeholder — Stage 2 will update Supabase user metadata and DB."""
    if body.role not in ["Admin", "Customer", "Resident"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be one of: Admin, Customer, Resident"
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user (Admin)",
)
async def delete_user(
    user_id: str,
    current_user: UserClaims = Depends(require_admin),
):
    """Placeholder — Stage 2 will delete from Supabase Auth and DB."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

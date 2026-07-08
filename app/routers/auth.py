"""
auth.py — Authentication & user identity endpoints.
Uses Supabase JWT validation from core/auth.py.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.core.auth import get_current_user, UserClaims

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Response Schemas ───────────────────────────────────────────

class UserProfile(BaseModel):
    user_id: str
    email: str
    role: str
    full_name: str | None = None


class RegisterProfileRequest(BaseModel):
    full_name: str
    phone: str | None = None


# ── Endpoints ─────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get current authenticated user",
    description="Returns the profile of the currently authenticated user extracted from Supabase JWT.",
)
async def get_me(
    current_user: UserClaims = Depends(get_current_user),
):
    """
    Return currently authenticated user details.

    This endpoint is used by frontend after login
    to verify the session and load user role.
    """

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication failed",
        )

    metadata = current_user.raw_claims.get("user_metadata", {})

    return UserProfile(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role or "Customer",
        full_name=metadata.get("full_name"),
    )


@router.get(
    "/me/db-role",
    response_model=dict,
    summary="Get user role from database",
    description="Fetch current user role.",
)
async def get_me_db_role(
    current_user: UserClaims = Depends(get_current_user),
):
    """
    Temporary role response.

    Later replace with database lookup.
    """

    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role or "Customer",
    }


@router.post(
    "/register-profile",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
    summary="Complete user profile after registration",
)
async def register_profile(
    body: RegisterProfileRequest,
    current_user: UserClaims = Depends(get_current_user),
):
    """
    Complete user profile after Supabase signup.
    """

    return UserProfile(
        user_id=current_user.user_id,
        email=current_user.email,
        role=current_user.role or "Customer",
        full_name=body.full_name,
    )
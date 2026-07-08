import jwt
from typing import Dict, Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings


security = HTTPBearer(auto_error=False)


class UserClaims:
    def __init__(
        self,
        user_id: str,
        email: str,
        role: str,
        raw_claims: Dict[str, Any],
    ):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.raw_claims = raw_claims


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserClaims:
    """
    Validate Supabase JWT and extract user information.
    """

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    token = credentials.credentials


    # Development mode
    if not settings.SUPABASE_JWT_SECRET:

        if token == "mock-admin-token":
            return UserClaims(
                user_id="00000000-0000-0000-0000-000000000001",
                email="admin@propvista.com",
                role="Admin",
                raw_claims={},
            )

        if token == "mock-resident-token":
            return UserClaims(
                user_id="00000000-0000-0000-0000-000000000002",
                email="resident@propvista.com",
                role="Resident",
                raw_claims={},
            )

        if token == "mock-customer-token":
            return UserClaims(
                user_id="00000000-0000-0000-0000-000000000003",
                email="customer@propvista.com",
                role="Customer",
                raw_claims={},
            )


        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )

        except Exception:
            raise HTTPException(
                status_code=401,
                detail="Invalid development token",
            )


    # Production Supabase JWT validation
    else:

        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=[settings.ALGORITHM],
                audience="authenticated",
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token expired",
            )

        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
            )


    user_id = payload.get("sub")
    email = payload.get("email", "")


    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing user id",
        )


    # Supabase metadata
    user_metadata = payload.get("user_metadata") or {}
    app_metadata = payload.get("app_metadata") or {}


    role = (
        user_metadata.get("role")
        or app_metadata.get("role")
        or payload.get("role")
    )


    # Email fallback for testing
    if not role:
        admin_emails = [
            "divyadonga8897@gmail.com",
            "divyause2@gmail.com",
            "admin@propvista.com",
        ]
        resident_emails = [
            "resident@propvista.com",
        ]

        if email.lower() in admin_emails or email.lower().startswith("admin"):
            role = "Admin"
        elif email.lower() in resident_emails or email.lower().startswith("resident"):
            role = "Resident"
        else:
            role = "Customer"


    # Normalize
    role = str(role).strip().lower()


    role_map = {
        "admin": "Admin",
        "resident": "Resident",
        "customer": "Customer",
    }


    role = role_map.get(role, "Customer")


    return UserClaims(
        user_id=user_id,
        email=email,
        role=role,
        raw_claims=payload,
    )
import jwt
import uuid
from typing import Dict, Any, Optional

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings

jwks_client = jwt.PyJWKClient(settings.SUPABASE_JWKS_URL)

security = HTTPBearer(auto_error=False)  # auto_error=False to allow checking query param if header is missing


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
print(">>> get_current_user() is executing <<<")

from app.database.session import get_db

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> UserClaims:
    """
    Validate Supabase JWT and extract user information.
    Raises HTTP 401 on any authentication failure — no silent bypasses.
    Supports both Authorization Bearer header and token query parameter.
    """
    jwt_token = None
    if credentials:
        jwt_token = credentials.credentials
    elif token:
        jwt_token = token

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )

    token = jwt_token

    try:
        print("========== START AUTH ==========")

        header = jwt.get_unverified_header(token)
        print("HEADER:", header)

        signing_key = jwks_client.get_signing_key_from_jwt(token)
        print("Signing key found")

        payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["ES256"],
        options={
            "verify_signature": True,
            "verify_exp": True,
            "verify_aud": False,
        },
    )

        print("PAYLOAD:", payload)

    except Exception as e:
        import traceback

        print("\n========== FULL ERROR ==========")
        traceback.print_exc()
        print("ERROR TYPE:", type(e))
        print("ERROR:", e)
        print("================================")

        raise HTTPException(
            status_code=401,
            detail=str(e)
        )
        
        # 4. Validate issuer (Supabase tokens typically use full URL or 'supabase')
        iss = payload.get("iss")
        expected_issuer_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
        if iss not in ["supabase", expected_issuer_url]:
            raise jwt.InvalidTokenError(f"Invalid issuer: {iss}")
            
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        print("========== JWT ERROR ==========")
        print("TOKEN:", token[:40], "...")
        print("ERROR:", repr(e))
        print("===============================")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    email = payload.get("email", "")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing user identity (sub claim).",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Resolve role from DB first, fallback to Supabase JWT metadata ──────
    role = None
    from app.models.models import User
    try:
        user_uuid = uuid.UUID(user_id)
        # Note: We execute sync select or wait on async select inside async dependency
        # Since this is an async function, we can await DB operations.
        res = await db.execute(select(User).where(User.id == user_uuid))
        db_user = res.scalar_one_or_none()
        if db_user:
            role = db_user.role
    except Exception as e:
        print(f"Error fetching user role from DB inside auth: {e}")

    if not role:
        user_metadata = payload.get("user_metadata") or {}
        app_metadata = payload.get("app_metadata") or {}
        role = (
            user_metadata.get("role")
            or app_metadata.get("role")
            or payload.get("role")
        )

    # Email-based role fallback (for your known admin emails)
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

    # Normalize role string
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


async def get_or_create_db_user(db: AsyncSession, current_user: "UserClaims"):
    """
    Ensure the authenticated Supabase user exists in the local `users` table.
    Creates the record automatically on first booking/payment if missing.
    This bridges the gap between Supabase Auth and the local PostgreSQL users table.
    """
    from app.models.models import User

    user_uuid = uuid.UUID(current_user.user_id)
    res = await db.execute(select(User).where(User.id == user_uuid))
    user = res.scalar_one_or_none()

    if not user:
        # Auto-create user record synced from Supabase JWT claims
        full_name = (
            current_user.raw_claims.get("user_metadata", {}).get("full_name")
            or current_user.email.split("@")[0]
        )
        user = User(
            id=user_uuid,
            email=current_user.email,
            role=current_user.role,
            full_name=full_name,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
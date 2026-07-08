from typing import List
from fastapi import Depends
from app.core.auth import get_current_user, UserClaims
from app.core.exceptions import RoleAccessDeniedException

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        # Capitalize and store allowed roles
        self.allowed_roles = [r.capitalize() for r in allowed_roles]

    def __call__(self, current_user: UserClaims = Depends(get_current_user)) -> UserClaims:
        if current_user.role not in self.allowed_roles:
            raise RoleAccessDeniedException(required_roles=self.allowed_roles)
        return current_user

# Pre-defined dependencies for routes
require_admin = RoleChecker(["Admin"])
require_resident = RoleChecker(["Resident"])
require_customer = RoleChecker(["Customer"])

# Allowed combination dependencies
require_admin_or_resident = RoleChecker(["Admin", "Resident"])
require_any_user = RoleChecker(["Admin", "Resident", "Customer"])

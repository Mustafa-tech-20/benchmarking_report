"""
Authentication and Authorization Module
Industry-standard JWT-based RBAC implementation with MongoDB
"""

from .jwt_handler import (
    create_access_token,
    verify_token,
    get_current_user,
    require_role,
)
from .models import User, UserRole, TokenData
from .database import (
    connect_to_mongodb,
    close_mongodb_connection,
    get_database,
    create_user,
    get_user_by_email,
)

__all__ = [
    "create_access_token",
    "verify_token",
    "get_current_user",
    "require_role",
    "User",
    "UserRole",
    "TokenData",
    "connect_to_mongodb",
    "close_mongodb_connection",
    "get_database",
    "create_user",
    "get_user_by_email",
]

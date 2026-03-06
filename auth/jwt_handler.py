"""
JWT Token Handler with MongoDB Integration
Industry-standard JWT implementation following OAuth 2.0 best practices
Uses bcrypt directly for better Python 3.13 compatibility
"""

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, status, Cookie, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .models import User, UserRole, TokenData
from .database import get_user_by_email


# Security Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

# HTTP Bearer for token extraction
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


async def authenticate_user(email: str, password: str) -> Optional[User]:
    """
    Authenticate user with email and password from MongoDB

    Args:
        email: User email
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    # Fetch user from MongoDB
    user_data = await get_user_by_email(email)

    if not user_data:
        return None

    # Verify password
    if not verify_password(password, user_data["hashed_password"]):
        return None

    # Return User model
    return User(
        email=user_data["email"],
        role=UserRole(user_data["role"]),
        full_name=user_data.get("full_name"),
        is_active=user_data.get("is_active", True),
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Payload data to encode
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    })

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """
    Verify and decode JWT token

    Args:
        token: JWT token string

    Returns:
        TokenData with user info

    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        role: str = payload.get("role")

        if email is None or role is None:
            raise credentials_exception

        token_data = TokenData(email=email, role=UserRole(role))
        return token_data

    except JWTError:
        raise credentials_exception


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Cookie(None, alias="access_token"),
) -> User:
    """
    Get current authenticated user from JWT token (MongoDB backed)

    Checks both Authorization header and cookie for token

    Args:
        credentials: Bearer token from Authorization header
        token: Token from cookie

    Returns:
        Current user

    Raises:
        HTTPException: If authentication fails
    """
    # Try to get token from Authorization header first, then cookie
    jwt_token = None
    if credentials:
        jwt_token = credentials.credentials
    elif token:
        jwt_token = token

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = verify_token(jwt_token)

    # Get user from MongoDB
    user_data = await get_user_by_email(token_data.email)

    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    user = User(
        email=user_data["email"],
        role=UserRole(user_data["role"]),
        full_name=user_data.get("full_name"),
        is_active=user_data.get("is_active", True),
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


def require_role(*allowed_roles: UserRole):
    """
    Dependency to check if user has required role

    Usage:
        @app.get("/admin", dependencies=[Depends(require_role(UserRole.VB))])

    Args:
        allowed_roles: Roles that are allowed to access the endpoint

    Returns:
        Dependency function
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join([r.value for r in allowed_roles])}",
            )
        return current_user

    return role_checker

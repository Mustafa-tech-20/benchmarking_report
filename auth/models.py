"""
Authentication Data Models
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserRole(str, Enum):
    """User roles for RBAC"""
    VB = "VB"  # Vehicle Benchmarking
    PP = "PP"  # Product Planning
    VD = "VD"  # Vehicle Development


class User(BaseModel):
    """User model"""
    email: EmailStr
    role: UserRole
    full_name: Optional[str] = None
    is_active: bool = True


class TokenData(BaseModel):
    """JWT token payload"""
    email: str
    role: UserRole


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema"""
    access_token: str
    token_type: str = "bearer"
    user: User

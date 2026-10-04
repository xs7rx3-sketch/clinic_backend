from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: str = Field(..., description="Patient email address (case-insensitive)")
    password: Optional[str] = Field(None, description="Account password")
    auth_pin: Optional[str] = Field(None, description="Fast PIN login (4-6 digits)")


class UserProfile(BaseModel):
    id: str
    name_ar: str
    name_en: str
    email: Optional[str] = None
    phone: Optional[str] = None
    patient_type: str = "NORMAL"
    is_vip: bool = False
    official_title: Optional[str] = None
    delegation_name: Optional[str] = None
    protocol_officer_name: Optional[str] = None
    protocol_officer_phone: Optional[str] = None


class LoginResponse(BaseModel):
    status: str = "success"
    token: str
    user: UserProfile


class MeResponse(BaseModel):
    status: str = "success"
    user: UserProfile

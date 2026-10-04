import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.config import ACCESS_TOKEN_EXPIRE_DAYS, JWT_ALGORITHM, JWT_SECRET
from src.api.dependencies import get_current_user
from src.api.schemas.auth import LoginRequest, LoginResponse, MeResponse, UserProfile
from src.database.queries import authenticate_patient_credentials, record_patient_login

log = logging.getLogger("api.routers.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Authenticate patient or VIP dignitary by email and password/PIN."""
    if not req.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    user = authenticate_patient_credentials(
        email=req.email,
        password=req.password,
        auth_pin=req.auth_pin,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials / بيانات الدخول غير صحيحة",
        )

    patient_id = str(user["id"])
    record_patient_login(patient_id)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": patient_id,
        "email": user.get("email"),
        "name_ar": user.get("name_ar"),
        "name_en": user.get("name_en"),
        "patient_type": user.get("patient_type"),
        "is_vip": user.get("is_vip", False),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)).timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    profile = UserProfile(
        id=patient_id,
        name_ar=user.get("name_ar") or "",
        name_en=user.get("name_en") or "",
        email=user.get("email"),
        phone=user.get("phone"),
        patient_type=user.get("patient_type") or "NORMAL",
        is_vip=user.get("is_vip", False),
        official_title=user.get("official_title"),
        delegation_name=user.get("delegation_name"),
        protocol_officer_name=user.get("protocol_officer_name"),
        protocol_officer_phone=user.get("protocol_officer_phone"),
    )
    return LoginResponse(status="success", token=token, user=profile)


@router.get("/me", response_model=MeResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Validates the Bearer JWT token and returns current patient profile."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user session")

    profile = UserProfile(
        id=str(current_user["id"]),
        name_ar=current_user.get("name_ar") or "",
        name_en=current_user.get("name_en") or "",
        email=current_user.get("email"),
        phone=current_user.get("phone"),
        patient_type=current_user.get("patient_type") or "NORMAL",
        is_vip=current_user.get("is_vip", False),
        official_title=current_user.get("official_title"),
        delegation_name=current_user.get("delegation_name"),
        protocol_officer_name=current_user.get("protocol_officer_name"),
        protocol_officer_phone=current_user.get("protocol_officer_phone"),
    )
    return MeResponse(status="success", user=profile)

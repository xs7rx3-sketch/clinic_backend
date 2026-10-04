import logging
from typing import Any, Dict, Optional
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.ai.graph import AIGraph
from src.api.config import JWT_ALGORITHM, JWT_SECRET, LLM_API_KEY
from src.database.queries import fetch_patient_by_id

log = logging.getLogger("api.dependencies")

security = HTTPBearer(auto_error=False)

# Global LangGraph instance cache
_GRAPH_INSTANCE: Optional[Any] = None


async def get_ai_graph() -> Any:
    """Provides a singleton initialized LangGraph instance for the AI chat agent."""
    global _GRAPH_INSTANCE
    if _GRAPH_INSTANCE is None:
        log.info("Initializing LangGraph AI engine...")
        graph_wrapper = AIGraph(api_key=LLM_API_KEY)
        await graph_wrapper.setup(memory=None)
        _GRAPH_INSTANCE = graph_wrapper.llm_graph
        log.info("LangGraph AI engine initialized successfully.")
    return _GRAPH_INSTANCE


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired / انتهت صلاحية الجلسة",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e} / الرمز غير صالح",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Dict[str, Any]:
    """Extracts and verifies the authenticated patient profile from Bearer JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required / يرجى تسجيل الدخول",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_jwt_token(credentials.credentials)
    patient_id = payload.get("sub")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
        )

    user = fetch_patient_by_id(patient_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found / المستخدم غير موجود",
        )
    return user


async def get_current_vip(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Ensures the authenticated user has VIP privileges."""
    if not user.get("is_vip"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to VIP dignitaries and official delegations / مخصص للوفود والشخصيات الرسمية فقط",
        )
    return user

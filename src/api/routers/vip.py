from fastapi import APIRouter
from src.database.queries import fetch_vip_overview

router = APIRouter(prefix="/api/vip", tags=["VIP & Royal Protocol"])


@router.get("/overview")
async def get_vip_overview():
    """Retrieves official VIP secured department reservations and displaced appointment notices."""
    data = fetch_vip_overview()
    return {
        "status": "success",
        "vip_reservations": data.get("vip_reservations", []),
        "displaced_history": data.get("displaced_history", []),
        "active_delegations": data.get("active_delegations", []),
    }

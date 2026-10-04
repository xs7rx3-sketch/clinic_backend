from fastapi import APIRouter, Query
from src.database.queries import fetch_patient_appointments

router = APIRouter(prefix="/api", tags=["Appointments"])


@router.get("/patient/appointments")
async def get_patient_appointments(
    patient_id: str = Query(..., description="UUID of the patient"),
    limit: int = Query(25, ge=1, le=100),
):
    """Retrieves live appointments for a patient."""
    appointments = fetch_patient_appointments(patient_id=patient_id.strip(), limit=limit)
    return {"status": "success", "appointments": appointments}

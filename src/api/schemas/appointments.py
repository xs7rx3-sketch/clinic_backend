from typing import Any, List, Optional
from pydantic import BaseModel


class AppointmentItem(BaseModel):
    id: str
    doctor_id: str
    start_at: Any
    end_at: Any
    status: str
    reason_for_visit: Optional[str] = None
    is_vip_booking: bool = False
    notes: Optional[str] = None
    doctor_name_ar: Optional[str] = None
    doctor_name_en: Optional[str] = None
    specialty_ar: Optional[str] = None
    specialty_en: Optional[str] = None
    department_name_ar: Optional[str] = None
    department_name_en: Optional[str] = None


class PatientAppointmentsResponse(BaseModel):
    status: str = "success"
    appointments: List[AppointmentItem]

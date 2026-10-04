import os
import sys
import uuid
from typing import Any, Optional
from dotenv import load_dotenv

from sqlalchemy import delete, desc, or_, select
from src.database.connection import get_db_session
from src.database.models import (
    Appointment,
    AppointmentHistory,
    Department,
    Doctor,
    Patient,
)


# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))



class TestColors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(title: str):
    print(f"\n{TestColors.BOLD}{TestColors.CYAN}{'=' * 70}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.HEADER}  {title}{TestColors.RESET}")
    print(f"{TestColors.BOLD}{TestColors.CYAN}{'=' * 70}{TestColors.RESET}")


def print_success(msg: str):
    print(f"  {TestColors.GREEN}[PASS] {msg}{TestColors.RESET}")


def print_fail(msg: str):
    print(f"  {TestColors.RED}[FAIL] {msg}{TestColors.RESET}")


def print_info(msg: str):
    print(f"  {TestColors.BLUE}[INFO] {msg}{TestColors.RESET}")


def get_live_test_entities() -> dict[str, Any]:
    """Fetches real test entities from database via ORM to ensure genuine IDs."""
    with get_db_session() as session:
        # 1. Doctor (Active doctor with highest experience)
        doc = session.scalars(
            select(Doctor)
            .where(Doctor.is_active.is_(True))
            .order_by(desc(Doctor.experience_years))
            .limit(1)
        ).first()

        doctor = {
            "id": str(doc.id),
            "name_ar": doc.name_ar,
            "name_en": doc.name_en,
            "title_ar": doc.title_ar,
            "specialty_ar": doc.specialty_ar,
            "specialty_en": doc.specialty_en,
            "department_id": str(doc.department_id),
            "hospital_id": str(doc.hospital_id) if doc.hospital_id else None,
        } if doc else {}

        # 2. Department of that active doctor
        dept = session.get(Department, doc.department_id) if doc and doc.department_id else None
        department = {
            "id": str(dept.id),
            "name_ar": dept.name_ar,
            "name_en": dept.name_en,
            "code": dept.code,
            "hospital_id": str(dept.hospital_id) if dept and dept.hospital_id else None,
        } if dept else {}

        # 3. Hospital
        hospital = {
            "id": department.get("hospital_id"),
            "name_ar": "مستشفى الأمل التخصصي",
            "name_en": "Hope Specialized Hospital",
        }

        # 4. Regular patient
        p_norm = session.scalars(
            select(Patient).where(Patient.patient_type == "NORMAL").limit(1)
        ).first()
        normal_patient = {
            "id": str(p_norm.id),
            "name_ar": p_norm.name_ar,
            "name_en": p_norm.name_en,
            "phone": p_norm.phone,
            "patient_type": p_norm.patient_type,
        } if p_norm else {}

        # 5. VIP patient
        p_vip = session.scalars(
            select(Patient).where(Patient.patient_type == "VIP").limit(1)
        ).first()
        vip_patient = {
            "id": str(p_vip.id),
            "name_ar": p_vip.name_ar,
            "name_en": p_vip.name_en,
            "phone": p_vip.phone,
            "patient_type": p_vip.patient_type,
        } if p_vip else {}

        return {
            "hospital": hospital,
            "department": department,
            "doctor": doctor,
            "normal_patient": normal_patient,
            "vip_patient": vip_patient,
        }


def cleanup_test_appointments(test_tag: str = "TEST_RUN", appointment_ids: Optional[list[str]] = None):
    """Safely cleans up any appointments created with test notes, reason, or explicit IDs via ORM."""
    with get_db_session() as session:
        tag_pat = f"%{test_tag}%"
        appts = session.scalars(
            select(Appointment).where(
                or_(
                    Appointment.reason_for_visit.ilike(tag_pat),
                    Appointment.notes.ilike(tag_pat),
                )
            )
        ).all()
        ids = {a.id for a in appts}

        if appointment_ids:
            for aid in appointment_ids:
                try:
                    ids.add(uuid.UUID(str(aid).strip()))
                except Exception:
                    pass

        if ids:
            session.execute(delete(AppointmentHistory).where(AppointmentHistory.appointment_id.in_(ids)))
            session.execute(delete(Appointment).where(Appointment.id.in_(ids)))
            print_info(f"Cleaned up {len(ids)} test appointment record(s) via ORM.")

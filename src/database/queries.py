from datetime import datetime
from typing import Any, Optional
import uuid
from sqlalchemy import desc, func, or_, select
from src.database.connection import get_db_session
from src.database.models import (
    Appointment,
    AppointmentHistory,
    Department,
    Doctor,
    Patient,
    VipDelegation,
)


def _patient_to_dict(p: Patient) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name_ar": p.name_ar,
        "name_en": p.name_en,
        "email": p.email,
        "phone": p.phone,
        "national_id": p.national_id,
        "gender": p.gender,
        "patient_type": p.patient_type or "NORMAL",
        "is_vip": p.patient_type == "VIP",
        "official_title": p.official_title,
        "delegation_name": p.delegation_name,
        "protocol_officer_name": p.protocol_officer_name,
        "protocol_officer_phone": p.protocol_officer_phone,
        "is_verified": p.is_verified,
    }


def fetch_patient_by_id(patient_id: str) -> Optional[dict[str, Any]]:
    """Retrieves patient profile by identifier using ORM."""
    with get_db_session() as session:
        pid = uuid.UUID(str(patient_id).strip())
        patient = session.get(Patient, pid)
        return _patient_to_dict(patient) if patient else None


def authenticate_patient_credentials(
    email: str,
    password: Optional[str] = None,
    auth_pin: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Authenticates patient via email and password or fast PIN."""
    clean_email = email.strip().lower()
    with get_db_session() as session:
        patient = session.scalars(
            select(Patient).where(func.lower(Patient.email) == clean_email)
        ).first()
        if not patient:
            return None

        # Verify PIN
        if auth_pin and patient.auth_pin and str(patient.auth_pin).strip() == str(auth_pin).strip():
            return _patient_to_dict(patient)

        # Verify password using database crypt
        if password and patient.password_hash:
            is_valid = session.execute(
                select(func.crypt(password, patient.password_hash) == patient.password_hash)
            ).scalar()
            if is_valid:
                return _patient_to_dict(patient)

        return None


def record_patient_login(patient_id: str) -> bool:
    """Updates the last_login_at timestamp for a patient."""
    with get_db_session() as session:
        pid = uuid.UUID(str(patient_id).strip())
        patient = session.get(Patient, pid)
        if patient:
            patient.last_login_at = func.now()
            return True
        return False


def fetch_patient_appointments(patient_id: str, limit: int = 25) -> list[dict[str, Any]]:
    """Retrieves patient appointments with doctor and department details."""
    with get_db_session() as session:
        pid = uuid.UUID(str(patient_id).strip())
        stmt = (
            select(Appointment, Doctor, Department)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .join(Department, Appointment.department_id == Department.id)
            .where(Appointment.patient_id == pid)
            .order_by(desc(Appointment.start_at))
            .limit(limit)
        )
        results = session.execute(stmt).all()
        return [
            {
                "id": str(appt.id),
                "doctor_id": str(appt.doctor_id),
                "start_at": str(appt.start_at),
                "end_at": str(appt.end_at),
                "status": appt.status,
                "reason_for_visit": appt.reason_for_visit,
                "is_vip_booking": appt.is_vip_booking,
                "notes": appt.notes,
                "doctor_name_ar": doc.name_ar,
                "doctor_name_en": doc.name_en,
                "specialty_ar": doc.specialty_ar,
                "specialty_en": doc.specialty_en,
                "department_name_ar": dept.name_ar,
                "department_name_en": dept.name_en,
            }
            for appt, doc, dept in results
        ]


def fetch_catalog_data(doc_limit: int = 30) -> dict[str, Any]:
    """Retrieves active departments and active doctors."""
    with get_db_session() as session:
        depts = session.scalars(
            select(Department).where(Department.is_active.is_(True)).order_by(Department.name_ar)
        ).all()
        docs = session.execute(
            select(Doctor, Department)
            .join(Department, Doctor.department_id == Department.id)
            .where(Doctor.is_active.is_(True))
            .order_by(desc(Doctor.experience_years))
            .limit(doc_limit)
        ).all()

        return {
            "departments": [
                {
                    "id": str(d.id),
                    "name_ar": d.name_ar,
                    "name_en": d.name_en,
                    "code": d.code,
                    "floor_number": d.floor_number,
                    "default_slot_minutes": d.default_slot_minutes,
                    "is_vip_secured": d.is_vip_secured,
                }
                for d in depts
            ],
            "doctors": [
                {
                    "id": str(doc.id),
                    "name_ar": doc.name_ar,
                    "name_en": doc.name_en,
                    "title_ar": doc.title_ar,
                    "title_en": doc.title_en,
                    "specialty_ar": doc.specialty_ar,
                    "specialty_en": doc.specialty_en,
                    "experience_years": doc.experience_years,
                    "consultation_fee": doc.consultation_fee,
                    "is_vip_physician": doc.is_vip_physician,
                    "rating": doc.rating,
                    "department_name_ar": dept.name_ar,
                    "department_name_en": dept.name_en,
                }
                for doc, dept in docs
            ],
        }


def fetch_vip_overview() -> dict[str, Any]:
    """Retrieves VIP reservations, displaced appointment records, and active delegations."""
    with get_db_session() as session:
        vip_appts = session.execute(
            select(Appointment, Department, Patient)
            .join(Department, Appointment.department_id == Department.id)
            .join(Patient, Appointment.patient_id == Patient.id)
            .where(Appointment.is_vip_booking.is_(True))
            .order_by(desc(Appointment.start_at))
            .limit(10)
        ).all()

        delegations = session.execute(
            select(VipDelegation, Department, Patient)
            .join(Department, VipDelegation.department_id == Department.id)
            .join(Patient, VipDelegation.patient_id == Patient.id)
            .order_by(desc(VipDelegation.secured_start_at))
            .limit(10)
        ).all()

        history_rows = session.execute(
            select(AppointmentHistory, Appointment, Patient, Doctor, Department)
            .join(Appointment, AppointmentHistory.appointment_id == Appointment.id)
            .join(Patient, Appointment.patient_id == Patient.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .join(Department, Appointment.department_id == Department.id)
            .where(
                or_(
                    AppointmentHistory.notes.ilike("%VIP%"),
                    AppointmentHistory.notes.ilike("%Displaced%"),
                    AppointmentHistory.notes.ilike("%إزاحة%"),
                )
            )
            .order_by(desc(AppointmentHistory.created_at))
            .limit(15)
        ).all()

        return {
            "vip_reservations": [
                {
                    "id": str(a.id),
                    "start_at": str(a.start_at),
                    "end_at": str(a.end_at),
                    "status": a.status,
                    "reason_for_visit": a.reason_for_visit,
                    "notes": a.notes,
                    "department_name_ar": dept.name_ar,
                    "vip_name": p.name_ar,
                }
                for a, dept, p in vip_appts
            ],
            "displaced_history": [
                {
                    "id": str(h.id),
                    "appointment_id": str(h.appointment_id),
                    "action": h.action,
                    "old_start_at": str(h.old_start_at),
                    "new_start_at": str(h.new_start_at),
                    "notes": h.notes,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                    "patient_name": p.name_ar,
                    "doctor_name": doc.name_ar,
                    "department_name": dept.name_ar,
                }
                for h, a, p, doc, dept in history_rows
            ],
            "active_delegations": [
                {
                    "id": str(d.id),
                    "delegation_title": d.delegation_title,
                    "secured_start_at": str(d.secured_start_at),
                    "secured_end_at": str(d.secured_end_at),
                    "status": d.status,
                    "displaced_count": d.displaced_count,
                    "department_name_ar": dept.name_ar,
                    "vip_name": p.name_ar,
                }
                for d, dept, p in delegations
            ],
        }


def resolve_department_id(identifier: Optional[str]) -> Optional[str]:
    """Resolves department UUID from an ID string, English name, or Arabic name via ORM."""
    dept = find_department(identifier)
    return dept["id"] if dept else None


def find_department(dept_identifier: Optional[str]) -> Optional[dict[str, Any]]:
    """Resolves department by UUID or case-insensitive Arabic/English name via ORM."""
    if not dept_identifier:
        return None
    raw = str(dept_identifier).strip()
    with get_db_session() as session:
        if len(raw) == 36 and "-" in raw:
            dept = session.get(Department, uuid.UUID(raw))
        else:
            pat = f"%{raw}%"
            dept = session.scalars(
                select(Department).where(
                    Department.is_active.is_(True),
                    or_(
                        Department.name_ar.ilike(pat),
                        Department.name_en.ilike(pat),
                        Department.code.ilike(pat),
                    ),
                ).limit(1)
            ).first()

        if not dept:
            return None

        return {
            "id": str(dept.id),
            "hospital_id": str(dept.hospital_id) if dept.hospital_id else None,
            "name_ar": dept.name_ar,
            "name_en": dept.name_en,
            "code": dept.code,
        }


def get_senior_doctor_by_department(dept_id: str) -> Optional[str]:
    """Finds the most experienced active doctor in a department via ORM."""
    if not dept_id:
        return None
    with get_db_session() as session:
        stmt = (
            select(Doctor.id)
            .where(Doctor.department_id == uuid.UUID(str(dept_id).strip()), Doctor.is_active.is_(True))
            .order_by(desc(Doctor.experience_years))
            .limit(1)
        )
        doc_id = session.execute(stmt).scalar()
        return str(doc_id) if doc_id else None


def insert_appointment(
    hid: Optional[str],
    dept_id: str,
    did: Optional[str],
    pid: str,
    start_at: str,
    end_at: str,
    reason: str,
    is_vip: bool = False,
    notes: Optional[str] = None,
    booking_source: Optional[str] = None,
) -> dict[str, Any]:
    """Inserts a new confirmed appointment via ORM."""
    with get_db_session() as session:
        dept_uuid = uuid.UUID(str(dept_id).strip())
        dept = session.get(Department, dept_uuid)
        h_uuid = uuid.UUID(str(hid).strip()) if hid else (dept.hospital_id if dept else None)
        source = booking_source or ("VIP_LIAISON" if is_vip else "FLUTTER_APP")

        appt = Appointment(
            hospital_id=h_uuid,
            department_id=dept_uuid,
            doctor_id=uuid.UUID(str(did).strip()) if did else None,
            patient_id=uuid.UUID(str(pid).strip()),
            start_at=datetime.fromisoformat(str(start_at).replace("T", " ")[:19]),
            end_at=datetime.fromisoformat(str(end_at).replace("T", " ")[:19]),
            status="CONFIRMED",
            booking_source=source,
            is_vip_booking=is_vip,
            reason_for_visit=reason,
            notes=notes,
        )
        session.add(appt)
        session.flush()
        return {
            "id": str(appt.id),
            "start_at": str(appt.start_at),
            "end_at": str(appt.end_at),
            "status": appt.status,
        }


def record_appointment_history(
    appt_id: str,
    action: str,
    old_start_at: Optional[str] = None,
    new_start_at: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    """Records an audit log entry for an appointment action via ORM."""
    with get_db_session() as session:
        hist = AppointmentHistory(
            appointment_id=uuid.UUID(str(appt_id).strip()),
            action=action,
            old_start_at=datetime.fromisoformat(str(old_start_at).replace("T", " ")[:19]) if old_start_at and old_start_at != "None" else None,
            new_start_at=datetime.fromisoformat(str(new_start_at).replace("T", " ")[:19]) if new_start_at and new_start_at != "None" else None,
            old_status=old_status,
            new_status=new_status,
            notes=notes,
        )
        session.add(hist)


def cancel_appointment(appt_id: str) -> None:
    """Cancels an appointment via ORM."""
    with get_db_session() as session:
        aid = uuid.UUID(str(appt_id).strip())
        appt = session.get(Appointment, aid)
        if appt:
            appt.status = "CANCELLED"
            appt.updated_at = func.now()


def reschedule_appointment(appt_id: str, start_at: str, end_at: str) -> None:
    """Reschedules an appointment to a new time window via ORM."""
    with get_db_session() as session:
        aid = uuid.UUID(str(appt_id).strip())
        appt = session.get(Appointment, aid)
        if appt:
            appt.start_at = datetime.fromisoformat(str(start_at).replace("T", " ")[:19])
            appt.end_at = datetime.fromisoformat(str(end_at).replace("T", " ")[:19])
            appt.status = "CONFIRMED"
            appt.updated_at = func.now()


def get_overlapping_appointments(dept_id: str, start_at: str, end_at: str) -> list[dict[str, Any]]:
    """Finds appointments overlapping with a specific window in a department via ORM."""
    if not dept_id:
        return []
    with get_db_session() as session:
        s_dt = datetime.fromisoformat(str(start_at).replace("T", " ")[:19])
        e_dt = datetime.fromisoformat(str(end_at).replace("T", " ")[:19])
        d_id = uuid.UUID(str(dept_id).strip())
        stmt = (
            select(Appointment, Patient, Doctor, Department)
            .join(Patient, Appointment.patient_id == Patient.id)
            .join(Doctor, Appointment.doctor_id == Doctor.id)
            .join(Department, Appointment.department_id == Department.id)
            .where(
                Appointment.department_id == d_id,
                Appointment.start_at < e_dt,
                Appointment.end_at > s_dt,
                ~Appointment.status.in_(["CANCELLED", "NO_SHOW"]),
                Appointment.is_vip_booking.is_(False),
            )
        )
        rows = session.execute(stmt).all()
        return [
            {
                "id": str(a.id),
                "patient_id": str(a.patient_id),
                "doctor_id": str(a.doctor_id),
                "start_at": str(a.start_at),
                "end_at": str(a.end_at),
                "patient_name": p.name_ar,
                "patient_phone": p.phone,
                "doctor_name": doc.name_ar,
                "department_name": dept.name_ar,
            }
            for a, p, doc, dept in rows
        ]


def search_clinical_entities(search_term: Optional[str] = None, hospital_id: Optional[str] = None) -> dict[str, Any]:
    """Finds matching active departments and doctors via ORM."""
    clean = (search_term or "").strip()
    with get_db_session() as session:
        dept_stmt = select(Department).where(Department.is_active.is_(True))
        doc_stmt = (
            select(Doctor, Department)
            .join(Department, Doctor.department_id == Department.id)
            .where(Doctor.is_active.is_(True))
        )

        if hospital_id:
            h_uuid = uuid.UUID(str(hospital_id).strip()) if (len(str(hospital_id)) == 36 and "-" in str(hospital_id)) else None
            if h_uuid:
                dept_stmt = dept_stmt.where(Department.hospital_id == h_uuid)
                doc_stmt = doc_stmt.where(Department.hospital_id == h_uuid)

        if clean:
            pat = f"%{clean}%"
            dept_stmt = dept_stmt.where(
                or_(
                    Department.name_ar.ilike(pat),
                    Department.name_en.ilike(pat),
                    Department.code.ilike(pat),
                )
            )
            doc_stmt = doc_stmt.where(
                or_(
                    Doctor.name_ar.ilike(pat),
                    Doctor.name_en.ilike(pat),
                    Doctor.specialty_ar.ilike(pat),
                    Doctor.specialty_en.ilike(pat),
                )
            )

        depts = session.scalars(dept_stmt.order_by(Department.name_ar).limit(20)).all()
        docs = session.execute(doc_stmt.order_by(desc(Doctor.experience_years)).limit(10)).all()

        return {
            "departments": [
                {"id": str(d.id), "name_ar": d.name_ar, "name_en": d.name_en, "code": d.code}
                for d in depts
            ],
            "doctors": [
                {
                    "id": str(doc.id),
                    "name_ar": doc.name_ar,
                    "name_en": doc.name_en,
                    "title_ar": doc.title_ar,
                    "title_en": doc.title_en,
                    "specialty_ar": doc.specialty_ar,
                    "specialty_en": doc.specialty_en,
                    "department_id": str(doc.department_id),
                    "department_name": dept.name_ar,
                    "experience_years": doc.experience_years,
                }
                for doc, dept in docs
            ],
        }


def search_doctors(term: str, department_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Searches active doctors by UUID or name/specialty via ORM."""
    clean = str(term or "").strip()
    with get_db_session() as session:
        stmt = (
            select(Doctor, Department)
            .join(Department, Doctor.department_id == Department.id)
            .where(Doctor.is_active.is_(True))
        )
        if len(clean) == 36 and "-" in clean:
            stmt = stmt.where(Doctor.id == uuid.UUID(clean))
        elif clean:
            pattern = f"%{clean}%"
            stmt = stmt.where(
                or_(
                    Doctor.name_ar.ilike(pattern),
                    Doctor.name_en.ilike(pattern),
                    Doctor.specialty_ar.ilike(pattern),
                    Doctor.specialty_en.ilike(pattern),
                )
            )
        if department_id:
            dept_uuid = resolve_department_id(department_id)
            if dept_uuid:
                stmt = stmt.where(Doctor.department_id == uuid.UUID(dept_uuid))

        rows = session.execute(stmt.limit(10)).all()
        return [
            {
                "id": str(doc.id),
                "name_ar": doc.name_ar,
                "name_en": doc.name_en,
                "title_ar": doc.title_ar,
                "title_en": doc.title_en,
                "specialty_ar": doc.specialty_ar,
                "specialty_en": doc.specialty_en,
                "department_id": str(doc.department_id),
                "department_name": dept.name_ar,
                "experience_years": doc.experience_years,
            }
            for doc, dept in rows
        ]


def get_doctors_with_workload(
    department_id: Optional[str] = None,
    specialty: Optional[str] = None,
    target_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Retrieves active doctors with their booked appointment counts on target_date via ORM."""
    with get_db_session() as session:
        stmt = (
            select(Doctor, Department)
            .join(Department, Doctor.department_id == Department.id)
            .where(Doctor.is_active.is_(True))
        )
        if department_id:
            dept_uuid = resolve_department_id(department_id)
            if dept_uuid:
                stmt = stmt.where(Doctor.department_id == uuid.UUID(dept_uuid))
        if specialty:
            pat = f"%{specialty.strip()}%"
            stmt = stmt.where(or_(Doctor.specialty_ar.ilike(pat), Doctor.specialty_en.ilike(pat)))

        docs = session.execute(stmt).all()
        day_str = (target_date or datetime.now().strftime("%Y-%m-%d"))[:10]
        day_start = datetime.fromisoformat(f"{day_str} 00:00:00")
        day_end = datetime.fromisoformat(f"{day_str} 23:59:59")

        results = []
        for doc, dept in docs:
            cnt = session.scalar(
                select(func.count(Appointment.id)).where(
                    Appointment.doctor_id == doc.id,
                    Appointment.start_at >= day_start,
                    Appointment.start_at <= day_end,
                    ~Appointment.status.in_(["CANCELLED", "NO_SHOW"]),
                )
            ) or 0
            results.append({
                "id": str(doc.id),
                "name_ar": doc.name_ar,
                "name_en": doc.name_en,
                "title_ar": doc.title_ar,
                "title_en": doc.title_en,
                "specialty_ar": doc.specialty_ar,
                "specialty_en": doc.specialty_en,
                "department_id": str(doc.department_id),
                "department_name": dept.name_ar,
                "experience_years": doc.experience_years,
                "current_day_appointments_count": cnt,
            })
        return results


def get_doctor_conflicts(
    doctor_id: str,
    start_at: str,
    end_at: str,
    exclude_appointment_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Checks for overlapping active appointments for a doctor in the given slot via ORM."""
    if not doctor_id:
        return []
    with get_db_session() as session:
        doc_uuid = uuid.UUID(str(doctor_id).strip())
        s_dt = datetime.fromisoformat(str(start_at).replace("T", " ")[:19])
        e_dt = datetime.fromisoformat(str(end_at).replace("T", " ")[:19])

        stmt = select(Appointment).where(
            Appointment.doctor_id == doc_uuid,
            Appointment.start_at < e_dt,
            Appointment.end_at > s_dt,
            ~Appointment.status.in_(["CANCELLED", "NO_SHOW"]),
        )
        if exclude_appointment_id:
            stmt = stmt.where(Appointment.id != uuid.UUID(str(exclude_appointment_id).strip()))

        appts = session.scalars(stmt).all()
        return [
            {
                "id": str(a.id),
                "start_at": str(a.start_at),
                "end_at": str(a.end_at),
                "status": a.status,
            }
            for a in appts
        ]


def get_department_doctors(department_id: str) -> list[dict[str, Any]]:
    """Retrieves all active doctors in a department via ORM."""
    dept_uuid = resolve_department_id(department_id)
    if not dept_uuid:
        return []
    with get_db_session() as session:
        docs = session.execute(
            select(Doctor, Department)
            .join(Department, Doctor.department_id == Department.id)
            .where(Doctor.department_id == uuid.UUID(dept_uuid), Doctor.is_active.is_(True))
            .order_by(desc(Doctor.experience_years))
        ).all()
        return [
            {
                "id": str(doc.id),
                "name_ar": doc.name_ar,
                "name_en": doc.name_en,
                "title_ar": doc.title_ar,
                "title_en": doc.title_en,
                "specialty_ar": doc.specialty_ar,
                "specialty_en": doc.specialty_en,
                "experience_years": doc.experience_years,
                "department_name": dept.name_ar,
            }
            for doc, dept in docs
        ]


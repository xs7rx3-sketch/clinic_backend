from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator

from src.ai.enums import (
    AppointmentStatus,
    NextRecommendedAction,
    NodeName,
    SQLActionType,
    SQLReportStatus,
)


# ----------------------------------------------------------------------
# 1. Specialized Node Input Schemas
# ----------------------------------------------------------------------

class GetValuesInput(BaseModel):
    """Input parameters for get_values node."""
    query: str = Field(
        description="Search term or entity to lookup (e.g. department name, specialty, doctor title)."
    )
    hospital_id: Optional[str] = Field(
        default=None,
        description="Optional hospital UUID scope."
    )


class GetAppointmentsInput(BaseModel):
    """Input parameters for get_appointments node."""
    query: Optional[str] = Field(
        default=None,
        description="Task or query description regarding schedules or availability."
    )
    hospital_id: Optional[str] = Field(
        default=None,
        description="Optional hospital UUID."
    )
    patient_id: Optional[str] = Field(
        default=None,
        description="Optional patient UUID to view their booked appointments."
    )
    department_id: Optional[str] = Field(
        default=None,
        description="Optional department UUID."
    )
    doctor_id: Optional[str] = Field(
        default=None,
        description="Optional doctor UUID to inspect schedule."
    )
    doctor: Optional[str] = Field(
        default=None,
        description="Optional doctor name or query to inspect schedule (e.g. 'د. فلان' or 'Dr. Example')."
    )
    date_or_range: Optional[str] = Field(
        default=None,
        description="Target date (YYYY-MM-DD) or datetime range."
    )


class RecommendDoctorInput(BaseModel):
    """Input parameters for recommend_doctor node."""
    department_id: Optional[str] = Field(
        default=None,
        description="Target department UUID."
    )
    specialty: Optional[str] = Field(
        default=None,
        description="Target medical specialty (e.g. Cardiology, Pediatrics, Dermatology)."
    )
    preferred_date: Optional[str] = Field(
        default=None,
        description="Target date for the consultation (YYYY-MM-DD)."
    )
    hospital_id: Optional[str] = Field(
        default=None,
        description="Optional hospital UUID."
    )


class ReserveAppointmentInput(BaseModel):
    """Input parameters for reserve_appointment node."""
    department_id: Optional[str] = Field(
        default=None,
        description="Department UUID for the appointment. Auto-filled from doctor if omitted."
    )
    doctor_id: Optional[str] = Field(
        default=None,
        description="Selected doctor UUID."
    )
    doctor: Optional[str] = Field(
        default=None,
        description="Doctor name or search query to resolve if doctor_id is unknown (e.g. 'د. فلان' or 'Dr. Example')."
    )
    start_at: str = Field(
        description="ISO 8601 start datetime string (e.g. 2026-10-01T10:00:00)."
    )
    end_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 end datetime string. If omitted, defaults to start_at + 30 minutes."
    )
    patient_id: Optional[str] = Field(
        default=None,
        description="Patient UUID. If omitted, auto-filled from authenticated patient context."
    )
    hospital_id: Optional[str] = Field(
        default=None,
        description="Hospital UUID. If omitted, auto-filled from authenticated patient context."
    )
    reason_for_visit: Optional[str] = Field(
        default=None,
        description="Brief medical reason or notes for the consultation."
    )
    booking_source: Optional[str] = Field(
        default=None,
        description="Booking channel, e.g. FLUTTER_APP, VOICE_AI, WEB, VIP_LIAISON, DASHBOARD."
    )

    @model_validator(mode="after")
    def validate_doctor_present(self) -> "ReserveAppointmentInput":
        if not self.doctor_id and not self.doctor:
            raise ValueError("Either doctor_id or doctor name must be provided.")
        return self


class ModifyAppointmentInput(BaseModel):
    """Input parameters for modify_appointment node."""
    appointment_id: Optional[str] = Field(
        default=None,
        description="Existing appointment UUID to reschedule or cancel. Can be auto-resolved from patient if omitted."
    )
    query: Optional[str] = Field(
        default=None,
        description="Optional description or query to locate the appointment."
    )
    new_start_at: Optional[str] = Field(
        default=None,
        description="New requested ISO start datetime string if rescheduling."
    )
    new_end_at: Optional[str] = Field(
        default=None,
        description="New requested ISO end datetime string. If omitted, defaults to new_start_at + 30 minutes."
    )
    new_status: Optional[AppointmentStatus] = Field(
        default=None,
        description="Target status if updating (e.g. RESCHEDULED, CANCELLED)."
    )
    notes: Optional[str] = Field(
        default=None,
        description="Reason for rescheduling or cancellation."
    )


class VIPDisplacementInput(BaseModel):
    """Input parameters for vip_displacement node."""
    department_id: Optional[str] = Field(
        default=None,
        description="Target department UUID to reserve exclusively for the VIP visit."
    )
    department: Optional[str] = Field(
        default=None,
        description="Target department name or specialty (e.g. 'أمراض وجراحة القلب', 'Cardiology')."
    )
    start_at: str = Field(
        description="ISO 8601 start datetime of the official VIP visit window."
    )
    end_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 end datetime of the VIP visit window. If omitted, defaults to start_at + 2 hours."
    )
    vip_patient_id: Optional[str] = Field(
        default=None,
        description="VIP / Dignitary patient UUID."
    )
    hospital_id: Optional[str] = Field(
        default=None,
        description="Hospital UUID."
    )
    notes: Optional[str] = Field(
        default=None,
        description="Official delegation or protocol visit notes."
    )
    booking_source: Optional[str] = Field(
        default="VIP_LIAISON",
        description="Booking channel, e.g. VIP_LIAISON, DASHBOARD."
    )

    @model_validator(mode="after")
    def validate_department_present(self) -> "VIPDisplacementInput":
        if not self.department_id and not self.department:
            raise ValueError("Either department_id or department name must be provided.")
        return self



# ----------------------------------------------------------------------
# 2. Central Router Decision Schema
# ----------------------------------------------------------------------

class NodeDecision(BaseModel):
    """Decision produced by the central React Controller using Chain of Thought reasoning."""
    thought: str = Field(
        description="Step-by-step reasoning (Chain of Thought): 1) User request analysis, 2) History inspection for previous node outputs, 3) Conflict/loop check, 4) Justification for next step."
    )
    next_node: NodeName = Field(
        description="The specialized node to execute next, or 'end' if ready to speak directly to the user."
    )
    node_input: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters dictionary to pass to the chosen node, conforming to that node's input schema."
    )
    response_to_user: Optional[str] = Field(
        default=None,
        description="The spoken or text response to the user when next_node is 'end'."
    )


# ----------------------------------------------------------------------
# 3. Standardized Node Output & Report Schemas
# ----------------------------------------------------------------------

class SQLNodeOutputReport(BaseModel):
    """Standardized deterministic JSON report emitted by SQL Specialist nodes."""
    status: SQLReportStatus = Field(
        description="Status of the executed SQL operation."
    )
    action: SQLActionType = Field(
        description="The domain action performed."
    )
    summary: str = Field(
        description="Concise factual summary for the React controller."
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Specific structured payload of the operation."
    )
    next_recommended_action: Optional[NextRecommendedAction] = Field(
        default=NextRecommendedAction.NONE,
        description="Hint for the next action: reserve, clarify, offer_alternatives, or none."
    )


# ----------------------------------------------------------------------
# 4. Specialized AI Specialist Pydantic Structured Output Schemas
# ----------------------------------------------------------------------

class AlternativeSlot(BaseModel):
    """Alternative 30-minute open appointment slot."""
    start_at: str = Field(description="ISO start datetime (YYYY-MM-DD HH:MM:SS)")
    end_at: str = Field(description="ISO end datetime (YYYY-MM-DD HH:MM:SS)")


class SlotAvailabilityReport(BaseModel):
    """Structured availability assessment produced by the AI Specialist."""
    status: SQLReportStatus = Field(description="SUCCESS if slot is free, CONFLICT if occupied")
    is_available: bool = Field(description="True if requested slot has zero conflicts")
    summary: str = Field(description="Factual, clear explanation of slot status")
    suggested_alternative_slots: list[AlternativeSlot] = Field(
        default_factory=list, description="2 to 3 alternative open time slots if conflict exists"
    )
    next_recommended_action: NextRecommendedAction = Field(
        default=NextRecommendedAction.RESERVE, description="Suggested next action (RESERVE if available, OFFER_ALTERNATIVES if conflict)"
    )


class RecommendedDoctorInfo(BaseModel):
    """Detailed profile of the top recommended doctor."""
    id: str = Field(description="Doctor UUID")
    name_en: str = Field(description="Doctor full English name")
    name_ar: str = Field(description="Doctor full Arabic name")
    title_ar: Optional[str] = Field(default=None, description="Doctor professional title in Arabic (e.g. استشاري, أخصائي)")
    title_en: Optional[str] = Field(default=None, description="Doctor professional title in English")
    specialty_ar: Optional[str] = Field(default=None, description="Medical specialty in Arabic")
    specialty_en: Optional[str] = Field(default=None, description="Medical specialty in English")
    experience_years: int = Field(description="Years of clinical experience")
    current_day_appointments_count: int = Field(description="Booked appointments count on requested date")
    reason_for_recommendation: str = Field(
        description="Clinical rationale explaining why this doctor is best suited (lowest workload, seniority)"
    )


class DoctorRecommendationReport(BaseModel):
    """Structured recommendation produced by the AI Doctor Allocation Specialist."""
    status: SQLReportStatus = Field(description="SUCCESS if doctor selected, NOT_FOUND if no candidates match")
    action: SQLActionType = Field(default=SQLActionType.RECOMMEND_DOCTOR)
    summary: str = Field(description="Concise factual summary of the recommendation")
    recommended_doctor: Optional[RecommendedDoctorInfo] = Field(
        default=None, description="The top recommended doctor"
    )
    alternative_doctors: list[dict[str, Any]] = Field(
        default_factory=list, description="Other qualified doctors from candidate pool"
    )
    next_recommended_action: NextRecommendedAction = Field(
        default=NextRecommendedAction.RESERVE, description="Next suggested operational step"
    )


class DisplacedPatientNotification(BaseModel):
    """Empathetic, personalized notification for a patient whose appointment was moved."""
    patient_name: str = Field(description="Patient full name")
    phone: Optional[str] = Field(default=None, description="Patient contact phone")
    notification_ar: str = Field(
        description="Courteous, reassuring notification in Arabic explaining rescheduling due to administrative reasons, mentioning doctor and new time"
    )
    notification_en: Optional[str] = Field(
        default=None, description="Courteous notification in English"
    )


class RescheduledPatientSlot(BaseModel):
    """AI-determined rescheduled appointment slot and patient notice."""
    appointment_id: str = Field(description="UUID of the original displaced appointment")
    patient_name: str = Field(description="Name of patient")
    new_start_at: str = Field(description="AI-selected optimal new start datetime (YYYY-MM-DD HH:MM:SS)")
    new_end_at: str = Field(description="AI-selected optimal new end datetime (YYYY-MM-DD HH:MM:SS)")
    reasoning: Optional[str] = Field(default=None, description="Operational reasoning for choosing this slot")
    notification_ar: str = Field(
        description="Empathetic, reassuring notification in Arabic explaining rescheduling, citing doctor and new time"
    )
    notification_en: Optional[str] = Field(
        default=None, description="Courteous notification in English"
    )


class VIPDisplacementAIResult(BaseModel):
    """High-protocol VIP strategic plan and empathetic patient communications."""
    selected_doctor_id: Optional[str] = Field(
        default=None, description="Doctor UUID chosen by AI to receive the VIP delegation based on seniority and clinical protocol"
    )
    rescheduled_slots: list[RescheduledPatientSlot] = Field(
        default_factory=list, description="AI-calculated optimal rescheduling for each affected patient"
    )
    summary: str = Field(description="Official summary of the secured department window and patient rescheduling")
    patient_notifications: list[DisplacedPatientNotification] = Field(
        default_factory=list, description="Personalized notifications for each affected patient"
    )
    next_recommended_action: NextRecommendedAction = Field(
        default=NextRecommendedAction.NONE, description="Next operational step"
    )


class CatalogLookupResult(BaseModel):
    """Dynamic clinical interpretation of catalog and entity lookups."""
    status: SQLReportStatus = Field(description="SUCCESS if relevant clinical entities found, NOT_FOUND if none")
    summary: str = Field(description="Dynamic, informative clinical summary answering the user's inquiry")
    matched_departments: list[dict[str, Any]] = Field(default_factory=list, description="Relevant departments found")
    matched_doctors: list[dict[str, Any]] = Field(default_factory=list, description="Relevant doctors found")
    next_recommended_action: NextRecommendedAction = Field(
        default=NextRecommendedAction.NONE, description="Next suggested operational step (e.g. RESERVE or CLARIFY)"
    )


class PatientAppointmentsSummaryResult(BaseModel):
    """AI summary of patient's booked appointments."""
    status: SQLReportStatus = Field(description="SUCCESS if appointments retrieved, NOT_FOUND if zero")
    summary: str = Field(description="Polite, clear overview of the patient's schedule and next actions")
    next_recommended_action: NextRecommendedAction = Field(default=NextRecommendedAction.NONE)



class ReservationReportResult(BaseModel):
    """Structured executive confirmation produced by the AI Reservation Specialist."""
    summary: str = Field(
        description="Concise, professional confirmation summary citing doctor name, department, date, time, and confirmed status."
    )
    next_recommended_action: NextRecommendedAction = Field(
        default=NextRecommendedAction.NONE,
        description="Next recommended action (typically NONE since booking is successfully committed)."
    )


class ModificationReportResult(BaseModel):
    """Structured audit summary produced by the AI Modification Specialist."""
    summary: str = Field(
        description="Concise factual audit confirmation acknowledging rescheduling or cancellation with relevant timestamps."
    )
    next_recommended_action: NextRecommendedAction = Field(
        default=NextRecommendedAction.NONE,
        description="Next recommended action (typically NONE)."
    )


class DoctorResolutionResult(BaseModel):
    """Dynamic multilingual evaluation of candidate doctors (not found, ambiguous matches, or resolved)."""
    status: SQLReportStatus = Field(description="SUCCESS if doctor identified or multiple matches need clarification; NOT_FOUND if zero doctors found")
    summary: str = Field(description="Dynamic, courteous summary formulated in the user's conversational language (Arabic or English) addressing the user")
    selected_doctor_id: Optional[str] = Field(default=None, description="UUID of the resolved doctor if exactly one match found")
    next_recommended_action: NextRecommendedAction = Field(description="CLARIFY if ambiguous or not found, RESERVE if exactly one doctor resolved")


class AppointmentResolutionResult(BaseModel):
    """Dynamic multilingual evaluation of appointment lookup (not found, ambiguous bookings, or resolved)."""
    status: SQLReportStatus = Field(description="SUCCESS if appointment identified or multiple appointments need clarification; NOT_FOUND if zero appointments found")
    summary: str = Field(description="Dynamic, courteous summary formulated in the user's conversational language (Arabic or English) addressing the user")
    selected_appointment_id: Optional[str] = Field(default=None, description="UUID of the single target appointment")
    next_recommended_action: NextRecommendedAction = Field(description="CLARIFY if multiple appointments or not found, NONE or MODIFY if single match")




import json
from typing import Any, Optional
from langchain_core.messages import BaseMessage
from utilities_ai.chains import structure_prompt

from src.ai.enums import NextRecommendedAction, SQLReportStatus

BASE_CLINICAL_SPECIALIST_INSTRUCTIONS = """
You are the Senior Clinical Operations Specialist for a UAE Healthcare Institution.
Your objective is to provide intelligent clinical decision-making, physician allocation, schedule analysis, and empathetic patient communications.
"""


def slot_availability_prompt(
    doctor_name: str,
    requested_slot: dict[str, str],
    conflicts: list[dict[str, Any]],
) -> list[BaseMessage]:
    """Evaluates whether a doctor's slot has conflicts and suggests alternative open slots."""
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: EVALUATE SLOT AVAILABILITY
    Doctor: {doctor_name}
    Requested Slot: {json.dumps(requested_slot, ensure_ascii=False)}
    Active Conflicts Found in DB: {len(conflicts)} ({json.dumps(conflicts, ensure_ascii=False)})

    RULES:
    - If conflicts count == 0: The slot is 100% free! Set `is_available = True`, `status = '{SQLReportStatus.SUCCESS.value}'`, `next_recommended_action = '{NextRecommendedAction.RESERVE.value}'`, and confirm availability.
    - If conflicts count > 0: The slot is occupied. Set `is_available = False`, `status = '{SQLReportStatus.CONFLICT.value}'`, `next_recommended_action = '{NextRecommendedAction.OFFER_ALTERNATIVES.value}'`, and suggest 2-3 open 30-minute alternative slots.
    """
    return structure_prompt(f"Evaluate availability for doctor {doctor_name}. Conflicts: {len(conflicts)}", system_prompt)


def doctor_recommendation_prompt(
    candidates: list[dict[str, Any]],
    criteria: dict[str, Any],
) -> list[BaseMessage]:
    """Ranks candidate doctors by lowest daily workload and highest experience."""
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: DOCTOR ALLOCATION (WORKLOAD & EXPERIENCE RANKING)
    Criteria: {json.dumps(criteria, ensure_ascii=False)}
    Candidates from DB:
    {json.dumps(candidates, ensure_ascii=False, indent=2)}

    RULES:
    - If candidates is empty: Set `status = '{SQLReportStatus.NOT_FOUND.value}'`, `recommended_doctor = None`, `next_recommended_action = '{NextRecommendedAction.CLARIFY.value}'`.
    - If candidates exist:
      1. Rank by lowest `current_day_appointments_count`.
      2. If tied, rank by highest `experience_years`.
      3. Set top doctor in `recommended_doctor`, remaining in `alternative_doctors`.
      4. Set `status = '{SQLReportStatus.SUCCESS.value}'`, `next_recommended_action = '{NextRecommendedAction.RESERVE.value}'`.
    """
    return structure_prompt(f"Recommend best doctor from {len(candidates)} candidates", system_prompt)


def doctor_resolution_prompt(
    user_query: str,
    search_term: str,
    candidates: list[dict[str, Any]],
) -> list[BaseMessage]:
    """Matches the user's requested doctor name/term to candidate database records."""
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: MULTILINGUAL DOCTOR RESOLUTION
    User Query: "{user_query}"
    Search Term: "{search_term}"
    Candidate Doctors from DB ({len(candidates)}):
    {json.dumps(candidates, ensure_ascii=False, indent=2)}

    RULES:
    1. Respond in the user's language (Arabic if Arabic, English if English).
    2. Understand Arabic-to-Latin transliterations (e.g. 'سلطان' matches 'Dr. Sultan').
    3. Exactly 1 clear match: Set `status = '{SQLReportStatus.SUCCESS.value}'`, `selected_doctor_id = match['id']`, `next_recommended_action = '{NextRecommendedAction.RESERVE.value}'`.
    4. Ambiguous (multiple matching doctors): Set `status = '{SQLReportStatus.SUCCESS.value}'`, `selected_doctor_id = None`, `next_recommended_action = '{NextRecommendedAction.CLARIFY.value}'` and ask user to choose.
    5. Zero candidates: Set `status = '{SQLReportStatus.NOT_FOUND.value}'`, `selected_doctor_id = None`, `next_recommended_action = '{NextRecommendedAction.CLARIFY.value}'`.
    """
    return structure_prompt(f"Resolve doctor for '{search_term}' from {len(candidates)} candidates", system_prompt)


def appointment_resolution_prompt(
    user_query: str,
    appointments: list[dict[str, Any]],
) -> list[BaseMessage]:
    """Resolves target appointment from active bookings or requests clarification."""
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: APPOINTMENT RESOLUTION
    User Query: "{user_query}"
    Appointments ({len(appointments)}):
    {json.dumps(appointments, ensure_ascii=False, indent=2)}

    RULES:
    1. Respond in user's language.
    2. Zero appointments: Set `status = '{SQLReportStatus.NOT_FOUND.value}'`, `selected_appointment_id = None`, `next_recommended_action = '{NextRecommendedAction.CLARIFY.value}'`.
    3. Exactly 1 appointment: Set `status = '{SQLReportStatus.SUCCESS.value}'`, `selected_appointment_id = appointments[0]['id']`, `next_recommended_action = '{NextRecommendedAction.NONE.value}'`.
    4. Multiple appointments: Set `status = '{SQLReportStatus.SUCCESS.value}'`, `selected_appointment_id = None`, `next_recommended_action = '{NextRecommendedAction.CLARIFY.value}'` and list appointments so user can pick.
    """
    return structure_prompt(f"Resolve appointment for '{user_query}' from {len(appointments)} records", system_prompt)


def appointment_confirmation_prompt(
    details: dict[str, Any],
) -> list[BaseMessage]:
    """Formulates confirmation summary for patient after booking, rescheduling, or cancelling."""
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: APPOINTMENT CONFIRMATION REPORT
    Details: {json.dumps(details, ensure_ascii=False, indent=2)}

    RULES:
    1. Formulate a polite, professional, and clear confirmation message for the patient.
    2. Confirm the doctor name, department, time, and status in the clinic database.
    3. Set `next_recommended_action = '{NextRecommendedAction.NONE.value}'`.
    """
    return structure_prompt(f"Formulate confirmation report: {json.dumps(details, ensure_ascii=False)}", system_prompt)


def catalog_interpretation_prompt(
    user_query: str,
    departments: list[dict[str, Any]],
    doctors: list[dict[str, Any]],
) -> list[BaseMessage]:
    """Interprets clinical catalog search results and formulates empathetic patient response."""
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: CLINICAL CATALOG INTERPRETATION
    User Query: "{user_query}"
    Found Departments ({len(departments)}): {json.dumps(departments, ensure_ascii=False)}
    Found Doctors ({len(doctors)}): {json.dumps(doctors, ensure_ascii=False)}

    RULES:
    1. Respond in the user's conversational language (Arabic if Arabic, English if English).
    2. If zero entities found: Set `status = '{SQLReportStatus.NOT_FOUND.value}'`, explain politely that no matching department or doctor was found, and set `next_recommended_action = '{NextRecommendedAction.CLARIFY.value}'`.
    3. If matching doctors or departments exist:
       - Summarize available specialties, doctors, and departments warmly.
       - Highlight the most relevant doctors/departments for the user's query.
       - Set `status = '{SQLReportStatus.SUCCESS.value}'`, and set `next_recommended_action = '{NextRecommendedAction.RESERVE.value}'` (encouraging booking) or `'{NextRecommendedAction.CLARIFY.value}'`.
    """
    return structure_prompt(f"Interpret catalog lookup for '{user_query}'", system_prompt)


def patient_schedule_summary_prompt(
    patient_id: str,
    appointments: list[dict[str, Any]],
) -> list[BaseMessage]:
    """Summarizes patient appointments clearly and advises on upcoming visits."""
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: PATIENT APPOINTMENTS SUMMARY
    Patient ID: {patient_id}
    Appointments ({len(appointments)}):
    {json.dumps(appointments, ensure_ascii=False, indent=2)}

    RULES:
    1. If zero appointments: Set `status = '{SQLReportStatus.NOT_FOUND.value}'`, inform the patient kindly that they have no booked appointments, and invite them to schedule one.
    2. If appointments exist:
       - Group/highlight upcoming confirmed appointments with doctor name, department, and time.
       - Inform the patient of any instructions or options to reschedule or cancel if needed.
       - Set `status = '{SQLReportStatus.SUCCESS.value}'`, `next_recommended_action = '{NextRecommendedAction.NONE.value}'`.
    """
    return structure_prompt(f"Summarize {len(appointments)} appointment(s) for patient {patient_id}", system_prompt)


def vip_displacement_prompt(
    vip_visit_details: dict[str, Any],
    department_doctors: list[dict[str, Any]],
    conflicting_appointments: list[dict[str, Any]],
) -> list[BaseMessage]:
    """AI Strategic Planner: Assigns attending physician, plans optimal rescheduling slots, and drafts notices."""
    context = {
        "vip_visit": vip_visit_details,
        "department_doctors": department_doctors,
        "conflicting_appointments": conflicting_appointments,
    }
    system_prompt = f"""
    {BASE_CLINICAL_SPECIALIST_INSTRUCTIONS}

    ### TASK: VIP STRATEGIC PROTOCOL & RESCHEDULING PLAN
    Context:
    {json.dumps(context, ensure_ascii=False, indent=2)}

    DECISION INSTRUCTIONS (YOU ARE THE CHIEF MEDICAL PROTOCOL OFFICER):
    1. Physician Assignment:
       - Review `department_doctors` (experience, titles, specialty).
       - Select the top senior consultant/physician for `selected_doctor_id` to attend the VIP delegation.
    2. Rescheduling Strategy:
       - For EACH appointment in `conflicting_appointments`, intelligently choose a new slot (`new_start_at`, `new_end_at`).
       - New slots MUST NOT overlap with the VIP visit window ({vip_visit_details.get("start_at")} to {vip_visit_details.get("end_at")}).
       - Conveniently place them starting immediately after the VIP window finishes, or staggered by 30-minute intervals.
       - Write compassionate, reassuring notifications in Arabic (`notification_ar`) and English (`notification_en`) apologizing for the administrative change and citing the new time and doctor.
    3. Executive Summary:
       - Write a concise, professional protocol summary detailing the secured window and total affected patients.
       - Set `next_recommended_action = '{NextRecommendedAction.NONE.value}'`.
    """
    return structure_prompt(
        f"Devise VIP protocol strategy and patient rescheduling for window {vip_visit_details.get('start_at')} to {vip_visit_details.get('end_at')}",
        system_prompt,
    )

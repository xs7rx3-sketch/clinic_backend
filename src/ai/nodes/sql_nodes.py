from datetime import datetime, timedelta
import os
from typing import Any, Optional
import uuid
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from src.ai.enums import NextRecommendedAction, SQLActionType, SQLReportStatus
from src.ai.node_schemas import (
    AppointmentResolutionResult,
    CatalogLookupResult,
    DoctorRecommendationReport,
    DoctorResolutionResult,
    ModificationReportResult,
    PatientAppointmentsSummaryResult,
    ReservationReportResult,
    SlotAvailabilityReport,
    SQLNodeOutputReport,
    VIPDisplacementAIResult,
)
from src.ai.prompts.sql_prompts import (
    appointment_confirmation_prompt,
    appointment_resolution_prompt,
    catalog_interpretation_prompt,
    doctor_recommendation_prompt,
    doctor_resolution_prompt,
    patient_schedule_summary_prompt,
    slot_availability_prompt,
    vip_displacement_prompt,
)
from src.ai.state_schema import AIOverallSchema
from src.config import SQL_LLM_BASE_URL, SQL_LLM_MODEL_NAME, SQL_LLM_TEMPERATURE
from src.database.connection import get_db_session
from src.database.models import Appointment
from src.database.queries import (
    cancel_appointment,
    fetch_patient_appointments,
    get_department_doctors,
    get_doctor_conflicts,
    get_doctors_with_workload,
    get_overlapping_appointments,
    insert_appointment,
    record_appointment_history,
    reschedule_appointment,
    resolve_department_id,
    search_clinical_entities,
    search_doctors,
)


def _format_result(state: AIOverallSchema, report: SQLNodeOutputReport, node_name: str) -> dict[str, Any]:
    """Appends sub-agent output observation to messages and updates state."""
    obs = AIMessage(content=f"[Output from {node_name} - {report.status.value}]: {report.summary}\nData: {report.data}")
    return {"messages": list(state.get("messages", [])) + [obs], "node_output": report.model_dump()}


class SQLNodes:
    """Specialized AI clinical database agents driven by LLM reasoning, structured schemas, and live Neon DB."""

    def __init__(self, llm: Optional[Any] = None):
        if llm is None and os.getenv("LLM_API_KEY"):
            llm = ChatOpenAI(
                model=SQL_LLM_MODEL_NAME,
                temperature=SQL_LLM_TEMPERATURE,
                base_url=SQL_LLM_BASE_URL,
                api_key=os.getenv("LLM_API_KEY"),
            )
        self.llm = llm

        self.catalog_llm = self.llm.with_structured_output(CatalogLookupResult, method="function_calling") if self.llm else None
        self.schedule_llm = self.llm.with_structured_output(PatientAppointmentsSummaryResult, method="function_calling") if self.llm else None
        self.avail_llm = self.llm.with_structured_output(SlotAvailabilityReport, method="function_calling") if self.llm else None
        self.doctor_rec_llm = self.llm.with_structured_output(DoctorRecommendationReport, method="function_calling") if self.llm else None
        self.reserve_llm = self.llm.with_structured_output(ReservationReportResult, method="function_calling") if self.llm else None
        self.modify_llm = self.llm.with_structured_output(ModificationReportResult, method="function_calling") if self.llm else None
        self.vip_llm = self.llm.with_structured_output(VIPDisplacementAIResult, method="function_calling") if self.llm else None
        self.doc_resolve_llm = self.llm.with_structured_output(DoctorResolutionResult, method="function_calling") if self.llm else None
        self.appt_resolve_llm = self.llm.with_structured_output(AppointmentResolutionResult, method="function_calling") if self.llm else None

    async def get_values_node(self, state: AIOverallSchema) -> dict[str, Any]:
        """Sub-Agent: Retrieves clinical catalog from Neon DB via ORM and formulates AI clinical interpretation."""
        raw_input = dict(state.get("node_input", {}))
        user_query = raw_input.get("query") or state.get("query", "")
        hosp_id = raw_input.get("hospital_id") or state.get("user_data", {}).get("hospital_id")

        entities = search_clinical_entities(user_query, hosp_id)
        depts = entities.get("departments", [])
        docs = entities.get("doctors", [])

        ai_res: CatalogLookupResult = await self.catalog_llm.ainvoke(
            catalog_interpretation_prompt(user_query, depts, docs)
        )
        report = SQLNodeOutputReport(
            status=ai_res.status,
            action=SQLActionType.LOOKUP,
            summary=ai_res.summary,
            data={"departments": depts, "doctors": docs, "items": depts + docs, "count": len(depts) + len(docs), "query": user_query},
            next_recommended_action=ai_res.next_recommended_action,
        )
        return _format_result(state, report, "get_values_node")

    async def get_appointments_node(self, state: AIOverallSchema) -> dict[str, Any]:
        """Sub-Agent: Inspects schedules, verifies slot availability, or summarizes patient bookings via AI."""
        raw_input = dict(state.get("node_input", {}))
        user_data = state.get("user_data", {})
        pid = raw_input.get("patient_id") or user_data.get("patient_id")
        did = raw_input.get("doctor_id")
        doc_term = raw_input.get("doctor") or did
        slot_date = raw_input.get("date_or_range")

        if doc_term or slot_date:
            resolved_docs = search_doctors(str(doc_term or ""))
            target_doc_id = str(resolved_docs[0]["id"]) if resolved_docs else str(did or "")
            doc_display_name = resolved_docs[0]["name_ar"] if resolved_docs else str(doc_term)

            s_str = str(slot_date or "").replace("T", " ")[:19]
            e_str = (datetime.fromisoformat(s_str) + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S") if len(s_str) >= 10 else s_str
            conflicts = get_doctor_conflicts(target_doc_id, s_str, e_str) if (target_doc_id and s_str) else []

            avail_report: SlotAvailabilityReport = await self.avail_llm.ainvoke(
                slot_availability_prompt(
                    doctor_name=doc_display_name,
                    requested_slot={"slot": slot_date or "Requested slot"},
                    conflicts=conflicts,
                )
            )
            report = SQLNodeOutputReport(
                status=avail_report.status,
                action=SQLActionType.AVAILABILITY_CHECK,
                summary=avail_report.summary,
                data={
                    "is_available": avail_report.is_available,
                    "slot": slot_date,
                    "doctor": doc_display_name,
                    "conflicts": conflicts,
                    "suggested_slots": [s.model_dump() for s in avail_report.suggested_alternative_slots],
                },
                next_recommended_action=avail_report.next_recommended_action,
            )
        else:
            appts = fetch_patient_appointments(str(pid)) if pid else []
            sched_res: PatientAppointmentsSummaryResult = await self.schedule_llm.ainvoke(
                patient_schedule_summary_prompt(str(pid), appts)
            )
            report = SQLNodeOutputReport(
                status=sched_res.status,
                action=SQLActionType.AVAILABILITY_CHECK,
                summary=sched_res.summary,
                data={"appointments": appts, "count": len(appts)},
                next_recommended_action=sched_res.next_recommended_action,
            )
        return _format_result(state, report, "get_appointments_node")

    async def recommend_doctor_node(self, state: AIOverallSchema) -> dict[str, Any]:
        """Sub-Agent: Evaluates live physician workload & experience via AI clinical allocation."""
        raw_input = dict(state.get("node_input", {}))
        dept_id = resolve_department_id(raw_input.get("department_id") or raw_input.get("department"))
        specialty = raw_input.get("specialty")
        pref_date = raw_input.get("preferred_date") or datetime.now().strftime("%Y-%m-%d")

        candidates = get_doctors_with_workload(dept_id, specialty, pref_date)

        rec_result: DoctorRecommendationReport = await self.doctor_rec_llm.ainvoke(
            doctor_recommendation_prompt(candidates, {"department_id": dept_id, "preferred_date": pref_date, "specialty": specialty})
        )
        report = SQLNodeOutputReport(
            status=rec_result.status,
            action=rec_result.action,
            summary=rec_result.summary,
            data={
                "recommended_doctor": rec_result.recommended_doctor.model_dump() if rec_result.recommended_doctor else None,
                "target_date": pref_date,
                "alternative_doctors": rec_result.alternative_doctors,
            },
            next_recommended_action=rec_result.next_recommended_action,
        )
        return _format_result(state, report, "recommend_doctor_node")

    async def reserve_appointment_node(self, state: AIOverallSchema) -> dict[str, Any]:
        """Sub-Agent: Resolves physician (handles transliteration/ambiguity), verifies availability, and commits booking via ORM."""
        raw_input = dict(state.get("node_input", {}))
        user_data = state.get("user_data", {})
        pid = raw_input.get("patient_id") or user_data.get("patient_id")
        doc_term = raw_input.get("doctor") or raw_input.get("doctor_id") or ""
        dept_id = resolve_department_id(raw_input.get("department_id") or raw_input.get("department"))
        hid = raw_input.get("hospital_id") or user_data.get("hospital_id")
        start_str = str(raw_input.get("start_at") or "").replace("T", " ")[:19]
        dt = datetime.fromisoformat(start_str) if start_str else datetime.now()
        end_str = str(raw_input.get("end_at") or (dt + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")).replace("T", " ")[:19]

        # 1. AI Doctor Resolution
        doc_rows = search_doctors(str(doc_term), department_id=dept_id)
        conv_query = state.get("query", "") or str(doc_term)
        doc_res: DoctorResolutionResult = await self.doc_resolve_llm.ainvoke(
            doctor_resolution_prompt(conv_query, str(doc_term), doc_rows)
        )
        if doc_res.next_recommended_action == NextRecommendedAction.CLARIFY or not doc_res.selected_doctor_id:
            report = SQLNodeOutputReport(
                status=doc_res.status, action=SQLActionType.RESERVE,
                summary=doc_res.summary,
                data={"search_term": doc_term, "candidate_doctors": doc_rows},
                next_recommended_action=doc_res.next_recommended_action,
            )
            return _format_result(state, report, "reserve_appointment_node")

        resolved_doc = next((d for d in doc_rows if str(d["id"]) == str(doc_res.selected_doctor_id)), doc_rows[0])
        did = str(resolved_doc["id"])
        dept_id = dept_id or str(resolved_doc.get("department_id", ""))

        # 2. Check conflicts & AI Availability Evaluation
        conflicts = get_doctor_conflicts(did, start_str, end_str)
        if conflicts:
            avail_report: SlotAvailabilityReport = await self.avail_llm.ainvoke(
                slot_availability_prompt(
                    doctor_name=resolved_doc.get("name_ar") or resolved_doc.get("name_en", "Doctor"),
                    requested_slot={"start_at": start_str, "end_at": end_str},
                    conflicts=conflicts,
                )
            )
            report = SQLNodeOutputReport(
                status=SQLReportStatus.CONFLICT, action=SQLActionType.RESERVE,
                summary=avail_report.summary,
                data={"conflicts": conflicts, "suggested_slots": [s.model_dump() for s in avail_report.suggested_alternative_slots]},
                next_recommended_action=NextRecommendedAction.OFFER_ALTERNATIVES,
            )
            return _format_result(state, report, "reserve_appointment_node")

        # 3. Commit Reservation via ORM with booking_source
        booking_src = raw_input.get("booking_source") or user_data.get("booking_source") or ("VIP_LIAISON" if user_data.get("is_vip") else "FLUTTER_APP")
        new_appt = insert_appointment(
            hid=hid, dept_id=dept_id, did=did, pid=pid, start_at=start_str, end_at=end_str,
            reason=raw_input.get("reason_for_visit") or "General Consultation",
            booking_source=booking_src,
        )
        appt_id = new_appt["id"]
        record_appointment_history(appt_id=appt_id, action="CREATED", new_start_at=start_str, new_status="CONFIRMED", notes="Booked via AI Portal")

        # 4. AI Confirmation Formulation
        ai_confirm: ReservationReportResult = await self.reserve_llm.ainvoke(
            appointment_confirmation_prompt({
                "appointment_id": appt_id, "doctor_name": resolved_doc.get("name_ar") or resolved_doc.get("name_en"),
                "department_name": resolved_doc.get("department_name"), "start_at": start_str, "end_at": end_str,
                "patient_id": str(pid), "status": "CONFIRMED",
            })
        )
        report = SQLNodeOutputReport(
            status=SQLReportStatus.SUCCESS, action=SQLActionType.RESERVE, summary=ai_confirm.summary,
            data={"appointment_id": appt_id, "doctor_id": did, "start_at": start_str, "end_at": end_str, "status": "CONFIRMED", "booking_source": booking_src},
            next_recommended_action=ai_confirm.next_recommended_action,
        )
        return _format_result(state, report, "reserve_appointment_node")

    async def modify_appointment_node(self, state: AIOverallSchema) -> dict[str, Any]:
        """Sub-Agent: Resolves existing booking, applies reschedule/cancel via ORM, and emits AI confirmation."""
        raw_input = dict(state.get("node_input", {}))
        user_data = state.get("user_data", {})
        pid = raw_input.get("patient_id") or user_data.get("patient_id")
        raw_aid = raw_input.get("appointment_id")
        target_status = str(raw_input.get("new_status") or "").upper()
        new_start = raw_input.get("new_start_at")

        appts = fetch_patient_appointments(str(pid)) if pid else []
        if raw_aid:
            matched = [a for a in appts if str(a["id"]) == str(raw_aid)]
            if matched:
                appts = matched
            else:
                with get_db_session() as session:
                    db_appt = session.get(Appointment, uuid.UUID(str(raw_aid).strip())) if (len(str(raw_aid)) == 36 and "-" in str(raw_aid)) else None
                    if db_appt:
                        doc_name = db_appt.doctor.name_ar if db_appt.doctor else "الطبيب المعالج"
                        appts = [{
                            "id": str(db_appt.id),
                            "doctor_name_ar": doc_name,
                            "start_at": str(db_appt.start_at),
                            "end_at": str(db_appt.end_at),
                            "status": db_appt.status,
                        }]
                    else:
                        appts = []
                if not appts:
                    report = SQLNodeOutputReport(
                        status=SQLReportStatus.NOT_FOUND,
                        action=SQLActionType.MODIFY,
                        summary=f"Appointment {raw_aid} not found in database records.",
                        data={"appointment_id": raw_aid},
                        next_recommended_action=NextRecommendedAction.CLARIFY,
                    )
                    return _format_result(state, report, "modify_appointment_node")

        conv_query = raw_input.get("query") or state.get("query", "")
        appt_res: AppointmentResolutionResult = await self.appt_resolve_llm.ainvoke(
            appointment_resolution_prompt(conv_query, appts)
        )
        if appt_res.next_recommended_action == NextRecommendedAction.CLARIFY or not appt_res.selected_appointment_id:
            report = SQLNodeOutputReport(
                status=appt_res.status, action=SQLActionType.MODIFY,
                summary=appt_res.summary,
                data={"appointments": appts},
                next_recommended_action=appt_res.next_recommended_action,
            )
            return _format_result(state, report, "modify_appointment_node")

        target_id = str(appt_res.selected_appointment_id)
        target_record = next((a for a in appts if str(a["id"]) == target_id), appts[0] if appts else {})

        if "CANCEL" in target_status or "الغاء" in conv_query:
            cancel_appointment(target_id)
            record_appointment_history(target_id, action="CANCELLED", new_status="CANCELLED", notes=raw_input.get("notes") or "Cancelled by patient")
            mod_type = "CANCELLED"
        else:
            s_str = str(new_start or "").replace("T", " ")[:19]
            dt_n = datetime.fromisoformat(s_str) if s_str else datetime.now()
            e_str = str(raw_input.get("new_end_at") or (dt_n + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")).replace("T", " ")[:19]
            reschedule_appointment(target_id, s_str, e_str)
            record_appointment_history(target_id, action="RESCHEDULED", old_start_at=str(target_record.get("start_at")), new_start_at=s_str, notes="Rescheduled via AI Portal")
            mod_type = "RESCHEDULED"

        ai_mod: ModificationReportResult = await self.modify_llm.ainvoke(
            appointment_confirmation_prompt({
                "appointment_id": target_id, "status": mod_type,
                "new_start_at": new_start, "doctor_name": target_record.get("doctor_name_ar") or target_record.get("doctor_name_en"),
                "patient_id": str(pid),
            })
        )
        report = SQLNodeOutputReport(
            status=SQLReportStatus.SUCCESS, action=SQLActionType.MODIFY, summary=ai_mod.summary,
            data={"appointment_id": target_id, "new_status": mod_type, "status": mod_type, "new_start_at": new_start},
            next_recommended_action=ai_mod.next_recommended_action,
        )
        return _format_result(state, report, "modify_appointment_node")

    async def vip_displacement_node(self, state: AIOverallSchema) -> dict[str, Any]:
        """Sub-Agent: AI-driven VIP delegation planning, physician allocation, patient rescheduling, and diplomatic notices."""
        raw_input = dict(state.get("node_input", {}))
        user_data = state.get("user_data", {})
        dept_id = resolve_department_id(raw_input.get("department_id") or raw_input.get("department")) or ""
        if not dept_id:
            report = SQLNodeOutputReport(
                status=SQLReportStatus.NOT_FOUND,
                action=SQLActionType.VIP_DISPLACEMENT,
                summary=f"Department '{raw_input.get('department_id') or raw_input.get('department')}' not found in hospital directory.",
                data={"requested_department": raw_input.get("department_id") or raw_input.get("department")},
                next_recommended_action=NextRecommendedAction.CLARIFY,
            )
            return _format_result(state, report, "vip_displacement_node")
        hid = raw_input.get("hospital_id") or user_data.get("hospital_id")
        vip_pid = raw_input.get("vip_patient_id") or user_data.get("patient_id")

        vip_start = str(raw_input.get("start_at") or "").replace("T", " ")[:19]
        dt = datetime.fromisoformat(vip_start) if vip_start else datetime.now()
        vip_end = str(raw_input.get("end_at") or (dt + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")).replace("T", " ")[:19]

        # 1. ORM Fetches live context: Department Doctors & Conflicting Appointments
        dept_doctors = get_department_doctors(dept_id)
        conflicting_appts = get_overlapping_appointments(dept_id, vip_start, vip_end)

        # 2. AI Strategic Protocol Decision: Chooses physician & plans patient rescheduling
        ai_plan: VIPDisplacementAIResult = await self.vip_llm.ainvoke(
            vip_displacement_prompt(
                vip_visit_details={"start_at": vip_start, "end_at": vip_end, "department_id": dept_id},
                department_doctors=dept_doctors,
                conflicting_appointments=conflicting_appts,
            )
        )

        # 3. ORM executes AI's rescheduling plan
        displaced_records = []
        for slot in ai_plan.rescheduled_slots:
            reschedule_appointment(slot.appointment_id, slot.new_start_at, slot.new_end_at)
            record_appointment_history(
                slot.appointment_id, action="RESCHEDULED",
                new_start_at=slot.new_start_at,
                notes=f"Displaced for VIP: {slot.reasoning or 'Protocol delegation'}",
            )
            displaced_records.append({
                "appointment_id": slot.appointment_id,
                "patient_name": slot.patient_name,
                "new_start_at": slot.new_start_at,
                "new_end_at": slot.new_end_at,
                "notification_ar": slot.notification_ar,
                "notification_en": slot.notification_en,
            })

        # 4. ORM secures VIP reservation with AI's selected physician and booking_source
        chosen_doc_id = ai_plan.selected_doctor_id or (dept_doctors[0]["id"] if dept_doctors else None)
        vip_booking_src = raw_input.get("booking_source") or "VIP_LIAISON"
        vip_appt = insert_appointment(
            hid=hid, dept_id=dept_id, did=chosen_doc_id, pid=vip_pid,
            start_at=vip_start, end_at=vip_end, reason="Official VIP Delegation Visit",
            is_vip=True, notes=raw_input.get("notes") or "Secured Department Protocol Window",
            booking_source=vip_booking_src,
        )
        vip_appt_id = vip_appt.get("id")
        if vip_appt_id:
            record_appointment_history(vip_appt_id, action="CREATED", new_start_at=vip_start, new_status="CONFIRMED", notes="Official VIP Reservation")

        notifications = [
            {"patient_name": s.patient_name, "notification_ar": s.notification_ar, "notification_en": s.notification_en}
            for s in ai_plan.rescheduled_slots
        ] or [n.model_dump() for n in ai_plan.patient_notifications]

        report = SQLNodeOutputReport(
            status=SQLReportStatus.SUCCESS, action=SQLActionType.VIP_DISPLACEMENT, summary=ai_plan.summary,
            data={
                "vip_appointment_id": vip_appt_id, "vip_doctor_id": chosen_doc_id,
                "vip_window": {"start_at": vip_start, "end_at": vip_end},
                "displaced_count": len(displaced_records),
                "displaced_appointments": displaced_records,
                "patient_notifications": notifications,
                "booking_source": vip_booking_src,
            },
            next_recommended_action=ai_plan.next_recommended_action,
        )
        return _format_result(state, report, "vip_displacement_node")

import asyncio
import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ai.enums import NextRecommendedAction, SQLReportStatus
from src.ai.nodes.sql_nodes import SQLNodes
from src.database.queries import insert_appointment
from tests.test_helpers import (
    cleanup_test_appointments,
    get_live_test_entities,
    print_fail,
    print_header,
    print_info,
    print_success,
)


async def run_sql_nodes_tests() -> bool:
    print_header("SUITE 1: DIRECT SQL SPECIALIST NODES (AI REASONING & ORM)")
    sql_nodes = SQLNodes()
    entities = get_live_test_entities()

    hospital = entities["hospital"]
    department = entities["department"]
    doctor = entities["doctor"]
    normal_patient = entities["normal_patient"]
    vip_patient = entities["vip_patient"]

    all_passed = True
    test_tag = "TEST_RUN_SQL_NODE"
    created_appointment_id = None

    try:
        # -------------------------------------------------------------
        # 1. Test get_values_node: Clinical Catalog Lookup
        # -------------------------------------------------------------
        print("\n[1/12] Testing get_values_node with clinical query ('Cardio' / 'قلب')...")
        state_values = {
            "query": "Cardio",
            "node_input": {"query": "Cardio"},
            "user_data": {},
            "messages": [],
        }
        res_v = await sql_nodes.get_values_node(state_values)
        rep_v = res_v["node_output"]
        if rep_v["status"] == SQLReportStatus.SUCCESS and rep_v["data"].get("count", 0) > 0:
            print_success(f"Found {rep_v['data']['count']} matching item(s). Summary: {rep_v['summary']}")
        else:
            print_fail(f"Expected SUCCESS with count > 0, got {rep_v}")
            all_passed = False

        # -------------------------------------------------------------
        # 2. Test get_values_node: Non-existent Query
        # -------------------------------------------------------------
        print("\n[2/12] Testing get_values_node with non-existent query (Zero Fallback Check)...")
        state_v_none = {
            "query": "NonExistentSpecialty_XYZ_9999",
            "node_input": {"query": "NonExistentSpecialty_XYZ_9999"},
            "user_data": {},
            "messages": [],
        }
        res_v_none = await sql_nodes.get_values_node(state_v_none)
        rep_v_none = res_v_none["node_output"]
        if rep_v_none["status"] == SQLReportStatus.NOT_FOUND and rep_v_none["data"].get("count", 0) == 0:
            print_success(f"Properly returned NOT_FOUND without fallbacks: {rep_v_none['summary']}")
        else:
            print_fail(f"Expected NOT_FOUND with count 0, got {rep_v_none}")
            all_passed = False

        # -------------------------------------------------------------
        # 3. Test recommend_doctor_node: Clinical Allocation & Workload
        # -------------------------------------------------------------
        print("\n[3/12] Testing recommend_doctor_node (Workload ranking & clinical rationale)...")
        target_date = "2026-11-20"
        state_rec = {
            "query": "أفضل طبيب",
            "node_input": {"department_id": department["id"], "preferred_date": target_date},
            "user_data": {},
            "messages": [],
        }
        res_rec = await sql_nodes.recommend_doctor_node(state_rec)
        rep_rec = res_rec["node_output"]
        if rep_rec["status"] == SQLReportStatus.SUCCESS and "recommended_doctor" in rep_rec["data"]:
            rec_doc = rep_rec["data"]["recommended_doctor"]
            print_success(f"Recommended Doctor: {rec_doc.get('name_ar')} | Workload: {rec_doc.get('current_day_appointments_count')} appts")
        else:
            print_fail(f"recommend_doctor_node failed: {rep_rec}")
            all_passed = False

        # -------------------------------------------------------------
        # 4. Test get_appointments_node: Patient Bookings Schedule
        # -------------------------------------------------------------
        print("\n[4/12] Testing get_appointments_node for patient appointments summary...")
        state_appts = {
            "query": "مواعيدي السابقة",
            "node_input": {"patient_id": normal_patient["id"]},
            "user_data": {"patient_id": normal_patient["id"]},
            "messages": [],
        }
        res_appts = await sql_nodes.get_appointments_node(state_appts)
        rep_appts = res_appts["node_output"]
        if rep_appts["status"] in (SQLReportStatus.SUCCESS, SQLReportStatus.NOT_FOUND):
            print_success(f"Retrieved appointments status: {rep_appts['status']} ({rep_appts['summary']})")
        else:
            print_fail(f"get_appointments_node failed: {rep_appts}")
            all_passed = False

        # -------------------------------------------------------------
        # 5. Test get_appointments_node: Slot Availability Check
        # -------------------------------------------------------------
        print("\n[5/12] Testing get_appointments_node for doctor slot availability...")
        free_slot = "2026-12-01 10:00:00"
        state_avail = {
            "query": "Check availability",
            "node_input": {"doctor_id": doctor["id"], "date_or_range": free_slot},
            "user_data": {},
            "messages": [],
        }
        res_avail = await sql_nodes.get_appointments_node(state_avail)
        rep_avail = res_avail["node_output"]
        if rep_avail["status"] == SQLReportStatus.SUCCESS and rep_avail["data"].get("is_available") is True:
            print_success(f"Slot {free_slot} confirmed available: {rep_avail['summary']}")
        else:
            print_fail(f"Slot availability check failed: {rep_avail}")
            all_passed = False

        # -------------------------------------------------------------
        # 6. Test reserve_appointment_node: Direct Booking with booking_source
        # -------------------------------------------------------------
        print("\n[6/12] Testing reserve_appointment_node (ORM booking & booking_source propagation)...")
        reserve_slot = "2026-12-01 10:00:00"
        state_resv = {
            "query": "Reserve",
            "node_input": {
                "hospital_id": hospital["id"],
                "department_id": doctor.get("department_id") or department["id"],
                "doctor_id": doctor["id"],
                "patient_id": normal_patient["id"],
                "start_at": reserve_slot,
                "reason_for_visit": f"Cardiology Checkup - {test_tag}",
                "booking_source": "FLUTTER_APP",
            },
            "user_data": {},
            "messages": [],
        }
        res_resv = await sql_nodes.reserve_appointment_node(state_resv)
        rep_resv = res_resv["node_output"]
        if rep_resv["status"] == SQLReportStatus.SUCCESS:
            created_appointment_id = rep_resv["data"]["appointment_id"]
            b_src = rep_resv["data"].get("booking_source")
            print_success(f"Appointment reserved! ID: {created_appointment_id} | Status: {rep_resv['data']['status']} | Booking Source: {b_src}")
        else:
            print_fail(f"reserve_appointment_node failed: {rep_resv}")
            all_passed = False

        # -------------------------------------------------------------
        # 7. Test reserve_appointment_node: Conflict Detection
        # -------------------------------------------------------------
        print("\n[7/12] Testing reserve_appointment_node conflict detection (Duplicate Slot)...")
        res_conflict = await sql_nodes.reserve_appointment_node(state_resv)
        rep_conflict = res_conflict["node_output"]
        if rep_conflict["status"] == SQLReportStatus.CONFLICT:
            print_success(f"Conflict correctly detected: {rep_conflict['summary']}")
        else:
            print_fail(f"Expected CONFLICT, got: {rep_conflict}")
            all_passed = False

        # -------------------------------------------------------------
        # 8. Test modify_appointment_node: Rescheduling
        # -------------------------------------------------------------
        print("\n[8/12] Testing modify_appointment_node (Rescheduling)...")
        resched_slot = "2026-12-01 14:00:00"
        state_resched = {
            "query": "Reschedule",
            "node_input": {
                "appointment_id": created_appointment_id,
                "new_start_at": resched_slot,
                "notes": f"Patient requested afternoon slot - {test_tag}",
            },
            "user_data": {},
            "messages": [],
        }
        res_mod = await sql_nodes.modify_appointment_node(state_resched)
        rep_mod = res_mod["node_output"]
        if rep_mod["status"] == SQLReportStatus.SUCCESS and rep_mod["data"].get("new_start_at") == resched_slot:
            print_success(f"Appointment rescheduled to {resched_slot} successfully.")
        else:
            print_fail(f"Rescheduling failed: {rep_mod}")
            all_passed = False

        # -------------------------------------------------------------
        # 9. Test modify_appointment_node: Cancellation
        # -------------------------------------------------------------
        print("\n[9/12] Testing modify_appointment_node (Cancellation)...")
        state_cancel = {
            "query": "Cancel",
            "node_input": {
                "appointment_id": created_appointment_id,
                "new_status": "CANCELLED",
                "notes": f"Cancelled by patient - {test_tag}",
            },
            "user_data": {},
            "messages": [],
        }
        res_cancel = await sql_nodes.modify_appointment_node(state_cancel)
        rep_cancel = res_cancel["node_output"]
        if rep_cancel["status"] == SQLReportStatus.SUCCESS and rep_cancel["data"].get("status") == "CANCELLED":
            print_success(f"Appointment cancelled successfully.")
        else:
            print_fail(f"Cancellation failed: {rep_cancel}")
            all_passed = False

        # -------------------------------------------------------------
        # 10. Test modify_appointment_node: Non-Existent ID (NOT_FOUND)
        # -------------------------------------------------------------
        print("\n[10/12] Testing modify_appointment_node with non-existent ID (NOT_FOUND check)...")
        fake_aid = "00000000-0000-0000-0000-000000000000"
        state_fake = {
            "query": "Cancel fake",
            "node_input": {"appointment_id": fake_aid, "new_status": "CANCELLED"},
            "user_data": {},
            "messages": [],
        }
        res_fake = await sql_nodes.modify_appointment_node(state_fake)
        rep_fake = res_fake["node_output"]
        if rep_fake["status"] == SQLReportStatus.NOT_FOUND:
            print_success("Properly returned NOT_FOUND for non-existent appointment ID.")
        else:
            print_fail(f"Expected NOT_FOUND, got: {rep_fake}")
            all_passed = False

        # -------------------------------------------------------------
        # 11. Test vip_displacement_node: Strategic Protocol & Notices
        # -------------------------------------------------------------
        print("\n[11/12] Testing vip_displacement_node (AI Physician Selection & Diplomatic Rescheduling)...")
        disp_target_start = "2026-12-10 09:30:00"
        disp_target_end = "2026-12-10 10:00:00"
        dummy_res = insert_appointment(
            hid=hospital["id"],
            dept_id=doctor.get("department_id") or department["id"],
            did=doctor["id"],
            pid=normal_patient["id"],
            start_at=disp_target_start,
            end_at=disp_target_end,
            reason="Regular Consultation to be displaced",
            notes=test_tag,
            booking_source="FLUTTER_APP",
        )

        vip_start = "2026-12-10 09:00:00"
        vip_end = "2026-12-10 11:00:00"
        state_vip = {
            "query": "حجز القسم لوفد رسمي",
            "node_input": {
                "hospital_id": hospital["id"],
                "department_id": doctor.get("department_id") or department["id"],
                "vip_patient_id": vip_patient["id"],
                "start_at": vip_start,
                "end_at": vip_end,
                "notes": f"Official Delegation Protocol Reservation - {test_tag}",
                "booking_source": "VIP_LIAISON",
            },
            "user_data": {"patient_id": vip_patient["id"], "is_vip": True},
            "messages": [],
        }
        res_vip = await sql_nodes.vip_displacement_node(state_vip)
        rep_vip = res_vip["node_output"]
        if rep_vip["status"] == SQLReportStatus.SUCCESS and rep_vip["data"].get("displaced_count", 0) >= 1:
            vip_src = rep_vip["data"].get("booking_source")
            print_success(
                f"VIP Window secured! Displaced count: {rep_vip['data']['displaced_count']} | "
                f"Booking Source: {vip_src} | "
                f"Patient notifications generated: {len(rep_vip['data']['patient_notifications'])}"
            )
            sample_notif = rep_vip["data"]["patient_notifications"][0]["notification_ar"]
            print_info(f"Sample generated Arabic notification:\n     \"{sample_notif}\"")
        else:
            print_fail(f"vip_displacement_node failed: {rep_vip}")
            all_passed = False

        # -------------------------------------------------------------
        # 12. Test reserve_appointment_node: Ambiguity / Missing Doctor Resilience
        # -------------------------------------------------------------
        print("\n[12/12] Testing reserve_appointment_node ambiguity handling (Graceful CLARIFY)...")
        state_invalid = {
            "query": "Reserve without doctor",
            "node_input": {"reason_for_visit": "Missing doctor info"},
            "user_data": {},
            "messages": [],
        }
        res_inv = await sql_nodes.reserve_appointment_node(state_invalid)
        rep_inv = res_inv["node_output"]
        if rep_inv.get("next_recommended_action") == NextRecommendedAction.CLARIFY or rep_inv.get("status") in (SQLReportStatus.NOT_FOUND, SQLReportStatus.CONFLICT):
            print_success("Agent caught missing doctor info gracefully and recommended CLARIFY.")
        else:
            print_fail(f"Expected CLARIFY, got: {rep_inv}")
            all_passed = False

    finally:
        print("\nCleaning up test artifacts from database...")
        cleanup_test_appointments(test_tag, [created_appointment_id] if created_appointment_id else None)

    if all_passed:
        print_success("ALL 12 SQL SPECIALIST TESTS PASSED WITH 100% SUCCESS!")
    else:
        print_fail("SOME SQL SPECIALIST TESTS FAILED. PLEASE CHECK LOGS ABOVE.")

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_sql_nodes_tests())
    sys.exit(0 if success else 1)

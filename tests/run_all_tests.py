import asyncio
import os
import sys
import time

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

from tests.test_01_sql_nodes import run_sql_nodes_tests
from tests.test_02_ai_scenarios_graph import run_ai_scenarios_tests
from tests.test_helpers import TestColors, print_header, print_info, print_success, print_fail


async def main():
    print(f"{TestColors.BOLD}{TestColors.CYAN}")
    print("=" * 70)
    print("      CLINIC AI SYSTEM - COMPREHENSIVE TEST SUITE RUNNER")
    print("=" * 70)
    print(f"{TestColors.RESET}")
    print("Available Test Suites:")
    print("  [1] Direct Database & SQL Specialist Nodes (Live clinic_testing DB)")
    print("  [2] End-to-End AI Graph Scenarios (LLM + Controller + SQL Nodes)")
    print("  [3] Run ALL Test Suites sequentially (Full System Verification)")
    print()

    # Check CLI arguments first (e.g. `python tests/run_all_tests.py 1`)
    choice = None
    if len(sys.argv) > 1:
        choice = sys.argv[1].strip()
    else:
        try:
            choice = input(f"{TestColors.YELLOW}Enter your choice [1, 2, or 3] (Default: 3): {TestColors.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "3"

    if not choice:
        choice = "3"

    start_time = time.time()
    results = {}

    if choice in ("1", "3"):
        t0 = time.time()
        print_info("Starting Suite 1: Direct SQL Specialist Nodes...")
        try:
            res_sql = await run_sql_nodes_tests()
            results["Suite 1: Direct SQL Nodes"] = ("PASS" if res_sql else "FAIL", time.time() - t0)
        except Exception as e:
            print_fail(f"Suite 1 encountered an unexpected exception: {e}")
            results["Suite 1: Direct SQL Nodes"] = ("ERROR", time.time() - t0)

    if choice in ("2", "3"):
        t0 = time.time()
        print_info("Starting Suite 2: End-to-End AI Graph Agent Scenarios...")
        try:
            res_ai = await run_ai_scenarios_tests()
            results["Suite 2: AI Graph Scenarios"] = ("PASS" if res_ai else "FAIL", time.time() - t0)
        except Exception as e:
            print_fail(f"Suite 2 encountered an unexpected exception: {e}")
            results["Suite 2: AI Graph Scenarios"] = ("ERROR", time.time() - t0)

    total_duration = time.time() - start_time

    # Print Final Summary Dashboard
    print_header("FINAL TEST EXECUTION SUMMARY")
    all_success = True
    for suite_name, (status, duration) in results.items():
        if status == "PASS":
            print(f"  {TestColors.GREEN}[PASS] {suite_name:<38} ({duration:.2f}s){TestColors.RESET}")
        else:
            print(f"  {TestColors.RED}[{status}] {suite_name:<38} ({duration:.2f}s){TestColors.RESET}")
            all_success = False

    print(f"\n{TestColors.BOLD}Total Elapsed Time: {total_duration:.2f} seconds{TestColors.RESET}")

    if all_success:
        print(f"\n{TestColors.BOLD}{TestColors.GREEN}========================================================")
        print("   CONGRATULATIONS: ALL SELECTED TEST SUITES PASSED!   ")
        print(f"========================================================{TestColors.RESET}\n")
        return 0
    else:
        print(f"\n{TestColors.BOLD}{TestColors.RED}========================================================")
        print("   ATTENTION: ONE OR MORE TEST SUITES ENCOUNTERED ISSUES")
        print(f"========================================================{TestColors.RESET}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

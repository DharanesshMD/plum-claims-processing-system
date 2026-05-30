import asyncio
import json
import os
import sys
from pathlib import Path

# Add backend dir to python path
sys.path.append(str(Path(__file__).parent))

from app.agents.orchestrator import process_claim
from app.models.claim import ClaimInput
from app.api.claims import _evaluate_test_case


async def main():
    test_cases_path = Path(__file__).parent.parent / "test_cases.json"
    with open(test_cases_path) as f:
        data = json.load(f)

    test_cases = data.get("test_cases", [])
    results = []

    print(f"Running {len(test_cases)} test cases...")
    for tc in test_cases:
        case_id = tc["case_id"]
        case_name = tc["case_name"]
        expected = tc["expected"]
        input_data = tc["input"]

        try:
            claim_input = ClaimInput(**input_data)
            decision = await process_claim(claim_input)
            eval_result = _evaluate_test_case(decision, expected)

            results.append({
                "case_id": case_id,
                "case_name": case_name,
                "status": "PASS" if eval_result["passed"] else "FAIL",
                "expected": expected.get("decision"),
                "actual": decision.decision.value if decision.decision else None,
                "expected_amount": expected.get("approved_amount"),
                "actual_amount": decision.approved_amount,
                "checks": eval_result["checks"],
            })
        except Exception as e:
            results.append({
                "case_id": case_id,
                "case_name": case_name,
                "status": "ERROR",
                "error": str(e)
            })

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    print("\nResults:")
    for r in results:
        print(
            f"{r['case_id']} - {r['case_name']}: {r['status']} "
            f"(Expected: {r.get('expected')} | Actual: {r.get('actual')}) "
            f"(Expected Amount: {r.get('expected_amount')} | Actual Amount: {r.get('actual_amount')})"
        )
        if r["status"] == "FAIL":
            print(f"  FAIL details: {r['checks']}")
        elif r["status"] == "ERROR":
            print(f"  ERROR: {r['error']}")
    print(f"\nPass rate: {passed}/{total} ({100 * passed / total:.0f}%)")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

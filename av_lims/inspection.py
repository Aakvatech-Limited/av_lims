"""Inspection obligations are coverage requirements, not engineering acceptance."""

import frappe


def coverage_for_results(plan, execution_names):
    records = []
    for name in set(execution_names):
        execution = frappe.get_doc("Lab Test Execution", name)
        execution.check_permission("read")
        if execution.status != "Processed":
            continue
        sample = frappe.get_doc("Lab Sample", execution.sample)
        sample.check_permission("read")
        test = frappe.db.get_value("Lab Test Method Version", execution.method_version, "test_definition")
        records.append(
            {
                "execution": name,
                "sample": sample.name,
                "specimen": execution.specimen,
                "test_definition": test,
                "material_lot": sample.material_lot,
                "sampling_location": sample.sampling_location,
            }
        )
    result = []
    for obligation in plan.obligations:
        matches = [
            x
            for x in records
            if x["test_definition"] == obligation.test_definition
            and (not obligation.material_lot or x["material_lot"] == obligation.material_lot)
            and (not obligation.sampling_location or x["sampling_location"] == obligation.sampling_location)
        ]
        key = {"Samples": "sample", "Specimens": "specimen", "Executions": "execution"}[
            obligation.count_basis
        ]
        actual = len({x[key] for x in matches if x[key]})
        result.append(
            {
                "inspection_plan": plan.name,
                "obligation_id": obligation.name,
                "title": obligation.title,
                "test_definition": obligation.test_definition,
                "count_basis": obligation.count_basis,
                "required_count": obligation.required_count,
                "actual_count": actual,
                "remaining_count": max(0, obligation.required_count - actual),
                "hold_point": obligation.hold_point,
                "hold_released": bool(
                    frappe.db.exists(
                        "Lab Hold Point Release",
                        {
                            "inspection_plan": plan.name,
                            "obligation_id": obligation.name,
                            "status": "Approved",
                        },
                    )
                ),
            }
        )
    return result

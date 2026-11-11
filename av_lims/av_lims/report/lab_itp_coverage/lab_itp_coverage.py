import frappe

from av_lims.inspection import coverage_for_results


def execute(filters=None):
    filters = frappe._dict(filters or {})
    frappe.has_permission("Lab Inspection Test Plan", "read", throw=True)
    query = {"status": "Released"}
    if filters.work_request:
        query["work_request"] = filters.work_request
    data = []
    for name in frappe.get_list("Lab Inspection Test Plan", filters=query, pluck="name", limit_page_length=0):
        plan = frappe.get_doc("Lab Inspection Test Plan", name)
        executions = frappe.get_list(
            "Lab Test Execution",
            filters={"work_request": plan.work_request, "status": "Processed"},
            fields=["name", "supersedes"],
            limit_page_length=0,
        )
        superseded = {x.supersedes for x in executions if x.supersedes}
        data.extend(coverage_for_results(plan, [x.name for x in executions if x.name not in superseded]))
    columns = [
        {
            "fieldname": "inspection_plan",
            "label": "Inspection Plan",
            "fieldtype": "Link",
            "options": "Lab Inspection Test Plan",
            "width": 170,
        }
    ]
    for name, label, kind in [
        ("obligation_id", "Row ID", "Data"),
        ("title", "Obligation", "Data"),
        ("test_definition", "Test", "Data"),
        ("count_basis", "Count Basis", "Data"),
        ("required_count", "Required", "Int"),
        ("actual_count", "Processed", "Int"),
        ("remaining_count", "Outstanding", "Int"),
        ("hold_point", "Hold Point", "Check"),
        ("hold_released", "Hold Released", "Check"),
    ]:
        columns.append({"fieldname": name, "label": label, "fieldtype": kind, "width": 140})
    return columns, data

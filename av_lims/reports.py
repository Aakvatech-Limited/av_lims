"""Permission-aware registers. No raw SQL, synthetic KPIs or guest access."""

import frappe
from frappe.utils import get_datetime, now_datetime


def register(doctype, fields, filters=None):
    frappe.has_permission(doctype, "read", throw=True)
    filters = frappe._dict(filters or {})
    query = {k: filters[k] for k in ("division", "work_request", "customer") if filters.get(k)}
    if doctype == "Lab Work Request":
        query.pop("work_request", None)
        if filters.get("work_request"):
            query["name"] = filters.work_request
    columns = [
        {"fieldname": "name", "label": "Document", "fieldtype": "Link", "options": doctype, "width": 190}
    ]
    for f, label, kind, options in fields:
        columns.append({"fieldname": f, "label": label, "fieldtype": kind, "options": options, "width": 170})
    return columns, frappe.get_list(
        doctype,
        filters=query,
        fields=["name", *[x[0] for x in fields]],
        order_by="modified desc",
        limit_page_length=0,
    )


def due_register(filters=None):
    columns, records = register(
        "Lab Test Schedule",
        [
            ("work_request", "Work Request", "Link", "Lab Work Request"),
            ("specimen", "Specimen", "Link", "Lab Specimen"),
            ("method_version", "Method", "Link", "Lab Test Method Version"),
            ("window_start", "Window Start", "Datetime", None),
            ("due_on", "Due", "Datetime", None),
            ("window_end", "Window End", "Datetime", None),
            ("execution", "Completed Execution", "Link", "Lab Test Execution"),
        ],
        filters,
    )
    columns.append(
        {"fieldname": "schedule_state", "label": "Schedule State", "fieldtype": "Data", "width": 130}
    )
    now = now_datetime()
    for row in records:
        row["schedule_state"] = (
            "Completed" if row.execution else "Overdue" if get_datetime(row.window_end) < now else "Scheduled"
        )
    return columns, records

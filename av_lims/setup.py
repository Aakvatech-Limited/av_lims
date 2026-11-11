"""Idempotent installation; never replace customer navigation or workflows."""

import frappe

LAB_ROLES = ("LIMS Technician", "LIMS Lead", "LIMS Manager", "LIMS Approver")


def before_install():
    for role in LAB_ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
                ignore_permissions=True
            )


def after_install():
    from frappe.permissions import add_permission

    # add_permission copies existing standard permissions before adding a new rule.
    # Existing customer permissions are retained, not reset.
    for doctype in (
        "Company",
        "Customer",
        "Contact",
        "Project",
        "UOM",
        "Quotation",
        "Supplier",
        "Item",
        "Asset",
    ):
        for role in LAB_ROLES:
            if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
                add_permission(doctype, role, ptype="read")
    after_migrate()


def after_migrate():
    for doctype, fields in (
        ("Lab Test Method Version", ["test_definition", "version"]),
        ("Lab QA Checklist Version", ["title", "version"]),
        ("Lab Specification Version", ["project_profile", "test_definition", "version"]),
    ):
        frappe.db.add_unique(doctype, fields, constraint_name="unique_lab_version")


def protect_approved_file(doc, method=None):
    if doc.is_new():
        return
    old = doc.get_doc_before_save()
    url = old.file_url if old else doc.file_url
    protected = False
    for doctype, fields in {
        "Lab Result Report": ["approved_file"],
        "Lab Work Authorization": ["signed_evidence"],
        "Lab Sample Receipt": ["signed_work_request"],
        "Lab Chain of Custody": ["completion_evidence"],
        "Lab Test Execution": ["raw_evidence"],
        "Lab Equipment Check": ["certificate"],
        "Lab Competency": ["evidence"],
        "Lab Corrective Action": ["evidence"],
        "Lab Result Dispatch": ["delivery_evidence"],
    }.items():
        if frappe.db.exists("DocType", doctype):
            protected = protected or any(
                frappe.db.exists(doctype, {f: url, "status": ["!=", "Draft"]}) for f in fields
            )
    if frappe.db.exists("DocType", "Lab Work Request"):
        requests = frappe.get_all(
            "Lab Work Request", or_filters={"test_program": url, "fee_estimate": url}, pluck="name"
        )
        protected = protected or any(
            frappe.db.exists("Lab Work Authorization", {"work_request": name, "status": "Authorized"})
            for name in requests
        )
    if protected and (
        method == "on_trash"
        or (
            old
            and (
                old.file_url != doc.file_url
                or old.is_private != doc.is_private
                or old.content_hash != doc.content_hash
            )
        )
    ):
        frappe.throw("Final laboratory evidence must remain private, unchanged and retained")

import frappe

from av_lims.controllers import has_action_role
from av_lims.domain import TRANSITIONS


@frappe.whitelist()
def available_actions(doctype, name):
    if doctype not in TRANSITIONS:
        return []
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    if not doc.has_permission("write"):
        return []
    return [
        action
        for action, (state, _, role) in TRANSITIONS[doctype].items()
        if doc.status == state and has_action_role(role)
    ]


def can_access():
    return frappe.session.user == "Administrator" or bool(
        {"LIMS Technician", "LIMS Lead", "LIMS Manager", "LIMS Approver"} & set(frappe.get_roles())
    )

"""Deterministically generate the app-owned Frappe metadata and navigation.

Run from the repository root. The business controllers are handwritten.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "av_lims" / "av_lims"
ROLES = ["LIMS Technician", "LIMS Lead", "LIMS Manager", "LIMS Approver"]
SCHEMAS = {}
OPERATORS = {
    "Lab Inspection Test Plan": ["LIMS Lead", "LIMS Manager"],
    "Lab Hold Point Release": ["LIMS Lead", "LIMS Manager"],
    "Lab Work Request": ["LIMS Lead", "LIMS Manager"],
    "Lab Work Authorization": ["LIMS Lead", "LIMS Manager"],
    "Lab Sample": ["LIMS Lead"],
    "Lab Sample Receipt": ["LIMS Lead"],
    "Lab Work Plan": ["LIMS Lead"],
    "Lab Chain of Custody": ["LIMS Lead", "LIMS Technician"],
    "Lab Test Execution": ["LIMS Lead", "LIMS Technician"],
    "Lab Specimen": ["LIMS Lead", "LIMS Technician"],
    "Lab Conditioning Record": ["LIMS Lead", "LIMS Technician"],
    "Lab Test Schedule": ["LIMS Lead"],
    "Lab QA Review": ["LIMS Manager"],
    "Lab Nonconformance": ["LIMS Lead", "LIMS Manager"],
    "Lab Corrective Action": ["LIMS Manager"],
    "Lab Conformity Evaluation": ["LIMS Manager"],
    "Lab Result Report": ["LIMS Lead", "LIMS Manager"],
    "Lab Result Dispatch": ["LIMS Lead"],
}


def field(name, kind="Data", options=None, **kw):
    result = {"fieldname": name, "label": name.replace("_", " ").title(), "fieldtype": kind, **kw}
    if options is not None:
        result["options"] = "\n".join(options) if isinstance(options, list) else options
    return result


def link(name, target, **kw):
    return field(name, "Link", target, **kw)


def rows(name, target):
    return field(name, "Table", target)


def add(name, fields, *, child=False, single=False, master=False):
    operators = OPERATORS.get(name, ["LIMS Manager"])
    writers = set(operators)
    if name in {
        "Lab Work Authorization",
        "Lab Result Report",
        "Lab Specification Version",
        "Lab Hold Point Release",
    }:
        writers.add("LIMS Approver")
    permissions = (
        []
        if child
        else [
            {
                "role": role,
                "read": 1,
                "report": 1,
                "print": 1,
                "create": int(role in operators),
                "write": int(role in writers),
            }
            for role in ROLES
        ]
    )
    if master:
        permissions = [
            {
                "role": r,
                "read": 1,
                "report": 1,
                "print": 1,
                "create": int(r == "LIMS Manager"),
                "write": int(r in writers),
            }
            for r in ROLES
        ]
    if single:
        permissions = [{"role": "LIMS Manager", "read": 1, "write": 1}]
    if not child:
        permissions.append(
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "report": 1, "print": 1}
        )
    if not child and not single:
        fields = [field("status", read_only=1, in_list_view=1, default="Draft"), *fields]
    SCHEMAS[name] = {
        "name": name,
        "fields": fields,
        "istable": int(child),
        "issingle": int(single),
        "master": master,
        "permissions": permissions,
    }


def job_context():
    return [
        link("work_request", "Lab Work Request", reqd=1, in_list_view=1),
        link("division", "Lab Division", read_only=1),
        link("project_profile", "Lab Project Profile", read_only=1),
        link("customer", "Customer", read_only=1),
    ]


add(
    "Lab Requested Test",
    [
        link("test_definition", "Lab Test Definition", reqd=1, in_list_view=1),
        field("sample_description"),
        field("quantity", "Int", default="1"),
        field("instructions", "Small Text"),
    ],
    child=True,
)
add(
    "Lab Receipt Item",
    [
        link("sample", "Lab Sample", reqd=1, in_list_view=1),
        field("condition", "Small Text"),
        field("decision", "Select", ["Accepted", "On Hold", "Rejected"], reqd=1, in_list_view=1),
    ],
    child=True,
)
add(
    "Lab Plan Item",
    [
        link("sample", "Lab Sample", reqd=1, in_list_view=1),
        link("specimen", "Lab Specimen"),
        link("method_version", "Lab Test Method Version", reqd=1, in_list_view=1),
        link("technician", "User", reqd=1),
        field("planned_on", "Datetime"),
    ],
    child=True,
)
add(
    "Lab Custody Event",
    [
        field("event_time", "Datetime", reqd=1, in_list_view=1),
        link("from_user", "User"),
        link("to_user", "User", reqd=1),
        field("location", reqd=1),
        field("acknowledged_by", read_only=1),
        field("acknowledged_on", "Datetime", read_only=1),
        field("remarks", "Small Text"),
    ],
    child=True,
)
add(
    "Lab Method Input",
    [
        field("code", reqd=1, in_list_view=1),
        field("description"),
        link("uom", "UOM"),
        field("mandatory", "Check", default="1"),
    ],
    child=True,
)
add(
    "Lab Method Output",
    [
        field("code", reqd=1, in_list_view=1),
        field("description"),
        field("expression", reqd=1),
        link("uom", "UOM"),
        field("precision", "Int", default="3"),
    ],
    child=True,
)
add(
    "Lab Observation",
    [
        field("code", reqd=1, in_list_view=1),
        field("value", "Float", precision="9", in_list_view=1),
        field(
            "recorded",
            "Check",
            label="Value Recorded",
            in_list_view=1,
            description="Confirm that the measured value, including zero, has been entered.",
        ),
        field("remarks", "Small Text"),
    ],
    child=True,
)
add(
    "Lab Result Value",
    [
        field("code", reqd=1, in_list_view=1),
        field("value", "Float", precision="9", read_only=1, in_list_view=1),
        field("uom", read_only=1),
        field("precision", "Int", read_only=1),
    ],
    child=True,
)
add(
    "Lab Review Result",
    [link("execution", "Lab Test Execution", reqd=1, in_list_view=1), field("result_digest", read_only=1)],
    child=True,
)
add(
    "Lab Checklist Item",
    [field("question", reqd=1, in_list_view=1), field("mandatory", "Check", default="1")],
    child=True,
)
add(
    "Lab Checklist Response",
    [
        field("question", reqd=1, in_list_view=1),
        field("outcome", "Select", ["Pass", "Fail", "Not Applicable"], reqd=1),
        field("remarks", "Small Text"),
    ],
    child=True,
)
add(
    "Lab Report Item",
    [
        link("execution", "Lab Test Execution", reqd=1, in_list_view=1),
        link("qa_review", "Lab QA Review", reqd=1),
        field("result_digest", read_only=1),
    ],
    child=True,
)
add(
    "Lab Specification Limit",
    [
        field("code", reqd=1, in_list_view=1),
        field("has_lower", "Check"),
        field("lower_limit", "Float", precision="9"),
        field("has_upper", "Check"),
        field("upper_limit", "Float", precision="9"),
    ],
    child=True,
)
add("Lab Equipment Usage", [link("equipment", "Lab Equipment", reqd=1, in_list_view=1)], child=True)
add(
    "Lab Inspection Obligation",
    [
        field("title", reqd=1, in_list_view=1),
        link("test_definition", "Lab Test Definition", reqd=1),
        link("material_lot", "Lab Material Lot"),
        link("sampling_location", "Lab Sampling Location"),
        field("required_count", "Int", reqd=1),
        field("count_basis", "Select", ["Samples", "Specimens", "Executions"], reqd=1, default="Samples"),
        field("hold_point", "Check"),
        link("witness_user", "User"),
        field("frequency_reference"),
    ],
    child=True,
)
add(
    "Lab Inspection Test Plan",
    [
        *job_context(),
        field("version", reqd=1),
        field("reference", reqd=1),
        rows("obligations", "Lab Inspection Obligation"),
        field("released_by", read_only=1),
        field("released_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Hold Point Release",
    [
        *job_context(),
        link("inspection_plan", "Lab Inspection Test Plan", reqd=1),
        field("obligation_id", reqd=1, description="Row ID of the held obligation on the inspection plan."),
        field("evidence", "Attach", reqd=1),
        field("remarks", "Small Text"),
        field("approved_by", read_only=1),
        field("approved_on", "Datetime", read_only=1),
    ],
)

add(
    "Lab Settings",
    [
        field(
            "policies_confirmed",
            "Check",
            description="Confirm approved business policies before operational actions are enabled.",
        ),
        field("require_signed_authorization", "Check", default="1"),
        field("allow_self_review", "Check", default="0"),
        field("allow_partial_reports", "Check", default="0"),
        field("enforce_competency", "Check", default="0"),
        field("enforce_equipment_validity", "Check", default="0"),
        field("policy_notes", "Small Text"),
    ],
    single=True,
)
add("Lab Division", [field("title", reqd=1, in_list_view=1), link("company", "Company", reqd=1)], master=True)
add(
    "Lab Sample Type",
    [
        field("title", reqd=1, in_list_view=1),
        field("receipt_instructions", "Small Text"),
        field("retention_days", "Int"),
    ],
    master=True,
)
add(
    "Lab Test Definition",
    [
        field("title", reqd=1, in_list_view=1),
        link("sample_type", "Lab Sample Type"),
        field("requires_specimen", "Check"),
        field("requires_conditioning", "Check"),
        field("requires_equipment", "Check"),
        field("description", "Small Text"),
    ],
    master=True,
)
add(
    "Lab Test Method Version",
    [
        link("test_definition", "Lab Test Definition", reqd=1, in_list_view=1),
        field("version", reqd=1, in_list_view=1),
        field("standard_reference"),
        field("procedure", "Text Editor"),
        rows("inputs", "Lab Method Input"),
        rows("outputs", "Lab Method Output"),
        field("approved_by", read_only=1),
        field("approved_on", "Datetime", read_only=1),
    ],
    master=True,
)
add(
    "Lab QA Checklist Version",
    [
        field("title", reqd=1, in_list_view=1),
        field("version", reqd=1),
        rows("questions", "Lab Checklist Item"),
        field("approved_by", read_only=1),
        field("approved_on", "Datetime", read_only=1),
    ],
    master=True,
)
add(
    "Lab Project Profile",
    [
        link("project", "Project", reqd=1, in_list_view=1),
        link("customer", "Customer", reqd=1),
        link("division", "Lab Division", reqd=1),
        field("site_name"),
        field("report_instructions", "Small Text"),
    ],
    master=True,
)
add(
    "Lab Sampling Location",
    [
        link("project_profile", "Lab Project Profile", reqd=1),
        field("title", reqd=1, in_list_view=1),
        field("structure"),
        field("element"),
        field("chainage"),
        field("layer"),
        field("borehole"),
        field("depth", "Float"),
        field("latitude", "Float", precision="9"),
        field("longitude", "Float", precision="9"),
    ],
    master=True,
)
add(
    "Lab Material Lot",
    [
        link("project_profile", "Lab Project Profile", reqd=1),
        field("lot_reference", reqd=1, in_list_view=1),
        link("supplier", "Supplier"),
        link("item", "Item"),
        field("source_location"),
        field("delivery_ticket"),
        field("pour_reference"),
        field("mix_reference"),
        field("grade"),
        field("produced_on", "Datetime"),
    ],
    master=True,
)
add(
    "Lab Specification Version",
    [
        link("project_profile", "Lab Project Profile", reqd=1),
        link("test_definition", "Lab Test Definition", reqd=1),
        field("version", reqd=1),
        field("reference", reqd=1),
        field("decision_rule", "Select", ["Simple Acceptance"], default="Simple Acceptance", reqd=1),
        rows("limits", "Lab Specification Limit"),
        field("approved_by", read_only=1),
        field("approved_on", "Datetime", read_only=1),
    ],
    master=True,
)
add(
    "Lab Equipment",
    [
        field("title", reqd=1, in_list_view=1),
        link("asset", "Asset"),
        field("serial_number"),
        field("disabled", "Check"),
    ],
    master=True,
)
add(
    "Lab Equipment Check",
    [
        link("equipment", "Lab Equipment", reqd=1, in_list_view=1),
        field("checked_on", "Date", reqd=1),
        field("valid_until", "Date", reqd=1),
        field("certificate", "Attach", reqd=1),
        field("verified_by", read_only=1),
        field("verified_on", "Datetime", read_only=1),
    ],
    master=True,
)
add(
    "Lab Competency",
    [
        link("user", "User", reqd=1, in_list_view=1),
        link("test_definition", "Lab Test Definition", reqd=1),
        field("valid_from", "Date", reqd=1),
        field("valid_until", "Date", reqd=1),
        field("can_test", "Check"),
        field("can_process", "Check"),
        field("can_review", "Check"),
        field("can_approve", "Check"),
        field("evidence", "Attach", reqd=1),
        field("verified_by", read_only=1),
        field("verified_on", "Datetime", read_only=1),
    ],
    master=True,
)

add(
    "Lab Work Request",
    [
        link("customer", "Customer", reqd=1, in_list_view=1),
        link("contact", "Contact"),
        link("division", "Lab Division", reqd=1),
        link("project_profile", "Lab Project Profile", reqd=1),
        field("client_reference"),
        field("test_program", "Attach", reqd=1),
        field("program_revision", reqd=1),
        link("quotation", "Quotation"),
        field("fee_estimate", "Attach"),
        rows("requested_tests", "Lab Requested Test"),
        field("instructions", "Small Text"),
    ],
)
add(
    "Lab Work Authorization",
    [
        *job_context(),
        field("basis", "Select", ["Contract", "Fee Estimate"], reqd=1),
        field("document_reference", reqd=1),
        field("document_revision", reqd=1),
        field("signed_evidence", "Attach", reqd=1),
        field("signatory", reqd=1),
        field("signed_on", "Date", reqd=1),
        field("scope_digest", read_only=1),
        field("authorized_by", read_only=1),
        field("authorized_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Sample",
    [
        *job_context(),
        field("client_sample_reference", reqd=1, in_list_view=1),
        link("sample_type", "Lab Sample Type", reqd=1),
        link("sampling_location", "Lab Sampling Location", reqd=1),
        link("material_lot", "Lab Material Lot"),
        link("specification", "Lab Specification Version"),
        field("sampled_on", "Datetime", reqd=1),
        field("quantity", "Float", reqd=1),
        link("uom", "UOM", reqd=1),
        field("current_location"),
        link("receipt", "Lab Sample Receipt", read_only=1),
        field("receipt_decision", read_only=1),
        link("parent_sample", "Lab Sample"),
        field("remarks", "Small Text"),
    ],
)
add(
    "Lab Sample Receipt",
    [
        *job_context(),
        field("received_on", "Datetime", reqd=1),
        field("delivery_reference"),
        field("signed_work_request", "Attach", reqd=1),
        rows("samples", "Lab Receipt Item"),
        field("received_by", read_only=1),
    ],
)
add(
    "Lab Work Plan",
    [
        *job_context(),
        rows("assignments", "Lab Plan Item"),
        field("released_by", read_only=1),
        field("released_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Chain of Custody",
    [
        *job_context(),
        link("sample", "Lab Sample", reqd=1, in_list_view=1),
        link("work_plan", "Lab Work Plan", reqd=1),
        rows("events", "Lab Custody Event"),
        field("completion_evidence", "Attach"),
        field("completed_by", read_only=1),
        field("completed_on", "Datetime", read_only=1),
        field("last_reopen_reason", "Small Text", read_only=1),
        field("reopened_by", read_only=1),
        field("reopened_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Specimen",
    [
        *job_context(),
        link("sample", "Lab Sample", reqd=1, in_list_view=1),
        field("set_reference", reqd=1),
        field("specimen_type", reqd=1),
        field("prepared_on", "Datetime", reqd=1),
        field("mould_reference"),
        field("dimensions"),
        field("preparation_notes", "Small Text"),
    ],
)
add(
    "Lab Conditioning Record",
    [
        *job_context(),
        link("sample", "Lab Sample", reqd=1),
        link("specimen", "Lab Specimen", reqd=1),
        field("condition_type", reqd=1),
        field("location", reqd=1),
        field("started_on", "Datetime", reqd=1),
        field("ended_on", "Datetime", reqd=1),
        field("observations", "Small Text", reqd=1),
        field("completed_by", read_only=1),
        field("completed_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Test Schedule",
    [
        *job_context(),
        link("sample", "Lab Sample", reqd=1),
        link("specimen", "Lab Specimen", reqd=1),
        link("method_version", "Lab Test Method Version", reqd=1),
        field("target_age_hours", "Float", reqd=1),
        field("early_tolerance_hours", "Float"),
        field("late_tolerance_hours", "Float"),
        field("due_on", "Datetime", read_only=1),
        field("window_start", "Datetime", read_only=1),
        field("window_end", "Datetime", read_only=1),
        field("execution", "Link", "Lab Test Execution", read_only=1),
    ],
)
add(
    "Lab Test Execution",
    [
        *job_context(),
        link("sample", "Lab Sample", reqd=1, in_list_view=1),
        link("specimen", "Lab Specimen"),
        link("work_plan", "Lab Work Plan", reqd=1),
        link("custody", "Lab Chain of Custody", reqd=1),
        link("method_version", "Lab Test Method Version", reqd=1),
        link("test_schedule", "Lab Test Schedule"),
        link("supersedes", "Lab Test Execution"),
        field("change_reason", "Small Text"),
        field("tested_on", "Datetime", reqd=1),
        rows("observations", "Lab Observation"),
        rows("equipment", "Lab Equipment Usage"),
        field("raw_evidence", "Attach"),
        rows("results", "Lab Result Value"),
        field("method_snapshot", "Code", "JSON", read_only=1),
        field("result_digest", read_only=1),
        field("tested_by", read_only=1),
        field("raw_completed_on", "Datetime", read_only=1),
        field("processed_by", read_only=1),
        field("processed_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab QA Review",
    [
        *job_context(),
        link("checklist_version", "Lab QA Checklist Version", reqd=1),
        rows("results", "Lab Review Result"),
        rows("responses", "Lab Checklist Response"),
        field("remarks", "Small Text"),
        link("corrective_action", "Lab Corrective Action"),
        field("reviewed_by", read_only=1),
        field("reviewed_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Nonconformance",
    [
        *job_context(),
        link("sample", "Lab Sample", reqd=1),
        link("execution", "Lab Test Execution", reqd=1),
        field("origin", "Select", ["Processing", "QA"], reqd=1),
        field("issue", "Small Text", reqd=1),
        field("containment", "Small Text", reqd=1),
        field("closed_by", read_only=1),
        field("closed_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Corrective Action",
    [
        *job_context(),
        link("nonconformance", "Lab Nonconformance", reqd=1),
        field("action_taken", "Small Text", reqd=1),
        field("evidence", "Attach", reqd=1),
        link("replacement_execution", "Lab Test Execution"),
        field("completed_by", read_only=1),
        field("completed_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Conformity Evaluation",
    [
        *job_context(),
        link("specification", "Lab Specification Version", reqd=1),
        rows("results", "Lab Review Result"),
        field("evaluation_snapshot", "Code", "JSON", read_only=1),
        field("outcome", read_only=1),
        field("evaluated_by", read_only=1),
        field("evaluated_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Result Report",
    [
        *job_context(),
        rows("results", "Lab Report Item"),
        link("conformity_evaluation", "Lab Conformity Evaluation"),
        link("supersedes", "Lab Result Report"),
        field("change_reason", "Small Text"),
        field("report_title", reqd=1),
        field("remarks", "Small Text"),
        field("snapshot", "Code", "JSON", read_only=1),
        field("snapshot_digest", read_only=1),
        field("approved_file", "Attach", read_only=1),
        field("approved_by", read_only=1),
        field("approved_on", "Datetime", read_only=1),
    ],
)
add(
    "Lab Result Dispatch",
    [
        *job_context(),
        link("report", "Lab Result Report", reqd=1),
        field("recipient", reqd=1),
        field("channel", "Select", ["Email", "Physical", "Other"], reqd=1),
        field("delivery_outcome", "Select", ["Pending", "Delivered", "Failed"], default="Pending"),
        field("delivery_evidence", "Attach"),
        field("remarks", "Small Text"),
        field("issued_by", read_only=1),
        field("issued_on", "Datetime", read_only=1),
    ],
)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + "\n")


def generate():
    for name, schema in SCHEMAS.items():
        slug = name.lower().replace(" ", "_")
        folder = MODULE / "doctype" / slug
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "__init__.py").write_text("")
        cls = name.replace(" ", "")
        base = "Document" if schema["istable"] else "LabDocument"
        imp = (
            "from frappe.model.document import Document"
            if schema["istable"]
            else "from av_lims.controllers import LabDocument"
        )
        (folder / (slug + ".py")).write_text(f"{imp}\n\n\nclass {cls}({base}):\n    pass\n")
        fields = schema["fields"]
        if not schema["istable"]:
            laid_out = []
            for idx, f in enumerate(fields):
                if idx == 0:
                    laid_out.append(field("details_section", "Section Break", label="Details"))
                if f["fieldtype"] == "Table":
                    laid_out.append(field(f["fieldname"] + "_section", "Section Break", label=f["label"]))
                elif idx and fields[idx - 1]["fieldtype"] == "Table":
                    laid_out.append(
                        field(
                            "after_" + fields[idx - 1]["fieldname"],
                            "Section Break",
                            label="Additional Details",
                        )
                    )
                elif idx and idx % 5 == 0:
                    laid_out.append(field("column_" + str(idx), "Column Break"))
                laid_out.append(f)
            fields = laid_out
        meta = {
            "doctype": "DocType",
            "name": name,
            "module": "AV LIMS",
            "engine": "InnoDB",
            "istable": schema["istable"],
            "issingle": schema["issingle"],
            "autoname": "hash"
            if schema["istable"]
            else "format:AVL-" + "".join(x[0] for x in name.split()[1:]).upper() + "-{#####}",
            "field_order": [f["fieldname"] for f in fields],
            "fields": fields,
            "permissions": schema["permissions"],
            "track_changes": int(not schema["istable"]),
            "sort_field": "modified",
            "sort_order": "DESC",
            "actions": [],
            "links": [],
            "states": [],
        }
        if schema["issingle"]:
            meta.pop("autoname")
        write_json(folder / (slug + ".json"), meta)
    (MODULE / "doctype" / "__init__.py").write_text("")
    navigation()
    reports()


def reports():
    for name, dt in [
        ("Lab Work Register", "Lab Work Request"),
        ("Lab Test Due Register", "Lab Test Schedule"),
        ("Lab Nonconformance Register", "Lab Nonconformance"),
        ("Lab ITP Coverage", "Lab Inspection Test Plan"),
    ]:
        slug = name.lower().replace(" ", "_")
        write_json(
            MODULE / "report" / slug / (slug + ".json"),
            {
                "doctype": "Report",
                "name": name,
                "report_name": name,
                "ref_doctype": dt,
                "report_type": "Script Report",
                "is_standard": "Yes",
                "module": "AV LIMS",
                "add_total_row": 0,
                "disabled": 0,
                "roles": [{"role": r} for r in ROLES],
            },
        )


def navigation():
    groups = {
        "Intake and Planning": [
            "Lab Inspection Test Plan",
            "Lab Hold Point Release",
            "Lab Work Request",
            "Lab Work Authorization",
            "Lab Sample Receipt",
            "Lab Sample",
            "Lab Work Plan",
        ],
        "Testing": [
            "Lab Chain of Custody",
            "Lab Specimen",
            "Lab Conditioning Record",
            "Lab Test Schedule",
            "Lab Test Execution",
        ],
        "Review and Release": [
            "Lab QA Review",
            "Lab Nonconformance",
            "Lab Corrective Action",
            "Lab Conformity Evaluation",
            "Lab Result Report",
            "Lab Result Dispatch",
        ],
        "Project Masters": [
            "Lab Project Profile",
            "Lab Sampling Location",
            "Lab Material Lot",
            "Lab Specification Version",
        ],
        "Laboratory Setup": [
            "Lab Division",
            "Lab Sample Type",
            "Lab Test Definition",
            "Lab Test Method Version",
            "Lab QA Checklist Version",
            "Lab Equipment",
            "Lab Equipment Check",
            "Lab Competency",
            "Lab Settings",
        ],
        "Reports": [
            "Lab Work Register",
            "Lab Test Due Register",
            "Lab Nonconformance Register",
            "Lab ITP Coverage",
        ],
    }
    items = [{"type": "Link", "label": "Home", "link_type": "Workspace", "link_to": "AV LIMS"}]
    links = []
    blocks = [{"id": "heading", "type": "header", "data": {"text": "AV LIMS", "col": 12}}]
    for idx, (label, names) in enumerate(groups.items()):
        items.append({"type": "Section Break", "label": label, "collapsible": 1})
        links.append({"type": "Card Break", "label": label})
        for name in names:
            kind = "Report" if label == "Reports" else "DocType"
            items.append(
                {
                    "type": "Link",
                    "label": name.removeprefix("Lab "),
                    "link_type": kind,
                    "link_to": name,
                    "child": 1,
                    "is_default_module": 1,
                }
            )
            links.append(
                {
                    "type": "Link",
                    "label": name.removeprefix("Lab "),
                    "link_type": kind,
                    "link_to": name,
                    "is_query_report": int(kind == "Report"),
                }
            )
        blocks.append({"id": f"card-{idx}", "type": "card", "data": {"card_name": label, "col": 4}})
    write_json(
        MODULE / "sidebar" / "av_lims" / "av_lims.json",
        {
            "doctype": "Sidebar",
            "name": "AV LIMS",
            "title": "AV LIMS",
            "module": "AV LIMS",
            "app": "av_lims",
            "standard": 1,
            "header_icon": "🧪",
            "items": items,
        },
    )
    write_json(
        ROOT / "av_lims" / "dock" / "av_lims" / "av_lims.json",
        {
            "doctype": "Dock",
            "name": "av_lims",
            "app": "av_lims",
            "standard": 1,
            "items": [{"link_type": "Sidebar", "link_to": "AV LIMS", "title": "AV LIMS", "icon": "🧪"}],
        },
    )
    write_json(
        MODULE / "workspace" / "av_lims" / "av_lims.json",
        {
            "doctype": "Workspace",
            "name": "AV LIMS",
            "label": "AV LIMS",
            "title": "AV LIMS",
            "module": "AV LIMS",
            "standard": 1,
            "public": 1,
            "type": "Workspace",
            "icon": "quality",
            "content": json.dumps(blocks),
            "links": links,
            "roles": [{"role": r} for r in ROLES],
            "charts": [],
            "number_cards": [],
            "shortcuts": [],
            "quick_lists": [],
            "custom_blocks": [],
        },
    )
    manifest = {
        n: {"master": s["master"], "child": bool(s["istable"]), "single": bool(s["issingle"])}
        for n, s in SCHEMAS.items()
    }
    write_json(ROOT / "av_lims" / "schema_manifest.json", manifest)


if __name__ == "__main__":
    generate()

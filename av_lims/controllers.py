"""Server-enforced laboratory state transitions and record consistency."""

import json
from contextvars import ContextVar

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, now_datetime

from av_lims.domain import (
    TRANSITIONS,
    LabRuleError,
    digest,
    evaluate_conformity,
    process_results,
    schedule_window,
    validate_method,
)

_ACTION = ContextVar("lims_action", default=None)
ROLE_MAP = {
    "technician": {"LIMS Technician", "LIMS Lead"},
    "lead": {"LIMS Lead"},
    "manager": {"LIMS Manager"},
    "approver": {"LIMS Approver"},
}
CONTEXT_FIELDS = ("division", "project_profile", "customer")
RAW_FIELDS = (
    "sample",
    "specimen",
    "work_plan",
    "custody",
    "method_version",
    "test_schedule",
    "tested_on",
    "observations",
    "equipment",
    "raw_evidence",
)
OUTPUT_FIELDS = {
    "last_reopen_reason",
    "reopened_by",
    "reopened_on",
    "method_snapshot",
    "result_digest",
    "results",
    "snapshot",
    "snapshot_digest",
    "approved_file",
    "scope_digest",
    "evaluation_snapshot",
    "outcome",
    "approved_by",
    "approved_on",
    "authorized_by",
    "authorized_on",
    "received_by",
    "tested_by",
    "raw_completed_on",
    "processed_by",
    "processed_on",
    "reviewed_by",
    "reviewed_on",
    "verified_by",
    "verified_on",
    "released_by",
    "released_on",
    "completed_by",
    "completed_on",
    "closed_by",
    "closed_on",
    "issued_by",
    "issued_on",
    "evaluated_by",
    "evaluated_on",
    "receipt",
    "receipt_decision",
    "execution",
}
LINK_CONTEXT = {
    "sample": "Lab Sample",
    "specimen": "Lab Specimen",
    "sampling_location": "Lab Sampling Location",
    "material_lot": "Lab Material Lot",
    "specification": "Lab Specification Version",
    "execution": "Lab Test Execution",
    "work_plan": "Lab Work Plan",
    "custody": "Lab Chain of Custody",
    "nonconformance": "Lab Nonconformance",
    "replacement_execution": "Lab Test Execution",
    "corrective_action": "Lab Corrective Action",
    "report": "Lab Result Report",
    "conformity_evaluation": "Lab Conformity Evaluation",
    "inspection_plan": "Lab Inspection Test Plan",
    "parent_sample": "Lab Sample",
}


def require(condition, message):
    if not condition:
        frappe.throw(message)


def linked(doctype, name):
    require(bool(name), f"A {doctype} reference is required")
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    return doc


def data_rows(doc, field, keys):
    return [{k: row.get(k) for k in keys} for row in doc.get(field) or []]


def same_value(a, b):
    def clean(v):
        if hasattr(v, "as_dict"):
            v = v.as_dict()
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        if isinstance(v, dict):
            return {
                k: clean(x)
                for k, x in v.items()
                if k not in {"modified", "modified_by", "creation", "owner", "docstatus", "idx"}
            }
        return v

    return digest(clean(a)) == digest(clean(b))


def document_payload(doc):
    return {
        f.fieldname: doc.get(f.fieldname)
        for f in doc.meta.fields
        if f.fieldtype not in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}
    }


def has_action_role(role):
    # Administrator is the explicit audited bootstrap account, not every System Manager.
    return frappe.session.user == "Administrator" or bool(ROLE_MAP[role] & set(frappe.get_roles()))


def private_evidence(url):
    require(bool(url), "Private evidence is required")
    files = frappe.get_all("File", filters={"file_url": url, "is_private": 1}, pluck="name")
    require(bool(files), "Evidence must be an uploaded private File, not an external URL")
    require(
        any(frappe.has_permission("File", "read", doc=name) for name in files),
        "Evidence is not accessible to this user",
    )


def request_digest(doc):
    return digest(
        {
            "customer": doc.customer,
            "division": doc.division,
            "project_profile": doc.project_profile,
            "test_program": doc.test_program,
            "program_revision": doc.program_revision,
            "requested_tests": data_rows(
                doc, "requested_tests", ["test_definition", "sample_description", "quantity", "instructions"]
            ),
            "quotation": doc.quotation,
            "fee_estimate": doc.fee_estimate,
            "instructions": doc.instructions,
        }
    )


def require_authorization(request):
    settings = frappe.get_single("Lab Settings")
    if not settings.require_signed_authorization:
        return
    authorizations = frappe.get_list(
        "Lab Work Authorization",
        filters={"work_request": request.name, "status": "Authorized"},
        fields=["scope_digest"],
        limit_page_length=1000,
    )
    require(
        any(a.scope_digest == request_digest(request) for a in authorizations),
        "Current work scope requires signed Head of Division authorization",
    )


def competency(user, method, capability, on_date):
    if not frappe.get_single("Lab Settings").enforce_competency:
        return
    require(
        frappe.db.exists(
            "Lab Competency",
            {
                "user": user,
                "test_definition": method.test_definition,
                "status": "Verified",
                "valid_from": ["<=", getdate(on_date)],
                "valid_until": [">=", getdate(on_date)],
                "can_" + capability: 1,
            },
        ),
        f"{user} has no valid {capability} competency for this test",
    )


def no_self_review(users):
    if not frappe.get_single("Lab Settings").allow_self_review:
        require(
            frappe.session.user not in users,
            "The performer cannot review or approve their own work under current policy",
        )


def execution_is_current(execution):
    require(execution.status == "Processed", "Only processed result revisions are eligible")
    require(
        linked("Lab Chain of Custody", execution.custody).status == "Completed",
        "Reopened custody holds affected results",
    )
    require(
        not frappe.db.exists("Lab Test Execution", {"supersedes": execution.name, "status": "Processed"}),
        "A newer processed result supersedes this revision",
    )
    open_ncr = frappe.get_list(
        "Lab Nonconformance",
        filters={"work_request": execution.work_request, "status": "Open"},
        fields=["name", "execution"],
        limit_page_length=1000,
    )
    lineage = {execution.name}
    parent = execution.supersedes
    while parent:
        require(parent not in lineage, "Result revision lineage contains a cycle")
        lineage.add(parent)
        parent = linked("Lab Test Execution", parent).supersedes
    for ncr in open_ncr:
        if ncr.execution in lineage:
            require(False, "An open laboratory nonconformance holds this result")


class LabDocument(Document):
    def validate(self):
        try:
            self._validate()
        except LabRuleError as exc:
            frappe.throw(str(exc))

    def _validate(self):
        old = self.get_doc_before_save()
        action = _ACTION.get()
        authorized = action and action[:2] == (self.doctype, self.name)
        require(not self.docstatus, "Laboratory records use controlled actions, not direct submit/cancel")
        if self.doctype != "Lab Settings":
            if self.is_new():
                require(self.status in (None, "", "Draft"), "Create records in Draft")
                self.status = "Draft"
            if old:
                if self.status != old.status:
                    require(authorized, "Use the authorized laboratory action to change status")
                if old.status not in ("Draft", "Active", "Raw Complete"):
                    before, after = document_payload(old), document_payload(self)
                    if authorized:
                        before = {k: v for k, v in before.items() if k not in OUTPUT_FIELDS | {"status"}}
                        after = {k: v for k, v in after.items() if k not in OUTPUT_FIELDS | {"status"}}
                    require(
                        same_value(after, before),
                        "Final laboratory records are immutable; create a linked revision",
                    )
                if old.status == "Raw Complete":
                    require(
                        all(same_value(self.get(f), old.get(f)) for f in RAW_FIELDS),
                        "Completed raw evidence cannot be edited",
                    )
                if old.status == "Active" and self.doctype == "Lab Chain of Custody":
                    require(
                        self.sample == old.sample
                        and self.work_plan == old.work_plan
                        and self.work_request == old.work_request,
                        "Active custody identity is locked",
                    )
            for f in OUTPUT_FIELDS:
                if f == "results" and self.doctype != "Lab Test Execution":
                    continue
                if f == "execution" and self.doctype != "Lab Test Schedule":
                    continue
                if self.meta.has_field(f) and not authorized:
                    require(
                        same_value(self.get(f), old.get(f) if old else None)
                        or (not self.get(f) and not (old and old.get(f))),
                        f"{f} is maintained by laboratory actions",
                    )
        self.validate_context()
        self.validate_specific()
        if self.doctype == "Lab Chain of Custody" and not old:
            require(
                all(not r.acknowledged_by and not r.acknowledged_on for r in self.events),
                "Custody acknowledgements cannot be supplied on creation",
            )
        if old and self.doctype == "Lab Chain of Custody":
            before = {x.name: x for x in old.events}
            after = {x.name: x for x in self.events}
            for name, row in before.items():
                if row.acknowledged_by:
                    require(
                        name in after and same_value(row.as_dict(), after[name].as_dict()),
                        "Acknowledged custody events are append-only",
                    )
            if not authorized:
                for row in self.events:
                    previous = before.get(row.name)
                    require(
                        row.acknowledged_by == (previous.acknowledged_by if previous else None)
                        and row.acknowledged_on == (previous.acknowledged_on if previous else None),
                        "Acknowledge custody events through the controlled action",
                    )

    def validate_context(self):
        if self.get("work_request"):
            request = linked("Lab Work Request", self.work_request)
            for f in CONTEXT_FIELDS:
                if self.meta.has_field(f):
                    self.set(f, request.get(f))
        profile = linked("Lab Project Profile", self.project_profile) if self.get("project_profile") else None
        if profile and self.get("customer"):
            require(profile.customer == self.customer, "Project profile and customer differ")
        if profile and self.get("division"):
            require(profile.division == self.division, "Project profile and division differ")
        for f, dt in LINK_CONTEXT.items():
            if not self.get(f):
                continue
            ref = linked(dt, self.get(f))
            if self.get("work_request") and ref.get("work_request"):
                require(ref.work_request == self.work_request, f"{f} belongs to a different work request")
            if self.get("project_profile") and ref.get("project_profile"):
                require(ref.project_profile == self.project_profile, f"{f} belongs to another project")
            if self.get("sample") and ref.get("sample"):
                require(ref.sample == self.sample, f"{f} belongs to a different sample")

    def validate_specific(self):
        dt = self.doctype
        if dt == "Lab Work Request":
            require(bool(self.requested_tests), "At least one requested test is required")
            if self.contact:
                contact = linked("Contact", self.contact)
                require(
                    any(x.link_doctype == "Customer" and x.link_name == self.customer for x in contact.links),
                    "Contact must be linked to the selected customer",
                )
            if self.quotation:
                q = linked("Quotation", self.quotation)
                require(
                    q.quotation_to == "Customer" and q.party_name == self.customer,
                    "Quotation must belong to this customer",
                )
        elif dt == "Lab Test Definition":
            old = self.get_doc_before_save()
            if old and frappe.db.exists(
                "Lab Test Method Version", {"test_definition": self.name, "status": "Approved"}
            ):
                require(
                    all(
                        self.get(f) == old.get(f)
                        for f in [
                            "sample_type",
                            "requires_specimen",
                            "requires_conditioning",
                            "requires_equipment",
                        ]
                    ),
                    "An approved method uses this definition; create a new definition to change testing requirements",
                )
        elif dt == "Lab Project Profile":
            project = linked("Project", self.project)
            require(
                not project.customer or project.customer == self.customer,
                "ERPNext project belongs to another customer",
            )
            division = linked("Lab Division", self.division)
            require(
                not project.company or project.company == division.company,
                "Project and laboratory companies differ",
            )
            old = self.get_doc_before_save()
            if old and frappe.db.exists("Lab Work Request", {"project_profile": self.name}):
                require(
                    all(self.get(f) == old.get(f) for f in ["project", "customer", "division"]),
                    "An active project's identity cannot be reassigned",
                )
        elif dt == "Lab Sample":
            require(self.quantity > 0, "Sample quantity must be positive")
            require(self.parent_sample != self.name, "A sample cannot be its own parent")
            parent = self.parent_sample
            seen = {self.name}
            while parent:
                require(parent not in seen, "Sample lineage contains a cycle")
                seen.add(parent)
                parent = linked("Lab Sample", parent).parent_sample
            old = self.get_doc_before_save()
            if old and old.receipt:
                require(
                    same_value(document_payload(self), document_payload(old))
                    or (_ACTION.get() and _ACTION.get()[:2] == (self.doctype, self.name)),
                    "Received sample identity is locked; register a replacement or subsample",
                )
        elif dt == "Lab Specimen":
            old = self.get_doc_before_save()
            if old and (
                frappe.db.exists("Lab Work Plan", {"status": "Released", "work_request": self.work_request})
                or frappe.db.exists("Lab Test Schedule", {"specimen": self.name})
            ):
                require(
                    same_value(document_payload(self), document_payload(old)),
                    "Planned specimen identity is locked",
                )
        elif dt == "Lab Test Method Version":
            validate_method(
                data_rows(self, "inputs", ["code", "mandatory"]),
                data_rows(self, "outputs", ["code", "expression", "precision"]),
            )
        elif dt == "Lab Specification Version":
            # Validate limit structure without treating laboratory QA as material conformity.
            limits = data_rows(
                self, "limits", ["code", "has_lower", "lower_limit", "has_upper", "upper_limit"]
            )
            evaluate_conformity([{"code": x["code"], "value": 0} for x in limits], limits)
        elif dt == "Lab QA Checklist Version":
            require(bool(self.questions), "A checklist needs questions")
            require(
                len({x.question for x in self.questions}) == len(self.questions),
                "Checklist questions must be distinct",
            )
        elif dt in {"Lab Equipment Check", "Lab Competency"}:
            start = self.get("checked_on") or self.get("valid_from")
            require(getdate(start) <= getdate(self.valid_until), "Validity dates are reversed")
        elif dt == "Lab Test Schedule":
            specimen = linked("Lab Specimen", self.specimen)
            self.due_on, self.window_start, self.window_end = schedule_window(
                get_datetime(specimen.prepared_on),
                self.target_age_hours,
                self.early_tolerance_hours or 0,
                self.late_tolerance_hours or 0,
            )
        elif dt == "Lab Conditioning Record":
            require(
                get_datetime(self.ended_on) >= get_datetime(self.started_on),
                "Conditioning dates are reversed",
            )
        elif dt == "Lab Test Execution":
            require(get_datetime(self.tested_on) <= now_datetime(), "Testing time cannot be in the future")
            require(self.supersedes != self.name, "A test cannot supersede itself")
            if self.supersedes:
                previous = linked("Lab Test Execution", self.supersedes)
                require(
                    previous.status == "Processed"
                    and previous.sample == self.sample
                    and (previous.specimen or "") == (self.specimen or "")
                    and previous.method_version == self.method_version,
                    "Replacement must preserve sample and method identity",
                )
                require(bool(self.change_reason), "A replacement result needs a change reason")
            plan = linked("Lab Work Plan", self.work_plan)
            require(
                any(
                    x.sample == self.sample
                    and (x.specimen or "") == (self.specimen or "")
                    and x.method_version == self.method_version
                    for x in plan.assignments
                ),
                "Execution does not match a planned assignment",
            )
        elif dt == "Lab Result Report":
            require(self.supersedes != self.name, "A report cannot supersede itself")
            if self.supersedes:
                previous = linked("Lab Result Report", self.supersedes)
                require(
                    previous.work_request == self.work_request and previous.status == "Approved",
                    "Only this job's approved report can be amended",
                )
                require(bool(self.change_reason), "Report amendment needs a reason")

    def on_trash(self):
        require(self.get("status") in (None, "", "Draft"), "Final laboratory records cannot be deleted")

    @frappe.whitelist()
    def run_action(self, action, reason=None):
        self.check_permission("write")
        require(not self.is_new(), "Save the record before taking an action")
        # Reload prevents stale client copies from replacing evidence during an action.
        frappe.db.get_value(self.doctype, self.name, "name", for_update=True)
        self.reload()
        self.check_permission("write")
        if self.get("work_request"):
            frappe.db.get_value("Lab Work Request", self.work_request, "name", for_update=True)
        transitions = TRANSITIONS.get(self.doctype, {})
        require(action in transitions, "Unknown laboratory action")
        old_status, new_status, role = transitions[action]
        require(self.status == old_status, "This action is not available in the current state")
        require(has_action_role(role), "Your laboratory role cannot perform this action")
        settings = frappe.get_single("Lab Settings")
        require(
            settings.policies_confirmed
            or self.doctype
            in {
                "Lab Test Method Version",
                "Lab QA Checklist Version",
                "Lab Specification Version",
                "Lab Equipment Check",
                "Lab Competency",
            },
            "Confirm approved operational policies in Lab Settings before using laboratory actions",
        )
        token = _ACTION.set((self.doctype, self.name, action))
        try:
            self._action_reason = reason
            self.apply_action(action)
            self.status = new_status
            self.save()
        finally:
            _ACTION.reset(token)
        return {"name": self.name, "status": self.status}

    @frappe.whitelist()
    def acknowledge(self, event_name):
        self.check_permission("write")
        frappe.db.get_value(self.doctype, self.name, "name", for_update=True)
        self.reload()
        self.check_permission("write")
        require(
            frappe.get_single("Lab Settings").policies_confirmed, "Operational policies must be confirmed"
        )
        require(self.doctype == "Lab Chain of Custody" and self.status == "Active", "Custody must be active")
        row = next((x for x in self.events if x.name == event_name), None)
        require(row and not row.acknowledged_by, "Select an unacknowledged custody event")
        require(row.to_user == frappe.session.user, "Only the named receiver can acknowledge this event")
        require(get_datetime(row.event_time) <= now_datetime(), "Cannot acknowledge a future transfer")
        token = _ACTION.set((self.doctype, self.name, "Acknowledge"))
        try:
            row.acknowledged_by = frappe.session.user
            row.acknowledged_on = now_datetime()
            self.save()
        finally:
            _ACTION.reset(token)
        return self.name

    def apply_action(self, action):
        user, at, dt = frappe.session.user, now_datetime(), self.doctype
        if dt == "Lab Inspection Test Plan":
            require(bool(self.obligations), "Inspection plan needs testing obligations")
            for row in self.obligations:
                require(row.required_count > 0, "Required test count must be positive")
                for name, target in [
                    (row.material_lot, "Lab Material Lot"),
                    (row.sampling_location, "Lab Sampling Location"),
                ]:
                    if name:
                        require(
                            linked(target, name).project_profile == self.project_profile,
                            "Inspection scope belongs to another project",
                        )
            self.released_by, self.released_on = user, at
        elif dt == "Lab Hold Point Release":
            plan = linked("Lab Inspection Test Plan", self.inspection_plan)
            require(plan.status == "Released", "Inspection plan must be released")
            obligation = next((x for x in plan.obligations if x.name == self.obligation_id), None)
            require(obligation and obligation.hold_point, "Select a held inspection obligation")
            require(
                not obligation.witness_user or obligation.witness_user == user,
                "Only the named witness can release this hold",
            )
            private_evidence(self.evidence)
            self.approved_by, self.approved_on = user, at
        elif dt == "Lab Work Authorization":
            require(getdate(self.signed_on) <= getdate(at), "Signature date cannot be in the future")
            private_evidence(self.signed_evidence)
            request = linked("Lab Work Request", self.work_request)
            private_evidence(request.test_program)
            require(
                bool(request.quotation or request.fee_estimate) if self.basis == "Fee Estimate" else True,
                "A fee estimate or Quotation must be retained",
            )
            self.scope_digest = request_digest(request)
            self.authorized_by, self.authorized_on = user, at
        elif dt == "Lab Sample Receipt":
            require(get_datetime(self.received_on) <= at, "Receipt time cannot be in the future")
            require_authorization(linked("Lab Work Request", self.work_request))
            private_evidence(self.signed_work_request)
            require(bool(self.samples), "Receipt needs samples")
            require(
                len({x.sample for x in self.samples}) == len(self.samples),
                "A receipt contains duplicate samples",
            )
            for row in self.samples:
                frappe.db.get_value("Lab Sample", row.sample, "name", for_update=True)
                sample = linked("Lab Sample", row.sample)
                require(sample.work_request == self.work_request, "Sample belongs to another job")
                require(
                    get_datetime(sample.sampled_on) <= get_datetime(self.received_on),
                    "Sample collection cannot follow receipt",
                )
                require(not sample.receipt, "Sample is already received")
                sample.check_permission("write")
                nested = _ACTION.set((sample.doctype, sample.name, "Receive"))
                try:
                    sample.receipt, sample.receipt_decision = self.name, row.decision
                    sample.save()
                finally:
                    _ACTION.reset(nested)
            self.received_by = user
        elif dt == "Lab Work Plan":
            require(bool(self.assignments), "A plan needs test assignments")
            keys = set()
            request = linked("Lab Work Request", self.work_request)
            require_authorization(request)
            requested = {x.test_definition for x in request.requested_tests}
            for row in self.assignments:
                sample = self.received_sample(row.sample)
                method = linked("Lab Test Method Version", row.method_version)
                require(
                    method.status == "Approved" and method.test_definition in requested,
                    "Use an approved method for a requested test",
                )
                definition = linked("Lab Test Definition", method.test_definition)
                require(
                    not definition.sample_type or definition.sample_type == sample.sample_type,
                    "Method is unsuitable for this sample type",
                )
                require(not definition.requires_specimen or row.specimen, "This test requires a specimen")
                if row.specimen:
                    require(
                        linked("Lab Specimen", row.specimen).sample == row.sample,
                        "Specimen does not belong to the planned sample",
                    )
                competency(row.technician, method, "test", row.planned_on or at)
                key = (row.sample, row.specimen or "", row.method_version)
                require(key not in keys, "Duplicate planned test")
                keys.add(key)
            self.released_by, self.released_on = user, at
        elif dt == "Lab Chain of Custody":
            plan = linked("Lab Work Plan", self.work_plan)
            require(
                plan.status == "Released" and any(x.sample == self.sample for x in plan.assignments),
                "Custody needs a released sample plan",
            )
            if action == "Reopen":
                require(
                    bool(self._action_reason and self._action_reason.strip()),
                    "Explain why custody is being reopened",
                )
                self.last_reopen_reason = self._action_reason
                self.reopened_by, self.reopened_on = user, at
            elif action == "Activate":
                frappe.db.get_value("Lab Sample", self.sample, "name", for_update=True)
                self.received_sample(self.sample)
                require(
                    not frappe.db.exists(
                        "Lab Chain of Custody",
                        {"sample": self.sample, "status": ["in", ["Active", "Completed"]]},
                    ),
                    "A custody record already exists for this sample",
                )
            else:
                require(
                    self.events and all(x.acknowledged_by for x in self.events),
                    "All custody transfers must be acknowledged",
                )
                private_evidence(self.completion_evidence)
                for row in plan.assignments:
                    if row.sample == self.sample:
                        require(
                            frappe.db.exists(
                                "Lab Test Execution",
                                {
                                    "sample": self.sample,
                                    "work_plan": self.work_plan,
                                    "method_version": row.method_version,
                                    "specimen": row.specimen or "",
                                    "status": ["in", ["Raw Complete", "Processed"]],
                                },
                            ),
                            "Planned testing must be recorded before custody completion",
                        )
                self.completed_by, self.completed_on = user, at
        elif dt == "Lab Test Execution":
            self.test_action(action, user, at)
        elif dt == "Lab QA Review":
            self.review_action(action, user, at)
        elif dt == "Lab Nonconformance":
            if action == "Close":
                actions = frappe.get_list(
                    "Lab Corrective Action",
                    filters={"nonconformance": self.name, "status": "Returned to QA"},
                    pluck="name",
                )
                require(
                    any(
                        frappe.db.exists("Lab QA Review", {"corrective_action": x, "status": "Accepted"})
                        for x in actions
                    ),
                    "Closure requires corrective action and successful repeat QA",
                )
                self.closed_by, self.closed_on = user, at
        elif dt == "Lab Corrective Action":
            ncr = linked("Lab Nonconformance", self.nonconformance)
            require(ncr.status == "Open", "Corrective action requires an open laboratory nonconformance")
            private_evidence(self.evidence)
            if self.replacement_execution:
                replacement = linked("Lab Test Execution", self.replacement_execution)
                require(
                    replacement.supersedes == ncr.execution and replacement.status == "Processed",
                    "Replacement must be the processed revision of the affected execution",
                )
            self.completed_by, self.completed_on = user, at
        elif dt == "Lab Result Report":
            self.approve_report(user, at)
        elif dt == "Lab Result Dispatch":
            report = linked("Lab Result Report", self.report)
            self.validate_live_report(report)
            require(
                self.delivery_outcome == "Delivered", "Record actual delivery evidence before marking issued"
            )
            private_evidence(self.delivery_evidence)
            self.issued_by, self.issued_on = user, at
        elif dt in {"Lab Test Method Version", "Lab QA Checklist Version", "Lab Specification Version"}:
            self.approved_by, self.approved_on = user, at
        elif dt in {"Lab Equipment Check", "Lab Competency"}:
            private_evidence(self.get("certificate") or self.get("evidence"))
            self.verified_by, self.verified_on = user, at
        elif dt == "Lab Conditioning Record":
            require(
                get_datetime(self.ended_on) <= at, "Conditioning must be completed before acknowledgement"
            )
            self.completed_by, self.completed_on = user, at
        elif dt == "Lab Conformity Evaluation":
            self.conformity_action(user, at)

    def received_sample(self, name):
        sample = linked("Lab Sample", name)
        require(sample.work_request == self.work_request, "Sample belongs to another work request")
        require(
            sample.receipt and sample.receipt_decision == "Accepted", "Sample must be received and accepted"
        )
        require(linked("Lab Sample Receipt", sample.receipt).status == "Received", "Receipt is not finalized")
        return sample

    def test_action(self, action, user, at):
        require_authorization(linked("Lab Work Request", self.work_request))
        sample = self.received_sample(self.sample)
        require(
            get_datetime(self.tested_on) >= get_datetime(sample.sampled_on),
            "Testing cannot precede sample collection",
        )
        if self.specimen:
            specimen = linked("Lab Specimen", self.specimen)
            require(
                get_datetime(self.tested_on) >= get_datetime(specimen.prepared_on),
                "Testing cannot precede specimen preparation",
            )
        method = linked("Lab Test Method Version", self.method_version)
        require(method.status == "Approved", "An approved method is required")
        plan = linked("Lab Work Plan", self.work_plan)
        require(plan.status == "Released", "Testing requires a released plan")
        custody = linked("Lab Chain of Custody", self.custody)
        definition = linked("Lab Test Definition", method.test_definition)
        if action == "Complete Raw":
            require(custody.status == "Active", "Testing requires active custody")
            assignment = next(
                (
                    x
                    for x in plan.assignments
                    if x.sample == self.sample
                    and x.method_version == self.method_version
                    and (x.specimen or "") == (self.specimen or "")
                ),
                None,
            )
            require(
                assignment and assignment.technician == user,
                "Only the assigned technician can complete raw testing",
            )
            competency(user, method, "test", self.tested_on)
            require(not definition.requires_specimen or self.specimen, "A specimen is required")
            if definition.requires_conditioning:
                require(
                    frappe.db.exists(
                        "Lab Conditioning Record",
                        {
                            "specimen": self.specimen,
                            "status": "Completed",
                            "ended_on": ["<=", self.tested_on],
                        },
                    ),
                    "Completed conditioning is required before testing",
                )
            if definition.requires_equipment or frappe.get_single("Lab Settings").enforce_equipment_validity:
                require(bool(self.equipment), "Record the testing equipment")
                for row in self.equipment:
                    equipment = linked("Lab Equipment", row.equipment)
                    require(not equipment.disabled, "Disabled equipment cannot be used")
                    require(
                        frappe.db.exists(
                            "Lab Equipment Check",
                            {
                                "equipment": row.equipment,
                                "status": "Verified",
                                "checked_on": ["<=", getdate(self.tested_on)],
                                "valid_until": [">=", getdate(self.tested_on)],
                            },
                        ),
                        "Equipment has no valid verified check at test time",
                    )
            # Validate inputs and calculation feasibility before freezing raw evidence.
            process_results(
                data_rows(method, "inputs", ["code", "mandatory"]),
                data_rows(method, "outputs", ["code", "expression", "precision", "uom"]),
                data_rows(self, "observations", ["code", "value", "recorded"]),
            )
            if self.raw_evidence:
                private_evidence(self.raw_evidence)
            if self.test_schedule:
                schedule = linked("Lab Test Schedule", self.test_schedule)
                require(
                    schedule.method_version == self.method_version and schedule.specimen == self.specimen,
                    "Schedule and execution differ",
                )
                require(
                    get_datetime(schedule.window_start)
                    <= get_datetime(self.tested_on)
                    <= get_datetime(schedule.window_end),
                    "Test is outside the approved schedule window; resolve the deviation before completion",
                )
            self.method_snapshot = frappe.as_json(
                {
                    "name": method.name,
                    "version": method.version,
                    "inputs": data_rows(method, "inputs", ["code", "mandatory", "uom"]),
                    "outputs": data_rows(method, "outputs", ["code", "expression", "precision", "uom"]),
                }
            )
            self.tested_by, self.raw_completed_on = user, at
        else:
            require(custody.status == "Completed", "Completed custody is required before processing")
            competency(user, method, "process", at)
            snapshot = json.loads(self.method_snapshot)
            self.set(
                "results",
                process_results(
                    snapshot["inputs"],
                    snapshot["outputs"],
                    data_rows(self, "observations", ["code", "value", "recorded"]),
                ),
            )
            self.result_digest = digest(
                {
                    "method": snapshot,
                    "observations": data_rows(self, "observations", ["code", "value"]),
                    "results": data_rows(self, "results", ["code", "value", "uom", "precision"]),
                }
            )
            if self.supersedes:
                require(
                    not frappe.db.exists(
                        "Lab Test Execution", {"supersedes": self.supersedes, "status": "Processed"}
                    ),
                    "This result already has a processed replacement",
                )
            self.processed_by, self.processed_on = user, at
            if self.test_schedule:
                schedule = linked("Lab Test Schedule", self.test_schedule)
                require(
                    not schedule.execution or schedule.execution == self.supersedes,
                    "Schedule already has a completed execution",
                )
                nested = _ACTION.set((schedule.doctype, schedule.name, "Fulfil"))
                try:
                    schedule.execution, schedule.status = self.name, "Completed"
                    schedule.save()
                finally:
                    _ACTION.reset(nested)

    def review_action(self, action, user, at):
        checklist = linked("Lab QA Checklist Version", self.checklist_version)
        require(checklist.status == "Approved", "QA needs an approved checklist")
        require(bool(self.results), "QA needs result revisions")
        expected = {x.question for x in checklist.questions}
        responses = {x.question: x for x in self.responses}
        require(
            len(responses) == len(self.responses) and not (responses.keys() - expected),
            "Unexpected or duplicate QA questions",
        )
        require(
            all(x.question in responses for x in checklist.questions if x.mandatory),
            "Mandatory QA questions are unanswered",
        )
        if action == "Accept":
            require(all(x.outcome != "Fail" for x in self.responses), "Failed QA checks prevent acceptance")
        require(len({x.execution for x in self.results}) == len(self.results), "Duplicate result revisions")
        action_doc = (
            linked("Lab Corrective Action", self.corrective_action) if self.corrective_action else None
        )
        if action_doc:
            require(action_doc.status == "Returned to QA", "Corrective action must be returned to QA")
            ncr = linked("Lab Nonconformance", action_doc.nonconformance)
            target = action_doc.replacement_execution or ncr.execution
            require(
                target in {x.execution for x in self.results}, "Repeat QA must include the affected result"
            )
        for row in self.results:
            execution = linked("Lab Test Execution", row.execution)
            require(
                execution.work_request == self.work_request and execution.status == "Processed",
                "Review results must belong to this job and be processed",
            )
            no_self_review({execution.tested_by, execution.processed_by})
            require(
                linked("Lab Chain of Custody", execution.custody).status == "Completed",
                "Complete custody before QA",
            )
            require(
                not frappe.db.exists(
                    "Lab Test Execution", {"supersedes": execution.name, "status": "Processed"}
                ),
                "Review the current result revision",
            )
            competency(user, linked("Lab Test Method Version", execution.method_version), "review", at)
            if action == "Accept":
                lineage = {execution.name}
                parent = execution.supersedes
                while parent:
                    require(parent not in lineage, "Result revision lineage contains a cycle")
                    lineage.add(parent)
                    parent = linked("Lab Test Execution", parent).supersedes
                rejected = frappe.get_list(
                    "Lab QA Review",
                    filters={"work_request": self.work_request, "status": "Correction Required"},
                    pluck="name",
                )
                if any(
                    any(r.execution in lineage for r in linked("Lab QA Review", name).results)
                    for name in rejected
                ):
                    require(action_doc, "A rejected result requires corrective action and repeat QA")
            row.result_digest = execution.result_digest
        if action == "Require Correction":
            require(
                bool(self.remarks),
                "Explain why correction is required and record a laboratory nonconformance",
            )
        self.reviewed_by, self.reviewed_on = user, at

    def checked_report_results(self):
        require(bool(self.results), "A report must contain results")
        require(len({x.execution for x in self.results}) == len(self.results), "Duplicate report results")
        contents = []
        for row in self.results:
            execution = linked("Lab Test Execution", row.execution)
            require(execution.work_request == self.work_request, "Report results belong to another job")
            execution_is_current(execution)
            qa = linked("Lab QA Review", row.qa_review)
            require(
                qa.status == "Accepted"
                and qa.work_request == self.work_request
                and any(
                    x.execution == execution.name and x.result_digest == execution.result_digest
                    for x in qa.results
                ),
                "A matching accepted QA review is required",
            )
            failed_qa = frappe.get_list(
                "Lab QA Review",
                filters={
                    "work_request": self.work_request,
                    "status": "Correction Required",
                    "reviewed_on": [">", qa.reviewed_on],
                },
                pluck="name",
            )
            require(
                not any(
                    any(x.execution == execution.name for x in linked("Lab QA Review", name).results)
                    for name in failed_qa
                ),
                "A later QA rejection holds this result",
            )
            row.result_digest = execution.result_digest
            contents.append(
                {
                    "execution": execution.name,
                    "sample": execution.sample,
                    "specimen": execution.specimen,
                    "method": execution.method_version,
                    "digest": execution.result_digest,
                    "results": data_rows(execution, "results", ["code", "value", "uom", "precision"]),
                }
            )
        return contents

    def approve_report(self, user, at):
        require_authorization(linked("Lab Work Request", self.work_request))
        contents = self.checked_report_results()
        self.check_inspection_coverage()
        for row in self.results:
            execution = linked("Lab Test Execution", row.execution)
            qa = linked("Lab QA Review", row.qa_review)
            no_self_review({execution.tested_by, execution.processed_by, qa.reviewed_by})
            competency(user, linked("Lab Test Method Version", execution.method_version), "approve", at)
        if not frappe.get_single("Lab Settings").allow_partial_reports:
            assignments = []
            for name in frappe.get_list(
                "Lab Work Plan",
                filters={"work_request": self.work_request, "status": "Released"},
                pluck="name",
            ):
                assignments.extend(linked("Lab Work Plan", name).assignments)
            covered = {(x["sample"], x["specimen"] or "", x["method"]) for x in contents}
            require(
                all((x.sample, x.specimen or "", x.method_version) in covered for x in assignments),
                "Current policy requires all released planned tests in the report",
            )
        conformity = None
        if self.conformity_evaluation:
            evaluation = linked("Lab Conformity Evaluation", self.conformity_evaluation)
            require(
                evaluation.status == "Evaluated" and evaluation.work_request == self.work_request,
                "Conformity evaluation is not finalized",
            )
            require(
                {x.execution for x in evaluation.results} == {x.execution for x in self.results},
                "Conformity and report result scope differ",
            )
            require(
                all(
                    next(x for x in self.results if x.execution == r.execution).result_digest
                    == r.result_digest
                    for r in evaluation.results
                ),
                "Conformity uses a different result revision",
            )
            conformity = json.loads(evaluation.evaluation_snapshot)
        self.approved_by, self.approved_on = user, at
        request = linked("Lab Work Request", self.work_request)
        self.snapshot = frappe.as_json(
            {
                "report": self.name,
                "title": self.report_title,
                "work_request": self.work_request,
                "customer": self.customer,
                "project_profile": self.project_profile,
                "program_revision": request.program_revision,
                "request_scope_digest": request_digest(request),
                "approved_by": user,
                "approved_on": str(at),
                "results": contents,
                "conformity": conformity,
                "remarks": self.remarks,
                "supersedes": self.supersedes,
            }
        )
        self.snapshot_digest = digest(json.loads(self.snapshot))
        from frappe.utils.pdf import get_pdf

        html = frappe.render_template(
            "av_lims/templates/approved_report.html", {"report": json.loads(self.snapshot)}
        )
        file = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": self.name + ".pdf",
                "is_private": 1,
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
                "content": get_pdf(html),
            }
        ).insert(ignore_permissions=True)
        self.approved_file = file.file_url

    def validate_live_report(self, report):
        require(report.status == "Approved" and report.approved_file, "A frozen approved report is required")
        require(
            not frappe.db.exists("Lab Result Report", {"supersedes": report.name, "status": "Approved"}),
            "This report has been superseded",
        )
        require(
            digest(json.loads(report.snapshot)) == report.snapshot_digest,
            "Approved snapshot integrity check failed",
        )
        request = linked("Lab Work Request", report.work_request)
        require_authorization(request)
        require(
            json.loads(report.snapshot)["request_scope_digest"] == request_digest(request),
            "Work scope changed after report approval",
        )
        # Re-evaluate eligibility without mutating the approved report.
        report.checked_report_results()
        report.check_inspection_coverage()
        private_evidence(report.approved_file)

    def check_inspection_coverage(self):
        from av_lims.inspection import coverage_for_results

        plans = frappe.get_list(
            "Lab Inspection Test Plan",
            filters={"work_request": self.work_request, "status": "Released"},
            pluck="name",
        )
        for plan_name in plans:
            plan = linked("Lab Inspection Test Plan", plan_name)
            coverage = coverage_for_results(plan, [x.execution for x in self.results])
            for row in coverage:
                if row["actual_count"] and row["hold_point"]:
                    require(row["hold_released"], "An inspection hold point prevents report release")
                if not frappe.get_single("Lab Settings").allow_partial_reports:
                    require(
                        row["remaining_count"] == 0, "Required inspection-plan testing remains incomplete"
                    )

    def conformity_action(self, user, at):
        spec = linked("Lab Specification Version", self.specification)
        require(
            spec.status == "Approved" and spec.decision_rule == "Simple Acceptance",
            "An approved supported specification is required",
        )
        require(bool(self.results), "Select processed results")
        require(
            len({x.execution for x in self.results}) == len(self.results),
            "Duplicate conformity result revisions",
        )
        evaluations = []
        for row in self.results:
            execution = linked("Lab Test Execution", row.execution)
            execution_is_current(execution)
            require(execution.work_request == self.work_request, "Conformity results belong to another job")
            method = linked("Lab Test Method Version", execution.method_version)
            require(method.test_definition == spec.test_definition, "Specification is for another test")
            sample = linked("Lab Sample", execution.sample)
            require(sample.specification == spec.name, "Sample must reference the evaluated specification")
            row.result_digest = execution.result_digest
            result = evaluate_conformity(
                data_rows(execution, "results", ["code", "value"]),
                data_rows(spec, "limits", ["code", "has_lower", "lower_limit", "has_upper", "upper_limit"]),
            )
            evaluations.append({"execution": execution.name, "results": result})
        self.outcome = (
            "Fail" if any(r["outcome"] == "Fail" for e in evaluations for r in e["results"]) else "Pass"
        )
        self.evaluation_snapshot = frappe.as_json(
            {
                "specification": spec.name,
                "version": spec.version,
                "decision_rule": spec.decision_rule,
                "outcome": self.outcome,
                "evaluations": evaluations,
            }
        )
        self.evaluated_by, self.evaluated_on = user, at

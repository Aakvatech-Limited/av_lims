"""Exercise production guard code with an explicit in-memory Frappe boundary.

These do not replace the separate database-backed site tests.
"""

import importlib.util
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch


class RuleFailure(Exception):
    pass


def throw(message):
    raise RuleFailure(message)


frappe_stub = types.ModuleType("frappe")
frappe_stub.whitelist = lambda: lambda fn: fn
frappe_stub.throw = throw
frappe_stub.session = types.SimpleNamespace(user="operator@example.test")
frappe_stub.db = Mock()
frappe_stub.get_roles = Mock(return_value=[])
frappe_stub.get_single = Mock()
frappe_stub.get_list = Mock()
frappe_stub.get_all = Mock()
frappe_stub.get_doc = Mock()
frappe_stub.has_permission = Mock()
model = types.ModuleType("frappe.model")
document = types.ModuleType("frappe.model.document")
document.Document = object
utils = types.ModuleType("frappe.utils")
utils.get_datetime = lambda v: v if isinstance(v, datetime) else datetime.fromisoformat(v)
utils.getdate = lambda v: utils.get_datetime(v).date()
utils.now_datetime = lambda: datetime(2026, 11, 10, 12)
with patch.dict(
    sys.modules,
    {"frappe": frappe_stub, "frappe.model": model, "frappe.model.document": document, "frappe.utils": utils},
):
    spec = importlib.util.spec_from_file_location(
        "controller_guard_subject", Path(__file__).resolve().parents[1] / "av_lims/controllers.py"
    )
    subject = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(subject)


class Row(dict):
    def __getattr__(self, key):
        return self.get(key)

    def as_dict(self):
        return dict(self)


class Probe(subject.LabDocument):
    def __init__(self, old=None, **values):
        self.__dict__.update(
            {
                "doctype": "Lab QA Review",
                "name": "TEST-1",
                "docstatus": 0,
                "status": "Draft",
                "_old": old,
                **values,
            }
        )
        fields = [
            Row(fieldname=x, fieldtype="Table" if x == "observations" else "Data")
            for x in values
            if not x.startswith("_")
        ]
        self.meta = types.SimpleNamespace(fields=fields, has_field=lambda name: name in values)

    def get(self, key):
        return self.__dict__.get(key)

    def is_new(self):
        return self._old is None

    def get_doc_before_save(self):
        return self._old

    def validate_context(self):
        pass

    def validate_specific(self):
        pass

    def check_permission(self, ptype):
        pass

    def reload(self):
        pass


class TestControllerGuards(unittest.TestCase):
    def setUp(self):
        subject._ACTION.set(None)
        frappe_stub.session.user = "operator@example.test"
        frappe_stub.get_roles.return_value = []
        frappe_stub.get_single.return_value = types.SimpleNamespace(
            policies_confirmed=True, allow_self_review=False
        )
        frappe_stub.db.exists.return_value = False

    def test_direct_state_change_is_rejected(self):
        old = Probe(status="Draft")
        with self.assertRaisesRegex(RuleFailure, "authorized laboratory action"):
            Probe(old, status="Accepted")._validate()

    def test_client_cannot_supply_approval_identity(self):
        with self.assertRaisesRegex(RuleFailure, "maintained by laboratory actions"):
            Probe(approved_by="forged")._validate()

    def test_final_document_content_is_immutable(self):
        old = Probe(status="Accepted", remarks="original")
        with self.assertRaisesRegex(RuleFailure, "immutable"):
            Probe(old, status="Accepted", remarks="changed")._validate()

    def test_authorized_transition_can_set_server_fields_only(self):
        old = Probe(status="Open", remarks="fixed", closed_by=None)
        subject._ACTION.set(("Lab QA Review", "TEST-1", "Close"))
        Probe(old, status="Closed", remarks="fixed", closed_by="reviewer")._validate()
        with self.assertRaisesRegex(RuleFailure, "immutable"):
            Probe(old, status="Closed", remarks="rewritten", closed_by="reviewer")._validate()

    def test_completed_raw_observations_cannot_be_edited(self):
        old = Probe(status="Raw Complete", observations=[Row(code="x", value=1, recorded=1)])
        with self.assertRaisesRegex(RuleFailure, "raw evidence"):
            Probe(old, status="Raw Complete", observations=[Row(code="x", value=2, recorded=1)])._validate()

    def test_forged_custody_acknowledgement_on_creation_is_rejected(self):
        with self.assertRaisesRegex(RuleFailure, "acknowledgements"):
            Probe(
                doctype="Lab Chain of Custody", events=[Row(acknowledged_by="other", acknowledged_on="now")]
            )._validate()

    def test_system_manager_is_not_implicitly_an_approver(self):
        frappe_stub.get_roles.return_value = ["System Manager"]
        self.assertFalse(subject.has_action_role("approver"))
        frappe_stub.get_roles.return_value = ["LIMS Approver"]
        self.assertTrue(subject.has_action_role("approver"))

    def test_self_review_remains_blocked_for_multi_role_users(self):
        frappe_stub.get_roles.return_value = ["LIMS Technician", "LIMS Manager", "LIMS Approver"]
        with self.assertRaisesRegex(RuleFailure, "own work"):
            subject.no_self_review({"operator@example.test"})

    def test_external_evidence_url_is_rejected(self):
        frappe_stub.get_all.return_value = []
        with self.assertRaisesRegex(RuleFailure, "private File"):
            subject.private_evidence("https://example.test/unsigned.pdf")

    def test_replacement_does_not_escape_open_predecessor_nonconformance(self):
        execution = Row(name="NEW", supersedes="OLD", status="Processed", work_request="JOB", custody="COC")
        frappe_stub.get_list.return_value = [Row(name="NCR", execution="OLD")]
        with patch.object(
            subject,
            "linked",
            side_effect=lambda dt, name: Row(status="Completed")
            if dt == "Lab Chain of Custody"
            else Row(supersedes=None),
        ):
            with self.assertRaisesRegex(RuleFailure, "nonconformance"):
                subject.execution_is_current(execution)

    def test_reopened_custody_blocks_release(self):
        with patch.object(subject, "linked", return_value=Row(status="Active")):
            with self.assertRaisesRegex(RuleFailure, "Reopened custody"):
                subject.execution_is_current(Row(status="Processed", custody="COC"))

    def test_action_authority_is_reset_after_failed_save(self):
        frappe_stub.get_roles.return_value = ["LIMS Manager"]
        doc = Probe(Probe(status="Draft"), status="Draft")
        doc.apply_action = Mock()
        doc.save = Mock(side_effect=RuleFailure("database failure"))
        with self.assertRaisesRegex(RuleFailure, "database failure"):
            doc.run_action("Accept")
        self.assertIsNone(subject._ACTION.get())


if __name__ == "__main__":
    unittest.main()

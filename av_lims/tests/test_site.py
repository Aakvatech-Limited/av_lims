"""Run on an installed development site; these are not standalone unit tests."""

import frappe
from frappe.tests import IntegrationTestCase


class TestLaboratorySite(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.test = frappe.get_doc(
            {"doctype": "Lab Test Definition", "title": "Integration calculation"}
        ).insert()
        self.method = frappe.get_doc(
            {
                "doctype": "Lab Test Method Version",
                "test_definition": self.test.name,
                "version": frappe.generate_hash(length=10),
                "inputs": [{"code": "x", "mandatory": 1}],
                "outputs": [{"code": "out", "expression": "x * 2", "precision": 2}],
            }
        ).insert()

    def test_approved_method_is_immutable(self):
        self.method.run_action("Approve")
        self.method.reload()
        self.assertEqual(self.method.status, "Approved")
        self.assertEqual(self.method.approved_by, "Administrator")
        self.method.outputs[0].expression = "x * 3"
        with self.assertRaises(frappe.ValidationError):
            self.method.save()

    def test_status_cannot_be_forged(self):
        self.method.status = "Approved"
        with self.assertRaises(frappe.ValidationError):
            self.method.save()

    def test_server_owned_approval_fields_cannot_be_forged(self):
        self.method.approved_by = "Administrator"
        with self.assertRaises(frappe.ValidationError):
            self.method.save()

    def test_installed_navigation_and_records(self):
        self.assertTrue(frappe.db.exists("Workspace", "AV LIMS"))
        self.assertTrue(frappe.db.exists("Sidebar", "AV LIMS"))
        self.assertTrue(frappe.db.exists("Dock", {"app": "av_lims", "standard": 1}))
        self.assertTrue(frappe.db.exists("Report", "Lab Test Due Register"))

    def test_distinct_method_version_is_database_enforced(self):
        duplicate = frappe.copy_doc(self.method)
        with self.assertRaises((frappe.DuplicateEntryError, frappe.UniqueValidationError)):
            duplicate.insert()

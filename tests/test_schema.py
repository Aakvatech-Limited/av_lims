import ast
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STANDARD = {
    "Customer",
    "Contact",
    "Company",
    "Project",
    "User",
    "Quotation",
    "Supplier",
    "Item",
    "Asset",
    "UOM",
}


class TestSchemaContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = {}
        for path in (ROOT / "av_lims" / "av_lims" / "doctype").glob("*/*.json"):
            data = json.loads(path.read_text())
            cls.schemas[data["name"]] = (path, data)

    def test_links_resolve_and_controllers_exist(self):
        for name, (path, meta) in self.schemas.items():
            self.assertTrue(path.with_suffix(".py").exists(), name)
            ast.parse(path.with_suffix(".py").read_text())
            names = [f["fieldname"] for f in meta["fields"]]
            self.assertEqual(len(names), len(set(names)), name)
            self.assertEqual(names, meta["field_order"], name)
            for f in meta["fields"]:
                if f["fieldtype"] in ("Link", "Table"):
                    self.assertIn(f["options"], set(self.schemas) | STANDARD, (name, f))
                if f["fieldtype"] == "Table":
                    self.assertEqual(self.schemas[f["options"]][1]["istable"], 1)

    def test_navigation_has_all_user_records_and_no_children(self):
        sidebar = json.loads((ROOT / "av_lims/av_lims/sidebar/av_lims/av_lims.json").read_text())
        targets = {x["link_to"] for x in sidebar["items"] if x.get("link_type") == "DocType"}
        expected = {n for n, (_, s) in self.schemas.items() if not s["istable"]}
        self.assertEqual(targets, expected)
        for row in sidebar["items"]:
            if row.get("link_type") == "Report":
                slug = row["link_to"].lower().replace(" ", "_")
                self.assertTrue((ROOT / "av_lims/av_lims/report" / slug / (slug + ".json")).exists())

    def test_package_imports_without_frappe_and_has_dependencies(self):
        import tomllib

        import av_lims

        self.assertEqual(av_lims.__version__, "16.0.0")
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertIn("erpnext", project["tool"]["bench"]["frappe-dependencies"])
        self.assertIn("frappe", project["tool"]["bench"]["frappe-dependencies"])

    def test_generator_is_reproducible(self):
        before = {str(p.relative_to(ROOT)): p.read_bytes() for p in (ROOT / "av_lims").rglob("*.json")}
        spec = importlib.util.spec_from_file_location("schema_generator", ROOT / "tools/generate_schema.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.generate()
        after = {str(p.relative_to(ROOT)): p.read_bytes() for p in (ROOT / "av_lims").rglob("*.json")}
        self.assertEqual(before, after)

    def test_no_raw_sql_or_eval(self):
        for path in (ROOT / "av_lims").rglob("*.py"):
            text = path.read_text()
            self.assertNotIn("frappe.db.sql", text, str(path))
            self.assertNotIn("eval(", text, str(path))


if __name__ == "__main__":
    unittest.main()

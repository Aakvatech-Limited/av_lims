import json
from pathlib import Path

app_name = "av_lims"
app_title = "AV LIMS"
app_publisher = "Aakvatech Limited"
app_description = "Laboratory and construction materials testing management"
app_email = "info@aakvatech.com"
app_license = "MIT"
app_logo_url = "/assets/av_lims/images/logo.svg"
app_home = "/desk/av-lims"
required_apps = ["erpnext"]

add_to_apps_screen = [
    {
        "name": app_name,
        "logo": app_logo_url,
        "title": app_title,
        "route": app_home,
        "has_permission": "av_lims.api.can_access",
    }
]

before_install = "av_lims.setup.before_install"
after_install = "av_lims.setup.after_install"
after_migrate = "av_lims.setup.after_migrate"

_manifest = json.loads((Path(__file__).parent / "schema_manifest.json").read_text())
doctype_js = {name: "public/js/lab_form.js" for name, spec in _manifest.items() if not spec["child"]}

doc_events = {
    "File": {
        "validate": "av_lims.setup.protect_approved_file",
        "on_trash": "av_lims.setup.protect_approved_file",
    }
}

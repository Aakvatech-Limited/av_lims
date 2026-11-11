from av_lims.reports import register


def execute(filters=None):
    return register(
        "Lab Work Request",
        [
            ("customer", "Customer", "Link", "Customer"),
            ("division", "Division", "Link", "Lab Division"),
            ("project_profile", "Project", "Link", "Lab Project Profile"),
            ("program_revision", "Program Revision", "Data", None),
            ("status", "Status", "Data", None),
        ],
        filters,
    )

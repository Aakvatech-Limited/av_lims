from av_lims.reports import register


def execute(filters=None):
    return register(
        "Lab Nonconformance",
        [
            ("work_request", "Work Request", "Link", "Lab Work Request"),
            ("sample", "Sample", "Link", "Lab Sample"),
            ("execution", "Execution", "Link", "Lab Test Execution"),
            ("origin", "Origin", "Data", None),
            ("issue", "Issue", "Data", None),
            ("status", "Status", "Data", None),
        ],
        filters,
    )

frappe.query_reports["Lab Test Due Register"] = {
    filters: [
        {fieldname: "division", label: __("Division"), fieldtype: "Link", options: "Lab Division"},
        {fieldname: "work_request", label: __("Work Request"), fieldtype: "Link", options: "Lab Work Request"}
    ]
};

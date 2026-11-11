frappe.query_reports["Lab Work Register"] = {
    filters: [
        {fieldname: "division", label: __("Division"), fieldtype: "Link", options: "Lab Division"},
        {fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer"},
        {fieldname: "work_request", label: __("Work Request"), fieldtype: "Link", options: "Lab Work Request"}
    ]
};

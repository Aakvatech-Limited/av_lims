(() => {
    // One shared file is loaded for multiple DocTypes in a desk session.
    const dt = typeof cur_frm !== "undefined" && cur_frm.doctype;
    frappe.av_lims_registered = frappe.av_lims_registered || {};
    if (!dt || frappe.av_lims_registered[dt]) return;
    frappe.av_lims_registered[dt] = true;
    frappe.ui.form.on(dt, {
        refresh(frm) {
            if (frm.is_new()) return;
            frappe.call({
                method: "av_lims.api.available_actions",
                args: {doctype: frm.doctype, name: frm.doc.name},
                callback(r) {
                    (r.message || []).forEach(action => {
                        frm.add_custom_button(__(action), () => {
                            const execute = () => {
                                if (action === "Reopen") {
                                    frappe.prompt([{fieldname: "reason", label: __("Reason"), fieldtype: "Small Text", reqd: 1}],
                                        values => frm.call("run_action", {action, reason: values.reason}).then(() => frm.reload_doc()), __("Reopen Custody"));
                                } else {
                                    return frm.call("run_action", {action}).then(() => frm.reload_doc());
                                }
                            };
                            if (frm.is_dirty()) frm.save().then(execute);
                            else execute();
                        }, __("Actions"));
                    });
                }
            });
            if (frm.doctype === "Lab Chain of Custody" && frm.doc.status === "Active") {
                frm.add_custom_button(__("Acknowledge Transfer"), () => {
                    const pending = (frm.doc.events || []).filter(row =>
                        row.to_user === frappe.session.user && !row.acknowledged_by);
                    if (!pending.length) {
                        frappe.msgprint(__("No transfers await your acknowledgement."));
                        return;
                    }
                    frappe.prompt([{fieldname: "event_name", label: __("Transfer"),
                        fieldtype: "Select", options: pending.map(x => ({value: x.name,
                            label: `${x.event_time} - ${x.location}`})), reqd: 1}],
                    values => frm.call("acknowledge", values).then(() => frm.reload_doc()),
                    __("Acknowledge Transfer"));
                });
            }
            if (frm.doctype === "Lab Result Report" && frm.doc.approved_file) {
                frm.add_custom_button(__("Approved Report"), () =>
                    window.open(frm.doc.approved_file, "_blank", "noopener"));
            }
            if (frm.doctype === "Lab Test Execution" && frm.doc.status === "Draft") {
                frm.add_custom_button(__("Load Method Inputs"), async () => {
                    if (!frm.doc.method_version) return frappe.msgprint(__("Select a method first."));
                    const load = async () => {
                        const method = await frappe.db.get_doc("Lab Test Method Version", frm.doc.method_version);
                        frm.clear_table("observations");
                        (method.inputs || []).forEach(row => frm.add_child("observations", {code: row.code, recorded: 0}));
                        frm.refresh_field("observations");
                        frm.dirty();
                    };
                    if ((frm.doc.observations || []).length) frappe.confirm(__("Replace existing draft observations?"), load);
                    else load();
                });
            }
            if (frm.doctype === "Lab QA Review" && frm.doc.status === "Draft") {
                frm.add_custom_button(__("Load Checklist"), async () => {
                    if (!frm.doc.checklist_version) return frappe.msgprint(__("Select a checklist first."));
                    const load = async () => {
                        const checklist = await frappe.db.get_doc("Lab QA Checklist Version", frm.doc.checklist_version);
                        frm.clear_table("responses");
                        (checklist.questions || []).forEach(row => frm.add_child("responses", {question: row.question}));
                        frm.refresh_field("responses");
                        frm.dirty();
                    };
                    if ((frm.doc.responses || []).length) frappe.confirm(__("Replace draft checklist responses?"), load);
                    else load();
                });
            }
            if (frm.doctype === "Lab Work Request") {
                ["Lab Work Authorization", "Lab Sample", "Lab Sample Receipt", "Lab Work Plan", "Lab Result Report"].forEach(target => {
                    if (frappe.model.can_create(target)) frm.add_custom_button(__(target.replace("Lab ", "")), () =>
                        frappe.new_doc(target, {work_request: frm.doc.name}), __("Create"));
                });
            }
        }
    });
    if (!frappe.av_lims_observation_handler) {
        frappe.av_lims_observation_handler = true;
        frappe.ui.form.on("Lab Observation", {
            value(frm, cdt, cdn) { frappe.model.set_value(cdt, cdn, "recorded", 1); }
        });
    }
})();

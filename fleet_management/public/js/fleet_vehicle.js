// Fleet Vehicle — related-record navigation and status headline

frappe.ui.form.on("Fleet Vehicle", {
    refresh(frm) {
        if (frm.doc.__islocal) return;

        const links = [
            { label: __("Trips"), doctype: "Fleet Trip" },
            { label: __("Job Cards"), doctype: "Fleet Job Card" },
            { label: __("Fuel Logs"), doctype: "Fleet Fuel Log" },
            { label: __("Compliance"), doctype: "Fleet Compliance Document" }
        ];

        links.forEach(function (link) {
            frm.add_custom_button(link.label, function () {
                frappe.set_route("List", link.doctype, { vehicle: frm.doc.name });
            }, __("View"));
        });

        if (frm.doc.status === "In Maintenance") {
            frm.dashboard.set_headline(
                __("This vehicle is currently In Maintenance and is not available for dispatch."),
                "orange"
            );
        } else if (frm.doc.status === "On Rent") {
            frm.dashboard.set_headline(
                __("This vehicle is currently On Rent under an active rental contract."),
                "blue"
            );
        }
    }
});

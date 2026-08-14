// Fleet Rental Contract — amounts, defaults and creation actions

function frc_row_amount(frm, cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row) return;
    const amount = flt(row.rate) * flt(row.qty);
    frappe.model.set_value(cdt, cdn, "amount", amount);
}

function frc_calc_total(frm) {
    let total = 0;
    (frm.doc.items || []).forEach(function (row) {
        total += flt(row.rate) * flt(row.qty);
    });
    frm.set_value("total_amount", total);
    frm.refresh_field("items");
    frm.refresh_field("total_amount");
}

function frc_fetch_vehicle_defaults(frm, cdt, cdn) {
    const row = locals[cdt] && locals[cdt][cdn];
    if (!row || !row.vehicle) return;
    frappe.db
        .get_value("Fleet Vehicle", row.vehicle, ["daily_rate", "monthly_rate", "hourly_rate", "item", "registration_no"])
        .then(function (r) {
            const v = (r && r.message) || {};
            let rate = null;
            if (row.rate_basis === "Daily") rate = v.daily_rate;
            else if (row.rate_basis === "Monthly") rate = v.monthly_rate;
            else if (row.rate_basis === "Hourly") rate = v.hourly_rate;
            if (rate) frappe.model.set_value(cdt, cdn, "rate", flt(rate));
            if (v.item && !row.item_code) frappe.model.set_value(cdt, cdn, "item_code", v.item);
        });
}

function frc_make_sales_invoice(frm) {
    const rows = frm.doc.items || [];
    if (!rows.length) {
        frappe.msgprint(__("There are no contract items to invoice."));
        return;
    }
    const vehicles = [];
    rows.forEach(function (r) {
        if (r.vehicle && vehicles.indexOf(r.vehicle) === -1) vehicles.push(r.vehicle);
    });
    const lookups = vehicles.map(function (v) {
        return frappe.db.get_value("Fleet Vehicle", v, "registration_no");
    });
    Promise.all(lookups).then(function (results) {
        const regs = {};
        vehicles.forEach(function (v, i) {
            const res = results[i];
            regs[v] = (res && res.message && res.message.registration_no) || v;
        });
        frappe.model.with_doctype("Sales Invoice", function () {
            const si = frappe.model.get_new_doc("Sales Invoice");
            si.customer = frm.doc.customer;
            si.company = frm.doc.company;
            si.currency = frm.doc.currency;
            si.cost_center = frm.doc.cost_center;
            si.project = frm.doc.project;
            si.due_date = frm.doc.end_date || frappe.datetime.nowdate();
            si.posting_date = frappe.datetime.nowdate();
            rows.forEach(function (row) {
                const item = frappe.model.add_child(si, "Sales Invoice Item", "items");
                const reg = regs[row.vehicle] || row.vehicle || __("Vehicle");
                const period = (row.start_date || frm.doc.start_date || "") + " - " + (row.end_date || frm.doc.end_date || "");
                const desc = __("Rental") + ": " + reg + " | " + period;
                if (row.item_code) {
                    item.item_code = row.item_code;
                }
                item.item_name = reg;
                item.description = desc;
                item.qty = flt(row.qty) || 1;
                item.rate = flt(row.rate);
                item.cost_center = frm.doc.cost_center;
            });
            frappe.set_route("Form", "Sales Invoice", si.name);
        });
    });
}

function frc_make_invoice_schedule(frm) {
    frappe.model.with_doctype("Fleet Rental Invoice Schedule", function () {
        const sch = frappe.model.get_new_doc("Fleet Rental Invoice Schedule");
        sch.rental_contract = frm.doc.name;
        sch.customer = frm.doc.customer;
        sch.company = frm.doc.company;
        sch.currency = frm.doc.currency;
        sch.period_start = frm.doc.start_date;
        sch.period_end = frm.doc.end_date;
        sch.amount = flt(frm.doc.total_amount);
        sch.status = "Pending";
        frappe.set_route("Form", "Fleet Rental Invoice Schedule", sch.name);
    });
}

frappe.ui.form.on("Fleet Rental Contract", {
    refresh(frm) {
        frc_calc_total(frm);
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Create Sales Invoice"), function () {
                frc_make_sales_invoice(frm);
            }, __("Create"));
            frm.add_custom_button(__("Create Invoice Schedule"), function () {
                frc_make_invoice_schedule(frm);
            }, __("Create"));
        }
    },
    validate(frm) {
        (frm.doc.items || []).forEach(function (row) {
            row.amount = flt(row.rate) * flt(row.qty);
        });
        frc_calc_total(frm);
    },
    items_add(frm) {
        frc_calc_total(frm);
    }
});

frappe.ui.form.on("Fleet Rental Item", {
    rate(frm, cdt, cdn) {
        frc_row_amount(frm, cdt, cdn);
        frc_calc_total(frm);
    },
    qty(frm, cdt, cdn) {
        frc_row_amount(frm, cdt, cdn);
        frc_calc_total(frm);
    },
    amount(frm) {
        frc_calc_total(frm);
    },
    items_remove(frm) {
        frc_calc_total(frm);
    },
    vehicle(frm, cdt, cdn) {
        frc_fetch_vehicle_defaults(frm, cdt, cdn);
    },
    rate_basis(frm, cdt, cdn) {
        frc_fetch_vehicle_defaults(frm, cdt, cdn);
    }
});

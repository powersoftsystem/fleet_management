// Fleet Trip — distance, expenses, margin and invoicing

function ftr_calc(frm) {
    let total_expenses = 0;
    (frm.doc.expenses || []).forEach(function (row) {
        total_expenses += flt(row.amount);
    });
    frm.set_value("total_expenses", total_expenses);

    let distance = flt(frm.doc.end_odometer) - flt(frm.doc.start_odometer);
    if (distance < 0) distance = 0;
    frm.set_value("actual_distance", distance);

    frm.set_value("gross_margin", flt(frm.doc.revenue_amount) - total_expenses);
    frm.set_value("cost_per_distance", distance > 0 ? total_expenses / distance : 0);

    frm.refresh_field("expenses");
}

function ftr_make_sales_invoice(frm) {
    if (!frm.doc.customer) {
        frappe.msgprint(__("Please set a Customer on this trip first."));
        return;
    }
    frappe.db.get_value("Fleet Vehicle", frm.doc.vehicle || "", "registration_no").then(function (r) {
        const reg = (r && r.message && r.message.registration_no) || frm.doc.vehicle || "";
        frappe.model.with_doctype("Sales Invoice", function () {
            const si = frappe.model.get_new_doc("Sales Invoice");
            si.customer = frm.doc.customer;
            si.company = frm.doc.company;
            si.currency = frm.doc.currency;
            si.cost_center = frm.doc.cost_center;
            si.posting_date = frappe.datetime.nowdate();
            const item = frappe.model.add_child(si, "Sales Invoice Item", "items");
            if (frm.doc.item_code) item.item_code = frm.doc.item_code;
            item.description = (frm.doc.origin || "") + " to " + (frm.doc.destination || "") + " | " + reg;
            item.item_name = __("Freight") + " " + (reg || "");
            item.qty = 1;
            item.rate = flt(frm.doc.revenue_amount);
            item.cost_center = frm.doc.cost_center;
            frappe.set_route("Form", "Sales Invoice", si.name);
        });
    });
}

frappe.ui.form.on("Fleet Trip", {
    refresh(frm) {
        if (frm.doc.docstatus === 1 && !frm.doc.sales_invoice) {
            frm.add_custom_button(__("Create Sales Invoice"), function () {
                ftr_make_sales_invoice(frm);
            }, __("Create"));
        }
    },
    validate(frm) {
        ftr_calc(frm);
    },
    start_odometer(frm) {
        ftr_calc(frm);
    },
    end_odometer(frm) {
        ftr_calc(frm);
    },
    revenue_amount(frm) {
        ftr_calc(frm);
    },
    expenses_add(frm) {
        ftr_calc(frm);
    }
});

frappe.ui.form.on("Fleet Trip Expense", {
    amount(frm) {
        ftr_calc(frm);
    },
    expenses_remove(frm) {
        ftr_calc(frm);
    }
});

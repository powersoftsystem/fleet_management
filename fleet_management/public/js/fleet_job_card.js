// Fleet Job Card — parts and total cost rollup

function fjc_calc(frm) {
    let parts_cost = 0;
    (frm.doc.parts || []).forEach(function (row) {
        row.amount = flt(row.rate) * flt(row.qty);
        parts_cost += flt(row.amount);
    });
    frm.set_value("parts_cost", parts_cost);
    frm.set_value("total_cost", parts_cost + flt(frm.doc.labour_cost) + flt(frm.doc.other_cost));
    frm.refresh_field("parts");
    frm.refresh_field("parts_cost");
    frm.refresh_field("total_cost");
}

frappe.ui.form.on("Fleet Job Card", {
    refresh(frm) {
        fjc_calc(frm);
    },
    validate(frm) {
        fjc_calc(frm);
    },
    labour_cost(frm) {
        fjc_calc(frm);
    },
    other_cost(frm) {
        fjc_calc(frm);
    },
    parts_add(frm) {
        fjc_calc(frm);
    }
});

frappe.ui.form.on("Fleet Maintenance Part", {
    rate(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (row) frappe.model.set_value(cdt, cdn, "amount", flt(row.rate) * flt(row.qty));
        fjc_calc(frm);
    },
    qty(frm, cdt, cdn) {
        const row = locals[cdt] && locals[cdt][cdn];
        if (row) frappe.model.set_value(cdt, cdn, "amount", flt(row.rate) * flt(row.qty));
        fjc_calc(frm);
    },
    amount(frm) {
        fjc_calc(frm);
    },
    parts_remove(frm) {
        fjc_calc(frm);
    }
});

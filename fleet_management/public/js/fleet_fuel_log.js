// Fleet Fuel Log — amount, distance and consumption metrics

function ffl_amount(frm) {
    frm.set_value("amount", flt(frm.doc.quantity) * flt(frm.doc.rate));
}

function ffl_metrics(frm) {
    if (!frm.doc.vehicle || !flt(frm.doc.odometer)) return;
    frappe.db.get_value("Fleet Vehicle", frm.doc.vehicle, "current_odometer").then(function (r) {
        const prev = flt(r && r.message && r.message.current_odometer);
        const distance = flt(frm.doc.odometer) - prev;
        if (distance <= 0) return;
        frm.set_value("distance_since_last", distance);
        frm.set_value("consumption", (flt(frm.doc.quantity) / distance) * 100);
        frm.set_value("cost_per_distance", flt(frm.doc.amount) / distance);
    });
}

frappe.ui.form.on("Fleet Fuel Log", {
    quantity(frm) {
        ffl_amount(frm);
        ffl_metrics(frm);
    },
    rate(frm) {
        ffl_amount(frm);
        ffl_metrics(frm);
    },
    odometer(frm) {
        ffl_metrics(frm);
    },
    vehicle(frm) {
        ffl_metrics(frm);
    },
    validate(frm) {
        ffl_amount(frm);
    }
});

# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

"""Scheduled jobs for Fleet Management.

Each unit of work is wrapped individually so that a single bad record cannot
abort the rest of the nightly run or the scheduler itself.
"""

import frappe
from frappe.utils import add_days, cint, date_diff, flt, getdate, today

from fleet_management.api import make_invoice_schedule
from fleet_management.utils import flt_or_zero, refresh_vehicle_compliance, safe_divide

#: Number of days of fuel history used for the rolling average consumption.
CONSUMPTION_WINDOW_DAYS = 180

#: Minimum number of submitted fuel logs before an average is meaningful.
MIN_FUEL_LOGS_FOR_AVERAGE = 2

#: Fallback reminder window when a compliance document has none set.
DEFAULT_REMINDER_DAYS = 30


def _run(step_name: str, fn, *args, **kwargs):
	"""Run a job step, logging and swallowing any failure."""
	try:
		result = fn(*args, **kwargs)
		frappe.db.commit()
		return result
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title=f"Fleet Management: {step_name} failed",
			message=frappe.get_traceback(with_context=True),
		)
		return None


# ---------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------


def daily():
	"""Nightly compliance re-grading and rental invoice scheduling."""
	affected_vehicles: set[str] = set()

	affected_vehicles |= _run("compliance document status", update_compliance_document_status) or set()
	affected_vehicles |= _run("insurance policy status", update_insurance_policy_status) or set()
	_run("vehicle compliance refresh", refresh_vehicles, affected_vehicles)
	_run("rental invoice scheduling", generate_due_invoice_schedules)


def _grade_status(expiry_date, reminder_days, current_status: str | None) -> str | None:
	"""Return the status an expiry-dated document should now carry.

	``Renewed`` and ``Not Applicable`` are terminal states set by a human and are
	never overwritten. Returns ``None`` when no change is needed.
	"""
	if current_status in ("Renewed", "Not Applicable", "Cancelled"):
		return None

	if not expiry_date:
		return None

	days_left = date_diff(getdate(expiry_date), getdate(today()))
	window = cint(reminder_days) or DEFAULT_REMINDER_DAYS

	if days_left < 0:
		new_status = "Expired"
	elif days_left <= window:
		new_status = "Expiring Soon"
	else:
		new_status = "Valid"

	return new_status if new_status != current_status else None


def update_compliance_document_status() -> set:
	"""Re-grade every live Fleet Compliance Document against today's date."""
	documents = frappe.get_all(
		"Fleet Compliance Document",
		filters={"docstatus": ["<", 2]},
		fields=["name", "vehicle", "expiry_date", "reminder_days", "status"],
	)

	touched: set[str] = set()

	for doc in documents:
		new_status = _grade_status(doc.get("expiry_date"), doc.get("reminder_days"), doc.get("status"))
		if not new_status:
			continue

		frappe.db.set_value(
			"Fleet Compliance Document", doc["name"], "status", new_status, update_modified=False
		)

		if doc.get("vehicle"):
			touched.add(doc["vehicle"])

	return touched


def update_insurance_policy_status() -> set:
	"""Re-grade submitted Fleet Insurance Policies against today's date."""
	policies = frappe.get_all(
		"Fleet Insurance Policy",
		filters={"docstatus": 1},
		fields=["name", "expiry_date", "status"],
	)

	touched: set[str] = set()

	for policy in policies:
		new_status = _grade_status(policy.get("expiry_date"), DEFAULT_REMINDER_DAYS, policy.get("status"))
		if not new_status:
			continue

		frappe.db.set_value(
			"Fleet Insurance Policy", policy["name"], "status", new_status, update_modified=False
		)

		covered = frappe.get_all(
			"Fleet Insurance Vehicle",
			filters={"parent": policy["name"], "parenttype": "Fleet Insurance Policy"},
			fields=["vehicle"],
			pluck="vehicle",
		)
		touched |= {vehicle for vehicle in covered if vehicle}

	return touched


def refresh_vehicles(vehicles) -> int:
	"""Recalculate derived compliance fields for the given vehicles."""
	refreshed = 0

	for vehicle in sorted(set(vehicles or [])):
		try:
			if refresh_vehicle_compliance(vehicle) is not None:
				refreshed += 1
		except Exception:
			frappe.log_error(
				title=f"Fleet Management: could not refresh vehicle {vehicle}",
				message=frappe.get_traceback(with_context=True),
			)

	return refreshed


def generate_due_invoice_schedules() -> int:
	"""Raise the next Fleet Rental Invoice Schedule row for active contracts.

	A contract is due for scheduling when it has no future period on file, i.e.
	the latest scheduled ``period_end`` is today or in the past.
	"""
	contracts = frappe.get_all(
		"Fleet Rental Contract",
		filters={"docstatus": 1, "status": "Active"},
		fields=["name", "start_date", "end_date"],
	)

	created = 0

	for contract in contracts:
		if contract.get("end_date") and getdate(contract["end_date"]) < getdate(today()):
			continue

		last_period_end = frappe.db.get_value(
			"Fleet Rental Invoice Schedule",
			{
				"rental_contract": contract["name"],
				"docstatus": ["<", 2],
				"status": ["!=", "Cancelled"],
			},
			"max(period_end)",
		)

		if last_period_end and getdate(last_period_end) > getdate(today()):
			# Current period is already scheduled.
			continue

		if contract.get("start_date") and getdate(contract["start_date"]) > getdate(today()):
			# Contract has not started yet.
			continue

		try:
			if make_invoice_schedule(contract["name"]):
				created += 1
		except Exception:
			frappe.log_error(
				title=f"Fleet Management: invoice scheduling failed for {contract['name']}",
				message=frappe.get_traceback(with_context=True),
			)

	return created


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------


def weekly():
	"""Weekly fuel-efficiency recalculation."""
	_run("average consumption", update_average_consumption)


def update_average_consumption() -> int:
	"""Recalculate ``average_consumption`` on every active Fleet Vehicle.

	Consumption is distance covered per unit of fuel over the last
	``CONSUMPTION_WINDOW_DAYS`` days, taken from submitted fuel logs only.
	"""
	from_date = add_days(getdate(today()), -CONSUMPTION_WINDOW_DAYS)

	vehicles = frappe.get_all(
		"Fleet Vehicle",
		filters={"status": ["not in", ("Sold", "Out of Service")]},
		fields=["name"],
		pluck="name",
	)

	updated = 0

	for vehicle in vehicles:
		try:
			logs = frappe.get_all(
				"Fleet Fuel Log",
				filters={
					"vehicle": vehicle,
					"docstatus": 1,
					"posting_date": [">=", from_date],
				},
				fields=["quantity", "distance_since_last"],
			)

			if len(logs) < MIN_FUEL_LOGS_FOR_AVERAGE:
				continue

			total_distance = sum(flt_or_zero(log.get("distance_since_last")) for log in logs)
			total_quantity = sum(flt_or_zero(log.get("quantity")) for log in logs)

			if total_distance <= 0 or total_quantity <= 0:
				continue

			average = safe_divide(total_distance, total_quantity, 3)
			current = flt_or_zero(frappe.db.get_value("Fleet Vehicle", vehicle, "average_consumption"))

			if flt(average, 3) == flt(current, 3):
				continue

			frappe.db.set_value(
				"Fleet Vehicle", vehicle, "average_consumption", average, update_modified=False
			)
			updated += 1
		except Exception:
			frappe.log_error(
				title=f"Fleet Management: consumption update failed for {vehicle}",
				message=frappe.get_traceback(with_context=True),
			)

	return updated

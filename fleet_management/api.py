# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

"""Whitelisted endpoints used by the Fleet Management client scripts.

Everything here is reachable from the desk, so each entry point checks the
caller's permission on both the source and the target DocType before doing work.
"""

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, add_months, flt, getdate, nowdate

from fleet_management.utils import flt_or_zero, get_vehicle_rate

#: Billing frequency -> (months, days) step used to build a rental period.
BILLING_FREQUENCY_STEP = {
	"daily": (0, 1),
	"weekly": (0, 7),
	"fortnightly": (0, 14),
	"bi-weekly": (0, 14),
	"monthly": (1, 0),
	"quarterly": (3, 0),
	"half-yearly": (6, 0),
	"semi-annually": (6, 0),
	"yearly": (12, 0),
	"annually": (12, 0),
}


def _check_permission(doctype: str, docname: str | None = None, ptype: str = "read"):
	"""Throw unless the current user has ``ptype`` permission."""
	if not frappe.has_permission(doctype, ptype=ptype, doc=docname):
		frappe.throw(
			_("Not permitted to {0} {1}").format(_(ptype), _(doctype)),
			frappe.PermissionError,
		)


def _period_end(start, frequency: str | None):
	"""Return the last day of the billing period starting on ``start``."""
	months, days = BILLING_FREQUENCY_STEP.get(str(frequency or "monthly").strip().lower(), (1, 0))

	start = getdate(start)
	end = add_months(start, months) if months else start
	if days:
		end = add_days(end, days)

	return add_days(end, -1)


def _count_billing_periods(start_date, end_date, frequency: str | None) -> int:
	"""How many whole/partial billing periods a contract spans. Never below 1."""
	if not start_date or not end_date:
		return 1

	start, end = getdate(start_date), getdate(end_date)
	if end < start:
		return 1

	periods, cursor, guard = 0, start, 0
	while cursor <= end and guard < 1000:
		cursor = add_days(_period_end(cursor, frequency), 1)
		periods += 1
		guard += 1

	return max(periods, 1)


@frappe.whitelist()
def make_sales_invoice_from_rental_contract(source_name, target_doc=None):
	"""Map a Fleet Rental Contract onto a draft ERPNext Sales Invoice."""
	_check_permission("Fleet Rental Contract", source_name, "read")
	_check_permission("Sales Invoice", ptype="create")

	def set_missing_values(source, target):
		target.customer = source.customer
		target.company = source.company
		target.currency = source.currency
		target.cost_center = source.cost_center
		target.project = source.project
		target.posting_date = nowdate()
		target.due_date = getdate(source.end_date) if source.end_date else nowdate()
		target.fleet_rental_contract = source.name
		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	def update_item(source_doc, target_doc, source_parent):
		vehicle = source_doc.vehicle or source_doc.vehicle_type or _("Vehicle")
		period_from = source_doc.start_date or source_parent.start_date
		period_to = source_doc.end_date or source_parent.end_date

		description = _("Hire of {0}").format(vehicle)
		if period_from and period_to:
			description = _("Hire of {0} from {1} to {2}").format(
				vehicle,
				frappe.format(getdate(period_from), {"fieldtype": "Date"}),
				frappe.format(getdate(period_to), {"fieldtype": "Date"}),
			)

		target_doc.description = source_doc.description or description
		target_doc.qty = flt_or_zero(source_doc.qty) or 1
		target_doc.rate = flt_or_zero(source_doc.rate)
		target_doc.cost_center = source_parent.cost_center
		target_doc.project = source_parent.project

	doclist = get_mapped_doc(
		"Fleet Rental Contract",
		source_name,
		{
			"Fleet Rental Contract": {
				"doctype": "Sales Invoice",
				"field_map": {
					"name": "fleet_rental_contract",
					"cost_center": "cost_center",
				},
				"validation": {"docstatus": ["=", 1]},
			},
			"Fleet Rental Item": {
				"doctype": "Sales Invoice Item",
				"field_map": {
					"item_code": "item_code",
					"qty": "qty",
					"rate": "rate",
					"amount": "amount",
					"name": "fleet_rental_item",
				},
				"postprocess": update_item,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist


@frappe.whitelist()
def make_sales_invoice_from_trip(source_name, target_doc=None):
	"""Map a Fleet Trip onto a draft ERPNext Sales Invoice with a single line."""
	_check_permission("Fleet Trip", source_name, "read")
	_check_permission("Sales Invoice", ptype="create")

	def set_missing_values(source, target):
		if not source.customer:
			frappe.throw(_("Set a Customer on the trip before invoicing it."))

		target.customer = source.customer
		target.company = source.company
		target.currency = source.currency
		target.cost_center = source.cost_center
		target.project = source.project
		target.posting_date = nowdate()
		target.due_date = nowdate()

		route = _("{0} to {1}").format(source.origin or _("Origin"), source.destination or _("Destination"))
		description = _("Freight for trip {0}: {1}").format(source.name, route)
		if source.registration_no:
			description = _("{0} (Vehicle {1})").format(description, source.registration_no)

		target.append(
			"items",
			{
				"item_code": source.item_code,
				"item_name": source.item_code or _("Freight"),
				"description": description,
				"qty": 1,
				"rate": flt_or_zero(source.revenue_amount),
				"cost_center": source.cost_center,
				"project": source.project,
			},
		)

		target.run_method("set_missing_values")
		target.run_method("calculate_taxes_and_totals")

	doclist = get_mapped_doc(
		"Fleet Trip",
		source_name,
		{
			"Fleet Trip": {
				"doctype": "Sales Invoice",
				"field_map": {"name": "fleet_trip"},
				"validation": {"docstatus": ["=", 1]},
			}
		},
		target_doc,
		set_missing_values,
	)

	return doclist


@frappe.whitelist()
def make_invoice_schedule(rental_contract):
	"""Create the next unbilled Fleet Rental Invoice Schedule row for a contract.

	Returns the new schedule name, or ``None`` when the contract is fully
	scheduled up to its end date.
	"""
	_check_permission("Fleet Rental Contract", rental_contract, "read")
	_check_permission("Fleet Rental Invoice Schedule", ptype="create")

	contract = frappe.db.get_value(
		"Fleet Rental Contract",
		rental_contract,
		[
			"name",
			"customer",
			"company",
			"currency",
			"start_date",
			"end_date",
			"status",
			"billing_frequency",
			"total_amount",
			"docstatus",
		],
		as_dict=True,
	)

	if not contract:
		frappe.throw(_("Fleet Rental Contract {0} not found").format(rental_contract))

	if contract.docstatus != 1:
		frappe.throw(_("Fleet Rental Contract {0} must be submitted first").format(rental_contract))

	if not contract.start_date:
		frappe.throw(_("Fleet Rental Contract {0} has no Start Date").format(rental_contract))

	last_period_end = frappe.db.get_value(
		"Fleet Rental Invoice Schedule",
		{
			"rental_contract": contract.name,
			"docstatus": ["<", 2],
			"status": ["!=", "Cancelled"],
		},
		"max(period_end)",
	)

	period_start = add_days(getdate(last_period_end), 1) if last_period_end else getdate(contract.start_date)

	if contract.end_date and period_start > getdate(contract.end_date):
		return None

	period_end = _period_end(period_start, contract.billing_frequency)
	if contract.end_date and period_end > getdate(contract.end_date):
		period_end = getdate(contract.end_date)

	periods = _count_billing_periods(contract.start_date, contract.end_date, contract.billing_frequency)
	amount = flt(flt_or_zero(contract.total_amount) / periods, 2)

	schedule = frappe.get_doc(
		{
			"doctype": "Fleet Rental Invoice Schedule",
			"rental_contract": contract.name,
			"customer": contract.customer,
			"company": contract.company,
			"currency": contract.currency,
			"period_start": period_start,
			"period_end": period_end,
			"due_date": period_end,
			"amount": amount,
			"status": "Pending",
		}
	)
	schedule.insert(ignore_permissions=False)

	return schedule.name


@frappe.whitelist()
def make_stock_entry_from_job_card(source_name, target_doc=None):
	"""Issue the parts on a Fleet Job Card as a Material Issue Stock Entry."""
	_check_permission("Fleet Job Card", source_name, "read")
	_check_permission("Stock Entry", ptype="create")

	def set_missing_values(source, target):
		target.stock_entry_type = "Material Issue"
		target.purpose = "Material Issue"
		target.company = source.company
		target.posting_date = nowdate()
		target.fleet_job_card = source.name

		if not target.get("items"):
			frappe.throw(_("Fleet Job Card {0} has no parts to issue").format(source.name))

		for item in target.items:
			item.cost_center = item.cost_center or source.cost_center

		target.run_method("set_missing_values")
		target.run_method("calculate_rate_and_amount")

	def update_part(source_doc, target_doc, source_parent):
		if flt_or_zero(source_doc.qty) <= 0:
			target_doc.qty = 0
			return

		target_doc.qty = flt_or_zero(source_doc.qty)
		target_doc.s_warehouse = source_doc.warehouse
		target_doc.uom = source_doc.uom
		target_doc.stock_uom = source_doc.uom
		target_doc.conversion_factor = 1
		target_doc.basic_rate = flt_or_zero(source_doc.rate)

	doclist = get_mapped_doc(
		"Fleet Job Card",
		source_name,
		{
			"Fleet Job Card": {
				"doctype": "Stock Entry",
				"field_map": {"name": "fleet_job_card"},
				"validation": {"docstatus": ["=", 1]},
			},
			"Fleet Maintenance Part": {
				"doctype": "Stock Entry Detail",
				"field_map": {
					"item_code": "item_code",
					"item_name": "item_name",
					"warehouse": "s_warehouse",
				},
				"postprocess": update_part,
				"condition": lambda part: flt_or_zero(part.qty) > 0,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist


@frappe.whitelist()
def get_vehicle_rate_for_basis(vehicle, rate_basis):
	"""Client-side helper: fetch the hire rate for a vehicle and rate basis."""
	_check_permission("Fleet Vehicle", vehicle, "read")

	return get_vehicle_rate(vehicle, rate_basis)


@frappe.whitelist()
def get_vehicle_odometer(vehicle):
	"""Client-side helper: current odometer and the date it was last read."""
	_check_permission("Fleet Vehicle", vehicle, "read")

	values = frappe.db.get_value(
		"Fleet Vehicle",
		vehicle,
		["current_odometer", "odometer_uom", "last_odometer_date"],
		as_dict=True,
	)

	return values or {}

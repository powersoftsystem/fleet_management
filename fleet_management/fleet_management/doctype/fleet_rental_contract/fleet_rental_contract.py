# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from fleet_management.utils import (
	flt_or_zero,
	get_vehicle_rate,
	set_vehicle_status,
	validate_date_range,
)

#: Vehicle statuses a vehicle may be in and still be put out on hire.
RELEASABLE_STATUSES = ("On Rent",)


class FleetRentalContract(Document):
	def validate(self):
		self.validate_period()
		self.validate_items()
		self.calculate_totals()
		self.set_status()

	def validate_period(self):
		validate_date_range(self.start_date, self.end_date, _("Start Date"), _("End Date"))

		if self.start_date and self.end_date and getdate(self.end_date) == getdate(self.start_date):
			frappe.throw(
				_("End Date must be after Start Date."),
				title=_("Invalid Period"),
			)

	def validate_items(self):
		if not self.get("items"):
			frappe.throw(_("Add at least one vehicle to the contract."), title=_("No Vehicles"))

		seen = {}

		for item in self.items:
			if not item.vehicle and not item.vehicle_type:
				frappe.throw(
					_("Row {0}: set either a Vehicle or a Vehicle Type.").format(item.idx),
					title=_("Missing Vehicle"),
				)

			if item.vehicle:
				if item.vehicle in seen:
					frappe.throw(
						_("Row {0}: vehicle {1} is already on row {2}.").format(
							item.idx, item.vehicle, seen[item.vehicle]
						),
						title=_("Duplicate Vehicle"),
					)
				seen[item.vehicle] = item.idx

			if not item.start_date:
				item.start_date = self.start_date
			if not item.end_date:
				item.end_date = self.end_date

			validate_date_range(
				item.start_date,
				item.end_date,
				_("Row {0} Start Date").format(item.idx),
				_("Row {0} End Date").format(item.idx),
			)

			if flt_or_zero(item.qty) <= 0:
				item.qty = 1

			if flt_or_zero(item.rate) <= 0 and item.vehicle:
				item.rate = get_vehicle_rate(item.vehicle, item.rate_basis)

			if flt_or_zero(item.rate) < 0:
				frappe.throw(
					_("Row {0}: Rate cannot be negative.").format(item.idx),
					title=_("Invalid Rate"),
				)

			if (
				item.start_odometer
				and item.end_odometer
				and flt_or_zero(item.end_odometer) < flt_or_zero(item.start_odometer)
			):
				frappe.throw(
					_("Row {0}: End Odometer cannot be less than Start Odometer.").format(item.idx),
					title=_("Invalid Odometer"),
				)

	def calculate_totals(self):
		total = 0.0

		for item in self.items:
			item.amount = flt(flt_or_zero(item.rate) * flt_or_zero(item.qty), 2)
			total += item.amount

		self.total_amount = flt(total, 2)
		self.total_invoiced = flt(flt_or_zero(self.total_invoiced), 2)
		self.outstanding_amount = flt(self.total_amount - self.total_invoiced, 2)

	def set_status(self):
		"""A contract is a Draft until it is submitted; after that the user owns
		the status (Active, On Hold, Expired, Closed) unless it is cancelled."""
		if self.docstatus == 0 and not self.status:
			self.status = "Draft"

	def on_submit(self):
		self.status = "Active"
		self.db_set("status", "Active")
		self.update_vehicle_status("On Rent")

	def on_cancel(self):
		self.ignore_linked_doctypes = ("GL Entry", "Stock Ledger Entry")
		self.status = "Cancelled"
		self.db_set("status", "Cancelled")
		self.release_vehicles()

	def update_vehicle_status(self, status: str):
		"""Put every vehicle on the contract into ``status``."""
		for item in self.items:
			if not item.vehicle:
				continue

			current = frappe.db.get_value("Fleet Vehicle", item.vehicle, "status")
			if current in ("Sold", "Out of Service"):
				frappe.throw(
					_("Row {0}: vehicle {1} is {2} and cannot be hired out.").format(
						item.idx, item.vehicle, _(current)
					),
					title=_("Vehicle Unavailable"),
				)

			set_vehicle_status(item.vehicle, status)

	def release_vehicles(self):
		"""Return hired vehicles to Available when the contract is cancelled."""
		for item in self.items:
			if not item.vehicle:
				continue

			set_vehicle_status(item.vehicle, "Available", only_if_in=RELEASABLE_STATUSES)

	def update_invoiced_amount(self):
		"""Recalculate invoiced and outstanding amounts from the invoice schedule."""
		invoiced = frappe.db.get_value(
			"Fleet Rental Invoice Schedule",
			{
				"rental_contract": self.name,
				"docstatus": ["<", 2],
				"status": ["in", ("Invoiced", "Paid")],
			},
			"sum(amount)",
		)

		self.db_set("total_invoiced", flt(flt_or_zero(invoiced), 2))
		self.db_set("outstanding_amount", flt(flt_or_zero(self.total_amount) - flt_or_zero(invoiced), 2))

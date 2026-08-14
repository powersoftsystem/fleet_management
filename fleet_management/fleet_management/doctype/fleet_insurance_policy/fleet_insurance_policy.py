# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from fleet_management.utils import flt_or_zero, refresh_vehicle_compliance, validate_date_range


class FleetInsurancePolicy(Document):
	def validate(self):
		self.validate_period()
		self.validate_vehicles()
		self.calculate_totals()
		self.set_status()

	def validate_period(self):
		validate_date_range(self.start_date, self.expiry_date, _("Start Date"), _("Expiry Date"))

	def validate_vehicles(self):
		if not self.get("vehicles"):
			frappe.throw(_("Add at least one vehicle to the policy."), title=_("No Vehicles"))

		seen = {}

		for row in self.vehicles:
			if not row.vehicle:
				frappe.throw(
					_("Row {0}: Vehicle is required.").format(row.idx),
					title=_("Missing Vehicle"),
				)

			if row.vehicle in seen:
				frappe.throw(
					_("Row {0}: vehicle {1} is already covered on row {2}.").format(
						row.idx, row.vehicle, seen[row.vehicle]
					),
					title=_("Duplicate Vehicle"),
				)
			seen[row.vehicle] = row.idx

			if not row.registration_no:
				row.registration_no = frappe.db.get_value(
					"Fleet Vehicle", row.vehicle, "registration_no"
				)

			for fieldname, label in (
				("sum_insured", _("Sum Insured")),
				("premium", _("Premium")),
				("excess", _("Excess")),
			):
				if flt_or_zero(row.get(fieldname)) < 0:
					frappe.throw(
						_("Row {0}: {1} cannot be negative.").format(row.idx, label),
						title=_("Invalid Amount"),
					)

	def calculate_totals(self):
		self.total_sum_insured = flt(
			sum(flt_or_zero(row.sum_insured) for row in self.vehicles), 2
		)
		self.total_premium = flt(sum(flt_or_zero(row.premium) for row in self.vehicles), 2)

	def set_status(self):
		if self.docstatus == 2 or self.status in ("Cancelled", "Renewed"):
			return

		if not self.expiry_date:
			return

		if getdate(self.expiry_date) < getdate(today()):
			self.status = "Expired"
		elif self.docstatus == 1:
			self.status = "Active"

	def on_submit(self):
		self.refresh_covered_vehicles()

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		self.refresh_covered_vehicles()

	def refresh_covered_vehicles(self):
		"""Recalculate the insurance expiry held on every covered vehicle."""
		for row in self.vehicles:
			if row.vehicle:
				refresh_vehicle_compliance(row.vehicle)

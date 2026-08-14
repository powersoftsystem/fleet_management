# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from fleet_management.utils import flt_or_zero, safe_divide, update_vehicle_odometer


class FleetFuelLog(Document):
	def validate(self):
		self.set_registration_no()
		self.validate_quantities()
		self.calculate_amount()
		self.calculate_distance()
		self.calculate_efficiency()

	def set_registration_no(self):
		if self.vehicle and not self.registration_no:
			self.registration_no = frappe.db.get_value("Fleet Vehicle", self.vehicle, "registration_no")

	def validate_quantities(self):
		if flt_or_zero(self.quantity) <= 0:
			frappe.throw(_("Quantity must be greater than zero."), title=_("Invalid Quantity"))

		if flt_or_zero(self.rate) < 0:
			frappe.throw(_("Rate cannot be negative."), title=_("Invalid Rate"))

		if flt_or_zero(self.odometer) < 0:
			frappe.throw(_("Odometer cannot be negative."), title=_("Invalid Odometer"))

	def calculate_amount(self):
		self.amount = flt(flt_or_zero(self.quantity) * flt_or_zero(self.rate), 2)

	def calculate_distance(self):
		"""Distance covered since the vehicle's last recorded odometer reading."""
		if not self.vehicle or flt_or_zero(self.odometer) <= 0:
			self.distance_since_last = flt(flt_or_zero(self.distance_since_last), 2)
			return

		previous = flt_or_zero(frappe.db.get_value("Fleet Vehicle", self.vehicle, "current_odometer"))

		if previous <= 0 or flt_or_zero(self.odometer) <= previous:
			# First fill for this vehicle, or a back-dated / corrective entry:
			# do not invent a distance.
			self.distance_since_last = 0
			return

		self.distance_since_last = flt(flt_or_zero(self.odometer) - previous, 2)

	def calculate_efficiency(self):
		"""Consumption (distance per unit of fuel) and cost per unit of distance."""
		distance = flt_or_zero(self.distance_since_last)

		self.consumption = safe_divide(distance, self.quantity, 3)
		self.cost_per_distance = safe_divide(self.amount, distance, 3)

	def on_submit(self):
		if self.vehicle and flt_or_zero(self.odometer) > 0:
			update_vehicle_odometer(self.vehicle, self.odometer, self.posting_date)

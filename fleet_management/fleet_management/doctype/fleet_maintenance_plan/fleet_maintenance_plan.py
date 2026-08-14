# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate

from fleet_management.utils import flt_or_zero, refresh_vehicle_compliance


class FleetMaintenancePlan(Document):
	def validate(self):
		self.set_registration_no()
		self.set_defaults_from_vehicle_type()
		self.validate_intervals()
		self.calculate_next_due()

	def set_registration_no(self):
		if self.vehicle and not self.registration_no:
			self.registration_no = frappe.db.get_value("Fleet Vehicle", self.vehicle, "registration_no")

	def set_defaults_from_vehicle_type(self):
		"""Inherit the service interval from the vehicle's type when not set."""
		if not self.vehicle:
			return

		if cint(self.interval_days) or flt_or_zero(self.interval_distance):
			return

		vehicle_type = frappe.db.get_value("Fleet Vehicle", self.vehicle, "vehicle_type")
		if not vehicle_type:
			return

		defaults = frappe.db.get_value(
			"Fleet Vehicle Type",
			vehicle_type,
			["service_interval_km", "service_interval_days"],
			as_dict=True,
		)
		if not defaults:
			return

		self.interval_distance = flt_or_zero(defaults.get("service_interval_km"))
		self.interval_days = cint(defaults.get("service_interval_days"))

	def validate_intervals(self):
		if flt_or_zero(self.interval_distance) < 0 or cint(self.interval_days) < 0:
			frappe.throw(_("Service intervals cannot be negative."), title=_("Invalid Interval"))

		if flt_or_zero(self.estimated_cost) < 0:
			frappe.throw(_("Estimated Cost cannot be negative."), title=_("Invalid Cost"))

		if not flt_or_zero(self.interval_distance) and not cint(self.interval_days):
			frappe.throw(
				_("Set a distance interval, a day interval, or both."),
				title=_("No Service Interval"),
			)

	def calculate_next_due(self):
		"""Next due date and odometer = last service + the configured interval."""
		interval_days = cint(self.interval_days)
		if interval_days and self.last_service_date:
			self.next_due_date = add_days(getdate(self.last_service_date), interval_days)
		elif not interval_days:
			self.next_due_date = None

		interval_distance = flt_or_zero(self.interval_distance)
		last_odometer = flt_or_zero(self.last_service_odometer)

		if interval_distance and last_odometer:
			self.next_due_odometer = flt(last_odometer + interval_distance, 2)
		elif not interval_distance:
			self.next_due_odometer = None

	def on_update(self):
		if self.vehicle:
			refresh_vehicle_compliance(self.vehicle)

	def is_due(self, as_on_date=None, odometer=None) -> bool:
		"""True when the plan is due by date or by odometer."""
		if not self.is_active:
			return False

		as_on_date = getdate(as_on_date) if as_on_date else getdate()

		if self.next_due_date and getdate(self.next_due_date) <= as_on_date:
			return True

		if self.next_due_odometer and flt_or_zero(odometer) >= flt_or_zero(self.next_due_odometer):
			return bool(flt_or_zero(odometer))

		return False

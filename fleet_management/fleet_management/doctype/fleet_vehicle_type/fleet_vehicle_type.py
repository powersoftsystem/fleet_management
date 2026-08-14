# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from fleet_management.utils import flt_or_zero

RATE_FIELDS = (
	("default_hourly_rate", "Default Hourly Rate"),
	("default_daily_rate", "Default Daily Rate"),
	("default_weekly_rate", "Default Weekly Rate"),
	("default_monthly_rate", "Default Monthly Rate"),
)

CAPACITY_FIELDS = (
	("load_capacity", "Load Capacity"),
	("seating_capacity", "Seating Capacity"),
)

INTERVAL_FIELDS = (
	("service_interval_km", "Service Interval (Distance)"),
	("service_interval_days", "Service Interval (Days)"),
)


class FleetVehicleType(Document):
	def validate(self):
		self.validate_non_negative()
		self.validate_load_uom()
		self.validate_service_interval()

	def validate_non_negative(self):
		for fieldname, label in RATE_FIELDS + CAPACITY_FIELDS + INTERVAL_FIELDS:
			if flt_or_zero(self.get(fieldname)) < 0:
				frappe.throw(
					_("{0} cannot be negative.").format(_(label)),
					title=_("Invalid Value"),
				)

	def validate_load_uom(self):
		if flt_or_zero(self.load_capacity) and not self.load_uom:
			frappe.throw(
				_("Set a Load UOM for a vehicle type that carries a load."),
				title=_("Missing UOM"),
			)

	def validate_service_interval(self):
		if not cint(self.service_interval_days) and not flt_or_zero(self.service_interval_km):
			frappe.msgprint(
				_(
					"No service interval is set for this vehicle type, so maintenance plans "
					"created from it will not schedule themselves."
				),
				title=_("No Service Interval"),
				indicator="orange",
			)

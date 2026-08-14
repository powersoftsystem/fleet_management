# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from fleet_management.utils import flt_or_zero

RATE_FIELDS = ("hourly_rate", "daily_rate", "weekly_rate", "monthly_rate")


class FleetVehicle(Document):
	def validate(self):
		self.normalise_registration_no()
		self.validate_unique_registration_no()
		self.validate_odometer()
		self.validate_rates()
		self.set_defaults_from_type()

	def normalise_registration_no(self):
		"""Registration numbers are stored trimmed and upper-cased."""
		if not self.registration_no:
			frappe.throw(_("Registration No is required."), title=_("Missing Registration"))

		self.registration_no = " ".join(str(self.registration_no).split()).upper()

		if not self.vehicle_name:
			self.vehicle_name = self.registration_no

	def validate_unique_registration_no(self):
		duplicate = frappe.db.exists(
			"Fleet Vehicle",
			{"registration_no": self.registration_no, "name": ["!=", self.name]},
		)

		if duplicate:
			frappe.throw(
				_("Vehicle {0} already uses registration number {1}.").format(
					duplicate, self.registration_no
				),
				title=_("Duplicate Registration"),
			)

	def validate_odometer(self):
		if flt_or_zero(self.current_odometer) < 0:
			frappe.throw(
				_("Current Odometer cannot be negative."),
				title=_("Invalid Odometer"),
			)

		self.current_odometer = flt(flt_or_zero(self.current_odometer), 2)

		if flt_or_zero(self.next_service_odometer) < 0:
			frappe.throw(
				_("Next Service Odometer cannot be negative."),
				title=_("Invalid Odometer"),
			)

	def validate_rates(self):
		for fieldname in RATE_FIELDS:
			if flt_or_zero(self.get(fieldname)) < 0:
				frappe.throw(
					_("{0} cannot be negative.").format(_(frappe.unscrub(fieldname))),
					title=_("Invalid Rate"),
				)

	def set_defaults_from_type(self):
		"""Pull the rate card down from the vehicle type when it is not set."""
		if not self.vehicle_type:
			return

		defaults = frappe.db.get_value(
			"Fleet Vehicle Type",
			self.vehicle_type,
			[f"default_{fieldname}" for fieldname in RATE_FIELDS],
			as_dict=True,
		)
		if not defaults:
			return

		for fieldname in RATE_FIELDS:
			if not flt_or_zero(self.get(fieldname)):
				self.set(fieldname, flt_or_zero(defaults.get(f"default_{fieldname}")))

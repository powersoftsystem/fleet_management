# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

#: Expiry fields checked on save, with their user-facing labels.
EXPIRY_FIELDS = (
	("licence_expiry", "Licence"),
	("medical_cert_expiry", "Medical Certificate"),
	("defensive_driving_expiry", "Defensive Driving Certificate"),
)


class FleetDriver(Document):
	def validate(self):
		self.set_driver_name()
		self.normalise_licence_no()
		self.validate_unique_licence_no()
		self.warn_on_expiries()

	def set_driver_name(self):
		if not self.driver_name and self.employee:
			self.driver_name = frappe.db.get_value("Employee", self.employee, "employee_name")

		if not self.driver_name:
			frappe.throw(_("Driver Name is required."), title=_("Missing Name"))

	def normalise_licence_no(self):
		if self.licence_no:
			self.licence_no = " ".join(str(self.licence_no).split()).upper()

	def validate_unique_licence_no(self):
		if not self.licence_no:
			return

		duplicate = frappe.db.exists(
			"Fleet Driver",
			{"licence_no": self.licence_no, "name": ["!=", self.name]},
		)

		if duplicate:
			frappe.throw(
				_("Driver {0} already uses licence number {1}.").format(duplicate, self.licence_no),
				title=_("Duplicate Licence"),
			)

	def warn_on_expiries(self):
		"""Warn — but do not block — when a driver's paperwork has lapsed."""
		for fieldname, label in EXPIRY_FIELDS:
			expiry = self.get(fieldname)
			if not expiry:
				continue

			if getdate(expiry) < getdate(today()):
				frappe.msgprint(
					_("{0} for {1} expired on {2}. This driver should not be dispatched.").format(
						_(label),
						self.driver_name,
						frappe.format(getdate(expiry), {"fieldtype": "Date"}),
					),
					title=_("Expired Document"),
					indicator="red",
				)

	def is_road_legal(self) -> bool:
		"""True when the driver has a licence that has not expired."""
		if not self.licence_no or not self.licence_expiry:
			return False

		return getdate(self.licence_expiry) >= getdate(today())

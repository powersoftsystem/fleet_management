# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, date_diff, getdate, today

from fleet_management.utils import flt_or_zero, refresh_vehicle_compliance, validate_date_range

#: Statuses a user owns; the automatic grading never overwrites them.
MANUAL_STATUSES = ("Renewed", "Not Applicable")

DEFAULT_REMINDER_DAYS = 30


class FleetComplianceDocument(Document):
	def validate(self):
		self.set_registration_no()
		self.validate_dates()
		self.validate_cost()
		self.set_status()

	def set_registration_no(self):
		if self.vehicle and not self.registration_no:
			self.registration_no = frappe.db.get_value("Fleet Vehicle", self.vehicle, "registration_no")

	def validate_dates(self):
		validate_date_range(self.issue_date, self.expiry_date, _("Issue Date"), _("Expiry Date"))

	def validate_cost(self):
		if flt_or_zero(self.cost) < 0:
			frappe.throw(_("Cost cannot be negative."), title=_("Invalid Cost"))

		if cint(self.reminder_days) < 0:
			frappe.throw(_("Reminder Days cannot be negative."), title=_("Invalid Reminder"))

	def set_status(self):
		"""Grade the document against today's date and its reminder window."""
		if self.status in MANUAL_STATUSES:
			return

		if not self.expiry_date:
			self.status = self.status or "Valid"
			return

		days_left = date_diff(getdate(self.expiry_date), getdate(today()))
		window = cint(self.reminder_days) or DEFAULT_REMINDER_DAYS

		if days_left < 0:
			self.status = "Expired"
		elif days_left <= window:
			self.status = "Expiring Soon"
		else:
			self.status = "Valid"

	def on_update(self):
		if self.vehicle:
			refresh_vehicle_compliance(self.vehicle)

	def after_delete(self):
		if self.vehicle:
			refresh_vehicle_compliance(self.vehicle)

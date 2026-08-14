# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from fleet_management.utils import flt_or_zero

AMOUNT_FIELDS = (
	("estimated_loss", "Estimated Loss"),
	("claim_amount", "Claim Amount"),
	("excess_paid", "Excess Paid"),
	("settled_amount", "Settled Amount"),
)

SETTLED_STATUSES = ("Settled", "Closed")


class FleetInsuranceClaim(Document):
	def validate(self):
		self.validate_amounts()
		self.validate_dates()
		self.validate_policy_cover()

	def validate_amounts(self):
		for fieldname, label in AMOUNT_FIELDS:
			if flt_or_zero(self.get(fieldname)) < 0:
				frappe.throw(
					_("{0} cannot be negative.").format(_(label)),
					title=_("Invalid Amount"),
				)

	def validate_dates(self):
		if self.incident_date and getdate(self.incident_date) > getdate(today()):
			frappe.throw(
				_("Incident Date cannot be in the future."),
				title=_("Invalid Date"),
			)

		if self.settlement_date and self.incident_date:
			if getdate(self.settlement_date) < getdate(self.incident_date):
				frappe.throw(
					_("Settlement Date cannot be earlier than the Incident Date."),
					title=_("Invalid Date"),
				)

		if self.status in SETTLED_STATUSES and not self.settlement_date:
			self.settlement_date = getdate(today())

	def validate_policy_cover(self):
		"""Warn when the incident falls outside the policy period or cover."""
		if not (self.policy and self.incident_date):
			return

		policy = frappe.db.get_value(
			"Fleet Insurance Policy",
			self.policy,
			["start_date", "expiry_date"],
			as_dict=True,
		)
		if not policy:
			return

		incident = getdate(self.incident_date)
		starts = getdate(policy.get("start_date")) if policy.get("start_date") else None
		ends = getdate(policy.get("expiry_date")) if policy.get("expiry_date") else None

		if (starts and incident < starts) or (ends and incident > ends):
			frappe.msgprint(
				_("The incident date falls outside the cover period of policy {0}.").format(self.policy),
				title=_("Outside Cover Period"),
				indicator="orange",
			)

		if self.vehicle and not frappe.db.exists(
			"Fleet Insurance Vehicle",
			{"parent": self.policy, "parenttype": "Fleet Insurance Policy", "vehicle": self.vehicle},
		):
			frappe.msgprint(
				_("Vehicle {0} is not listed on policy {1}.").format(self.vehicle, self.policy),
				title=_("Vehicle Not Covered"),
				indicator="orange",
			)

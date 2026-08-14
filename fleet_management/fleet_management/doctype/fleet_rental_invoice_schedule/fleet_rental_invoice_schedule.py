# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from fleet_management.utils import flt_or_zero, validate_date_range


class FleetRentalInvoiceSchedule(Document):
	def validate(self):
		self.set_missing_values()
		self.validate_period()
		self.validate_amount()
		self.sync_status_with_invoice()

	def set_missing_values(self):
		if not self.rental_contract:
			frappe.throw(_("Rental Contract is required."), title=_("Missing Contract"))

		contract = frappe.db.get_value(
			"Fleet Rental Contract",
			self.rental_contract,
			["customer", "company", "currency"],
			as_dict=True,
		)
		if not contract:
			frappe.throw(
				_("Fleet Rental Contract {0} not found.").format(self.rental_contract),
				title=_("Missing Contract"),
			)

		self.customer = self.customer or contract.get("customer")
		self.company = self.company or contract.get("company")
		self.currency = self.currency or contract.get("currency")

		if not self.due_date and self.period_end:
			self.due_date = getdate(self.period_end)

		if not self.status:
			self.status = "Pending"

	def validate_period(self):
		validate_date_range(self.period_start, self.period_end, _("Period Start"), _("Period End"))

		if self.due_date and self.period_start and getdate(self.due_date) < getdate(self.period_start):
			frappe.throw(
				_("Due Date cannot be earlier than the Period Start."),
				title=_("Invalid Due Date"),
			)

		overlapping = frappe.db.exists(
			"Fleet Rental Invoice Schedule",
			{
				"name": ["!=", self.name],
				"rental_contract": self.rental_contract,
				"status": ["!=", "Cancelled"],
				"period_start": ["<=", getdate(self.period_end)],
				"period_end": [">=", getdate(self.period_start)],
			},
		)

		if overlapping:
			frappe.throw(
				_("Schedule {0} already covers part of this period.").format(overlapping),
				title=_("Overlapping Period"),
			)

	def validate_amount(self):
		if flt_or_zero(self.amount) < 0:
			frappe.throw(_("Amount cannot be negative."), title=_("Invalid Amount"))

	def sync_status_with_invoice(self):
		"""Keep the status honest about whether an invoice actually exists."""
		if self.status == "Cancelled":
			return

		if self.sales_invoice:
			if not frappe.db.exists("Sales Invoice", self.sales_invoice):
				frappe.throw(
					_("Sales Invoice {0} does not exist.").format(self.sales_invoice),
					title=_("Missing Invoice"),
				)

			if self.status == "Pending":
				self.status = "Invoiced"
		elif self.status in ("Invoiced", "Paid"):
			frappe.throw(
				_("Link a Sales Invoice before marking this period as {0}.").format(_(self.status)),
				title=_("Missing Invoice"),
			)

	def on_update(self):
		self.update_contract_totals()

	def update_contract_totals(self):
		if not self.rental_contract:
			return

		contract = frappe.get_doc("Fleet Rental Contract", self.rental_contract)
		if contract.docstatus == 1:
			contract.update_invoiced_amount()

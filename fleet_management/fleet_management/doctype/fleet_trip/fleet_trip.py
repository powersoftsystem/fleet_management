# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime

from fleet_management.utils import (
	flt_or_zero,
	safe_divide,
	set_vehicle_status,
	update_vehicle_odometer,
)

#: Trip statuses that mean the vehicle is currently out on the road.
ON_ROAD_STATUSES = ("Dispatched", "In Transit")

#: Trip statuses that mean the vehicle is back and free for other work.
RELEASED_STATUSES = ("Delivered", "Completed", "Cancelled")


class FleetTrip(Document):
	def validate(self):
		self.set_registration_no()
		self.validate_schedule()
		self.validate_odometer()
		self.calculate_distance()
		self.calculate_expenses()
		self.calculate_revenue()
		self.calculate_margin()

	def set_registration_no(self):
		if self.vehicle and not self.registration_no:
			self.registration_no = frappe.db.get_value("Fleet Vehicle", self.vehicle, "registration_no")

	def validate_schedule(self):
		if self.planned_start and self.planned_end:
			if get_datetime(self.planned_end) < get_datetime(self.planned_start):
				frappe.throw(
					_("Planned End cannot be earlier than Planned Start."),
					title=_("Invalid Schedule"),
				)

		if self.actual_start and self.actual_end:
			if get_datetime(self.actual_end) < get_datetime(self.actual_start):
				frappe.throw(
					_("Actual End cannot be earlier than Actual Start."),
					title=_("Invalid Schedule"),
				)

		if self.driver and self.co_driver and self.driver == self.co_driver:
			frappe.throw(
				_("Driver and Co-Driver cannot be the same person."),
				title=_("Invalid Crew"),
			)

	def validate_odometer(self):
		start = flt_or_zero(self.start_odometer)
		end = flt_or_zero(self.end_odometer)

		if start < 0 or end < 0:
			frappe.throw(_("Odometer readings cannot be negative."), title=_("Invalid Odometer"))

		if end and end < start:
			frappe.throw(
				_("End Odometer ({0}) cannot be less than Start Odometer ({1}).").format(end, start),
				title=_("Invalid Odometer"),
			)

	def calculate_distance(self):
		start = flt_or_zero(self.start_odometer)
		end = flt_or_zero(self.end_odometer)

		if start > 0 and end > start:
			self.actual_distance = flt(end - start, 2)
		elif not flt_or_zero(self.actual_distance):
			self.actual_distance = 0

	def calculate_expenses(self):
		total = 0.0

		for expense in self.get("expenses") or []:
			if flt_or_zero(expense.amount) < 0:
				frappe.throw(
					_("Row {0}: Expense amount cannot be negative.").format(expense.idx),
					title=_("Invalid Expense"),
				)
			total += flt_or_zero(expense.amount)

		self.total_expenses = flt(total, 2)

	def calculate_revenue(self):
		"""Derive revenue from the freight rate when it has not been set by hand."""
		rate = flt_or_zero(self.freight_rate)
		if not rate:
			self.revenue_amount = flt(flt_or_zero(self.revenue_amount), 2)
			return

		basis = str(self.rate_basis or "").strip().lower()

		if basis in ("per km", "per kilometre", "per kilometer", "per distance", "distance"):
			self.revenue_amount = flt(rate * flt_or_zero(self.actual_distance), 2)
		elif basis in ("per tonne", "per ton", "per weight", "weight"):
			self.revenue_amount = flt(rate * flt_or_zero(self.cargo_weight), 2)
		elif not flt_or_zero(self.revenue_amount):
			# Fixed / lump-sum trip rate.
			self.revenue_amount = flt(rate, 2)
		else:
			self.revenue_amount = flt(flt_or_zero(self.revenue_amount), 2)

	def calculate_margin(self):
		self.gross_margin = flt(flt_or_zero(self.revenue_amount) - flt_or_zero(self.total_expenses), 2)
		self.cost_per_distance = safe_divide(self.total_expenses, self.actual_distance, 3)

	def on_submit(self):
		if not self.vehicle:
			return

		if self.status in ON_ROAD_STATUSES:
			set_vehicle_status(self.vehicle, "On Trip", only_if_in=("Available", "On Rent"))
		elif self.status in RELEASED_STATUSES:
			set_vehicle_status(self.vehicle, "Available", only_if_in=("On Trip",))

		reading = flt_or_zero(self.end_odometer) or flt_or_zero(self.start_odometer)
		if reading > 0:
			update_vehicle_odometer(self.vehicle, reading, self.actual_end or self.posting_date)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("GL Entry", "Stock Ledger Entry")
		set_vehicle_status(self.vehicle, "Available", only_if_in=("On Trip",))

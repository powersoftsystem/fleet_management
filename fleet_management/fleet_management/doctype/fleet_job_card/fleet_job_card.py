# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, get_datetime, getdate, time_diff_in_hours, today

from fleet_management.utils import (
	flt_or_zero,
	refresh_vehicle_compliance,
	set_vehicle_status,
	update_vehicle_odometer,
)

#: Statuses that mean the vehicle is back on the road.
CLOSED_STATUSES = ("Completed", "Closed", "Cancelled")


class FleetJobCard(Document):
	def validate(self):
		self.set_registration_no()
		self.validate_odometer()
		self.calculate_parts()
		self.calculate_totals()
		self.calculate_downtime()

	def set_registration_no(self):
		if self.vehicle and not self.registration_no:
			self.registration_no = frappe.db.get_value("Fleet Vehicle", self.vehicle, "registration_no")

	def validate_odometer(self):
		if flt_or_zero(self.odometer) < 0:
			frappe.throw(_("Odometer cannot be negative."), title=_("Invalid Odometer"))

	def calculate_parts(self):
		parts_cost = 0.0

		for part in self.get("parts") or []:
			if flt_or_zero(part.qty) < 0:
				frappe.throw(
					_("Row {0}: Quantity cannot be negative.").format(part.idx),
					title=_("Invalid Quantity"),
				)

			part.amount = flt(flt_or_zero(part.qty) * flt_or_zero(part.rate), 2)
			parts_cost += part.amount

		self.parts_cost = flt(parts_cost, 2)

	def calculate_totals(self):
		self.labour_cost = flt(flt_or_zero(self.labour_cost), 2)
		self.other_cost = flt(flt_or_zero(self.other_cost), 2)
		self.total_cost = flt(
			flt_or_zero(self.parts_cost) + flt_or_zero(self.labour_cost) + flt_or_zero(self.other_cost),
			2,
		)

	def calculate_downtime(self):
		if not (self.start_datetime and self.end_datetime):
			self.downtime_hours = flt(flt_or_zero(self.downtime_hours), 2)
			return

		start = get_datetime(self.start_datetime)
		end = get_datetime(self.end_datetime)

		if end < start:
			frappe.throw(
				_("End Datetime cannot be earlier than Start Datetime."),
				title=_("Invalid Period"),
			)

		self.downtime_hours = flt(time_diff_in_hours(end, start), 2)

	def on_submit(self):
		self.update_vehicle()
		self.update_maintenance_plan()

	def on_cancel(self):
		self.ignore_linked_doctypes = ("GL Entry", "Stock Ledger Entry")
		set_vehicle_status(self.vehicle, "Available", only_if_in=("In Maintenance",))

	def update_vehicle(self):
		"""Take the vehicle off the road while the job is open, and log the odometer."""
		if not self.vehicle:
			return

		if self.status not in CLOSED_STATUSES:
			set_vehicle_status(
				self.vehicle,
				"In Maintenance",
				only_if_in=("Available", "On Rent", "On Trip"),
			)

		if flt_or_zero(self.odometer) > 0:
			update_vehicle_odometer(self.vehicle, self.odometer, self.posting_date)

	def update_maintenance_plan(self):
		"""Roll the linked maintenance plan forward by its service interval."""
		if not self.maintenance_plan:
			return

		plan = frappe.db.get_value(
			"Fleet Maintenance Plan",
			self.maintenance_plan,
			["name", "vehicle", "interval_distance", "interval_days"],
			as_dict=True,
		)
		if not plan:
			return

		service_date = getdate(self.end_datetime or self.posting_date or today())
		service_odometer = flt_or_zero(self.odometer)

		values = {
			"last_service_date": service_date,
			"next_due_date": None,
			"next_due_odometer": None,
		}

		interval_days = cint(plan.get("interval_days"))
		if interval_days > 0:
			values["next_due_date"] = add_days(service_date, interval_days)

		interval_distance = flt_or_zero(plan.get("interval_distance"))
		if service_odometer > 0:
			values["last_service_odometer"] = service_odometer
			if interval_distance > 0:
				values["next_due_odometer"] = flt(service_odometer + interval_distance, 2)

		frappe.db.set_value("Fleet Maintenance Plan", plan["name"], values, update_modified=False)

		if plan.get("vehicle"):
			refresh_vehicle_compliance(plan["vehicle"])

# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

from frappe.model.document import Document


class FleetMaintenanceTask(Document):
	"""A task carried out on a Fleet Job Card or planned on a Fleet Maintenance Plan.

	Totals and validation for this row are handled by the parent controller so
	that the whole document is calculated in one pass.
	"""

	pass

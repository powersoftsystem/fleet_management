# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

from frappe.model.document import Document


class FleetMaintenancePart(Document):
	"""A part consumed on a Fleet Job Card.

	Totals and validation for this row are handled by the parent controller so
	that the whole document is calculated in one pass.
	"""

	pass

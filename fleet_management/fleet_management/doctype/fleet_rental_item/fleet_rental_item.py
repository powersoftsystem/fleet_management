# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

from frappe.model.document import Document


class FleetRentalItem(Document):
	"""A single hired vehicle line on a Fleet Rental Contract.

	Totals and validation for this row are handled by the parent controller so
	that the whole document is calculated in one pass.
	"""

	pass

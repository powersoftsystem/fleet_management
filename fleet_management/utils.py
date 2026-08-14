# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

"""Shared helpers used across the Fleet Management controllers, API and jobs."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

#: Compliance document types that feed a dedicated expiry field on Fleet Vehicle.
#: Matching is done on lower-cased substrings so that site-specific naming such as
#: "Roadworthy Certificate" or "Annual Road Tax" still maps to the right field.
COMPLIANCE_FIELD_KEYWORDS = (
	("insurance_expiry", ("insurance",)),
	("roadworthy_expiry", ("roadworth", "road worth", "fitness")),
	("road_tax_expiry", ("road tax", "licence disc", "license disc")),
	("permit_expiry", ("permit",)),
)

#: Statuses of a Fleet Compliance Document that still count as cover in force.
VALID_COMPLIANCE_STATUSES = ("Valid", "Expiring Soon", "Renewed")

RATE_BASIS_FIELDS = {
	"hourly": "hourly_rate",
	"daily": "daily_rate",
	"weekly": "weekly_rate",
	"monthly": "monthly_rate",
}


def flt_or_zero(value, precision: int | None = None) -> float:
	"""Return ``value`` as a float, treating ``None``/empty/garbage as ``0``.

	``frappe.utils.flt`` already coerces most inputs, but it raises on objects it
	cannot handle. This wrapper is total: it never raises.
	"""
	if value is None or value == "":
		return 0.0

	try:
		return flt(value, precision) if precision is not None else flt(value)
	except (TypeError, ValueError):
		return 0.0


def get_vehicle_rate(vehicle: str, rate_basis: str | None) -> float:
	"""Return the hire rate held on ``vehicle`` for the given ``rate_basis``.

	Falls back to the vehicle type's default rate when the vehicle itself has no
	rate on file. Returns ``0`` when nothing is configured or the vehicle is gone.
	"""
	if not vehicle or not rate_basis:
		return 0.0

	fieldname = RATE_BASIS_FIELDS.get(str(rate_basis).strip().lower())
	if not fieldname:
		return 0.0

	values = frappe.db.get_value("Fleet Vehicle", vehicle, [fieldname, "vehicle_type"], as_dict=True)
	if not values:
		return 0.0

	rate = flt_or_zero(values.get(fieldname))
	if rate:
		return rate

	if values.get("vehicle_type"):
		default_field = f"default_{fieldname}"
		rate = flt_or_zero(
			frappe.db.get_value("Fleet Vehicle Type", values.get("vehicle_type"), default_field)
		)

	return rate


def update_vehicle_odometer(vehicle: str, odometer, date=None) -> bool:
	"""Move a vehicle's odometer forward.

	The odometer is monotonic: a lower reading (a typo, or a back-dated document
	entered after a later one) is ignored rather than rewinding the vehicle.

	Returns ``True`` when the vehicle was updated.
	"""
	if not vehicle:
		return False

	reading = flt_or_zero(odometer)
	if reading <= 0:
		return False

	current = frappe.db.get_value(
		"Fleet Vehicle", vehicle, ["current_odometer", "last_odometer_date"], as_dict=True
	)
	if not current:
		return False

	if reading <= flt_or_zero(current.get("current_odometer")):
		return False

	frappe.db.set_value(
		"Fleet Vehicle",
		vehicle,
		{
			"current_odometer": reading,
			"last_odometer_date": getdate(date) if date else getdate(today()),
		},
		update_modified=False,
	)

	return True


def _compliance_field_for(document_type: str | None) -> str | None:
	"""Map a compliance document type onto a Fleet Vehicle expiry field."""
	if not document_type:
		return None

	needle = str(document_type).strip().lower()
	for fieldname, keywords in COMPLIANCE_FIELD_KEYWORDS:
		if any(keyword in needle for keyword in keywords):
			return fieldname

	return None


def _latest_compliance_expiries(vehicle: str) -> dict:
	"""Latest expiry date per vehicle field from valid Fleet Compliance Documents."""
	expiries: dict[str, object] = {}

	documents = frappe.get_all(
		"Fleet Compliance Document",
		filters={
			"vehicle": vehicle,
			"status": ["in", VALID_COMPLIANCE_STATUSES],
			"docstatus": ["<", 2],
		},
		fields=["document_type", "expiry_date"],
	)

	for row in documents:
		if not row.get("expiry_date"):
			continue

		fieldname = _compliance_field_for(row.get("document_type"))
		if not fieldname:
			continue

		expiry = getdate(row.get("expiry_date"))
		if not expiries.get(fieldname) or expiry > expiries[fieldname]:
			expiries[fieldname] = expiry

	return expiries


def _latest_policy_expiry(vehicle: str):
	"""Latest expiry date across submitted insurance policies covering ``vehicle``."""
	covers = frappe.get_all(
		"Fleet Insurance Vehicle",
		filters={"vehicle": vehicle, "parenttype": "Fleet Insurance Policy"},
		fields=["parent"],
		pluck="parent",
	)
	if not covers:
		return None

	policies = frappe.get_all(
		"Fleet Insurance Policy",
		filters={
			"name": ["in", list(set(covers))],
			"docstatus": 1,
			"status": ["not in", ("Cancelled", "Lapsed")],
		},
		fields=["expiry_date"],
	)

	dates = [getdate(p.get("expiry_date")) for p in policies if p.get("expiry_date")]

	return max(dates) if dates else None


def _next_service_due(vehicle: str) -> dict:
	"""Earliest next due date and odometer across the vehicle's active plans."""
	plans = frappe.get_all(
		"Fleet Maintenance Plan",
		filters={"vehicle": vehicle, "is_active": 1, "docstatus": ["<", 2]},
		fields=["next_due_date", "next_due_odometer"],
	)

	dates = [getdate(p.get("next_due_date")) for p in plans if p.get("next_due_date")]
	odometers = [flt_or_zero(p.get("next_due_odometer")) for p in plans]
	odometers = [o for o in odometers if o > 0]

	return {
		"next_service_date": min(dates) if dates else None,
		"next_service_odometer": min(odometers) if odometers else None,
	}


def refresh_vehicle_compliance(vehicle: str) -> dict | None:
	"""Recalculate the derived compliance and service fields on a Fleet Vehicle.

	Pulls the latest expiry per document type from Fleet Compliance Document and
	Fleet Insurance Policy, and the earliest outstanding service from the active
	Fleet Maintenance Plans, then writes them back onto the vehicle.

	Returns the values written, or ``None`` when the vehicle does not exist.
	"""
	if not vehicle or not frappe.db.exists("Fleet Vehicle", vehicle):
		return None

	values = {
		"insurance_expiry": None,
		"roadworthy_expiry": None,
		"road_tax_expiry": None,
		"permit_expiry": None,
	}
	values.update(_latest_compliance_expiries(vehicle))

	policy_expiry = _latest_policy_expiry(vehicle)
	if policy_expiry and (
		not values.get("insurance_expiry") or policy_expiry > getdate(values["insurance_expiry"])
	):
		values["insurance_expiry"] = policy_expiry

	values.update(_next_service_due(vehicle))

	frappe.db.set_value("Fleet Vehicle", vehicle, values, update_modified=False)

	return values


def set_vehicle_status(vehicle: str, status: str, only_if_in=None) -> bool:
	"""Set a vehicle's status, optionally only when it is in one of ``only_if_in``."""
	if not vehicle or not status:
		return False

	current = frappe.db.get_value("Fleet Vehicle", vehicle, "status")
	if current is None:
		return False

	if only_if_in and current not in only_if_in:
		return False

	if current == status:
		return False

	frappe.db.set_value("Fleet Vehicle", vehicle, "status", status, update_modified=False)

	return True


def validate_date_range(start_date, end_date, start_label=None, end_label=None):
	"""Throw a user-facing error when ``end_date`` is not after ``start_date``."""
	if not start_date or not end_date:
		return

	if getdate(end_date) < getdate(start_date):
		frappe.throw(
			_("{0} ({1}) cannot be earlier than {2} ({3})").format(
				end_label or _("End Date"),
				frappe.format(getdate(end_date), {"fieldtype": "Date"}),
				start_label or _("Start Date"),
				frappe.format(getdate(start_date), {"fieldtype": "Date"}),
			),
			title=_("Invalid Period"),
		)


def safe_divide(numerator, denominator, precision: int = 4) -> float:
	"""Divide with a zero guard, returning ``0`` when the denominator is empty."""
	denominator = flt_or_zero(denominator)
	if not denominator:
		return 0.0

	return flt(flt_or_zero(numerator) / denominator, precision)


def has_app_permission() -> bool:
	"""Control who sees the Fleet Management icon on the /apps screen."""
	roles = set(frappe.get_roles())
	allowed = {"System Manager", "Fleet Manager", "Fleet Supervisor", "Fleet Driver"}
	return bool(roles & allowed)

# Copyright (c) Powersoft Systems and contributors
# For license information, please see LICENSE

import frappe

FLEET_ROLES = (
	{
		"role_name": "Fleet Manager",
		"desk_access": 1,
	},
	{
		"role_name": "Fleet Supervisor",
		"desk_access": 1,
	},
	{
		"role_name": "Fleet Driver",
		"desk_access": 1,
	},
)


def after_install():
	"""Run once when the app is installed on a site."""
	create_fleet_roles()
	frappe.db.commit()
	print("Fleet Management: installation complete.")


def create_fleet_roles():
	"""Create the Fleet roles if they do not already exist.

	Safe to run repeatedly: existing roles are left untouched so that any
	permission tuning done on site survives a reinstall or migrate.
	"""
	created = 0

	for role in FLEET_ROLES:
		role_name = role["role_name"]

		if frappe.db.exists("Role", role_name):
			print(f"Fleet Management: role '{role_name}' already exists, skipping.")
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": role.get("desk_access", 1),
				"is_custom": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		created += 1
		print(f"Fleet Management: created role '{role_name}'.")

	print(f"Fleet Management: {created} role(s) created, {len(FLEET_ROLES) - created} already present.")

	return created

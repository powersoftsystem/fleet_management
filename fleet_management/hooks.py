app_name = "fleet_management"
app_title = "Fleet Management"
app_publisher = "Powersoft Systems"
app_description = (
	"Fleet, rental, maintenance, insurance and trip costing management built on ERPNext"
)
app_email = "info@powersoftsystems.com"
app_license = "GPL-3.0"

required_apps = ["erpnext"]

# ---------------------------------------------------------------------------
# Includes in <head>
# ---------------------------------------------------------------------------

# app_include_css = "/assets/fleet_management/css/fleet_management.css"
# app_include_js = "/assets/fleet_management/js/fleet_management.js"

# ---------------------------------------------------------------------------
# Client scripts attached to DocTypes
# ---------------------------------------------------------------------------

doctype_js = {
	"Fleet Vehicle": "public/js/fleet_vehicle.js",
	"Fleet Rental Contract": "public/js/fleet_rental_contract.js",
	"Fleet Job Card": "public/js/fleet_job_card.js",
	"Fleet Fuel Log": "public/js/fleet_fuel_log.js",
	"Fleet Trip": "public/js/fleet_trip.js",
}

# doctype_list_js = {"Fleet Vehicle": "public/js/fleet_vehicle_list.js"}

# ---------------------------------------------------------------------------
# Apps screen (Frappe v15+/v16) - puts a Fleet Management icon on /apps
# ---------------------------------------------------------------------------

add_to_apps_screen = [
	{
		"name": "fleet_management",
		"logo": "/assets/fleet_management/images/fleet_management_logo.svg",
		"title": "Fleet Management",
		"route": "/app/fleet-management",
		"has_permission": "fleet_management.utils.has_app_permission",
	}
]

# ---------------------------------------------------------------------------
# Fixtures exported with `bench --site <site> export-fixtures`
# ---------------------------------------------------------------------------

FLEET_DOCTYPES = [
	"Fleet Vehicle",
	"Fleet Vehicle Type",
	"Fleet Driver",
	"Fleet Rental Contract",
	"Fleet Rental Item",
	"Fleet Rental Invoice Schedule",
	"Fleet Insurance Policy",
	"Fleet Insurance Vehicle",
	"Fleet Insurance Claim",
	"Fleet Compliance Document",
	"Fleet Maintenance Plan",
	"Fleet Maintenance Task",
	"Fleet Maintenance Part",
	"Fleet Job Card",
	"Fleet Fuel Log",
	"Fleet Trip",
	"Fleet Trip Expense",
	"Fleet Trip Stop",
]

FLEET_ROLES = ["Fleet Manager", "Fleet Supervisor", "Fleet Driver"]

fixtures = [
	{
		"dt": "Workspace",
		"filters": [["name", "=", "Fleet Management"]],
	},
	{
		"dt": "Number Card",
		"filters": [["module", "=", "Fleet Management"]],
	},
	{
		"dt": "Notification",
		"filters": [["name", "like", "Fleet - %"]],
	},
	{
		"dt": "Role",
		"filters": [["name", "in", FLEET_ROLES]],
	},
	{
		"dt": "Custom Field",
		"filters": [["dt", "in", FLEET_DOCTYPES]],
	},
	{
		"dt": "Property Setter",
		"filters": [["doc_type", "in", FLEET_DOCTYPES]],
	},
]

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

after_install = "fleet_management.install.after_install"

# before_uninstall = "fleet_management.install.before_uninstall"

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------

scheduler_events = {
	"daily": [
		"fleet_management.tasks.daily",
	],
	"weekly": [
		"fleet_management.tasks.weekly",
	],
}

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

# Restrict drivers to their own records. Enable once the site has decided how
# drivers map to users.
#
# permission_query_conditions = {
# 	"Fleet Trip": "fleet_management.permissions.fleet_trip_query_conditions",
# 	"Fleet Fuel Log": "fleet_management.permissions.fleet_fuel_log_query_conditions",
# }
#
# has_permission = {
# 	"Fleet Trip": "fleet_management.permissions.fleet_trip_has_permission",
# }

# ---------------------------------------------------------------------------
# Document events
# ---------------------------------------------------------------------------

# Controller logic lives in the DocType controllers. Cross-app hooks belong here.
#
# doc_events = {
# 	"Sales Invoice": {
# 		"on_submit": "fleet_management.events.sales_invoice.update_rental_schedule",
# 		"on_cancel": "fleet_management.events.sales_invoice.revert_rental_schedule",
# 	},
# 	"Asset": {
# 		"on_update": "fleet_management.events.asset.sync_fleet_vehicle",
# 	},
# }

# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

# override_doctype_class = {}
# override_whitelisted_methods = {}

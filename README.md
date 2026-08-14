# Fleet Management

A complete fleet, rental, maintenance, insurance and trip-costing application for
[Frappe](https://frappeframework.com) v15 / v16 and [ERPNext](https://erpnext.com).

Fleet Management turns ERPNext into an operations system for anyone who runs vehicles for a
living: haulage and logistics operators, plant and equipment hire companies, bus and taxi
fleets, and internal corporate fleets. Vehicles, drivers, rental contracts, workshop jobs,
fuel, insurance, statutory compliance and per-trip profitability all live in one module and
post straight through to ERPNext's Sales Invoice, Purchase Invoice, Stock Entry and Asset
records — no double entry, no spreadsheets.

---

## Why this app

* **One vehicle record, one truth.** Registration, odometer, rates, service due dates and
  every compliance expiry roll up onto the Fleet Vehicle so the fleet list itself is the
  exception report.
* **Rental billing that runs itself.** Contracts generate their own invoice schedule on the
  billing frequency you choose, and each period maps to an ERPNext Sales Invoice in one click.
* **Costing that is actually costed.** Trips carry revenue, fuel, tolls, driver expenses and
  workshop cost, and give you gross margin and cost per kilometre per trip, per vehicle.
* **Compliance you cannot forget.** Insurance, roadworthy, road tax and permits are tracked
  with reminder windows and are re-graded every night by the scheduler.

---

## Features by module

### Fleet register
* **Fleet Vehicle** — registration, type, ownership, branch, status (Available / On Rent /
  On Trip / In Maintenance / Out of Service / Sold), current odometer and odometer UOM,
  average consumption, GPS device ID and last known location.
* Links to the ERPNext **Asset**, **Item**, purchase **Supplier**, purchase date and amount,
  and a default **Cost Center** so fleet spend lands in the right place in the P&L.
* Hourly / daily / weekly / monthly hire rates held per vehicle, defaulted from the type.
* **Fleet Vehicle Type** — category, load and seating capacity, default rate card and the
  service intervals (distance and days) used to schedule maintenance.

### Drivers
* **Fleet Driver** — linked to an ERPNext **Employee** and **User**, with mobile number,
  licence number, class and expiry, medical certificate and defensive-driving expiry, plus a
  default vehicle.
* Expiry warnings on save so an out-of-date licence never quietly stays on the road.

### Rental and hire
* **Fleet Rental Contract** (submittable) — customer, period, billing frequency, with/without
  driver, security deposit, and a line per vehicle carrying rate basis, rate, quantity,
  mileage allowance, excess mileage rate and start/end odometer.
* Contract totals, invoiced and outstanding amounts; links to **Sales Order**, **Project**
  and **Cost Center**.
* Submitting a contract flips its vehicles to *On Rent*; cancelling releases them.
* **Fleet Rental Invoice Schedule** — one row per billing period with period start/end, due
  date, amount, status (Pending / Invoiced / Paid / Cancelled) and the resulting Sales Invoice.
  The daily scheduler creates due rows automatically for active contracts.

### Maintenance and workshop
* **Fleet Maintenance Plan** — per vehicle and service type, with distance and day intervals,
  last service date/odometer and the computed next due date and odometer.
* **Fleet Job Card** (submittable) — job type, priority, status, reported by, odometer,
  in-house or external workshop, supplier, technician, start/end datetime and computed
  downtime hours.
* Parts and labour: parts lines (item, qty, UOM, rate, warehouse) roll into parts cost, added
  to labour and other cost for a true total cost per job.
* Issue parts to the job as a **Material Issue Stock Entry**, bill external work to a
  **Purchase Invoice**, and attach the job to a **Fleet Insurance Claim** for accident repairs.
* On submit the linked maintenance plan's last service and next due are rolled forward.

### Fuel
* **Fleet Fuel Log** (submittable) — fuel type, odometer, quantity, rate and amount, full-tank
  flag, supplier, item and cost centre.
* Distance since last fill, consumption and cost per distance computed automatically, with
  divide-by-zero protection; the vehicle odometer only ever moves forward.
* Weekly job recalculates each vehicle's rolling average consumption from submitted logs.

### Insurance and compliance
* **Fleet Insurance Policy** (submittable) — insurer, broker, cover type, period, and a line
  per covered vehicle with sum insured, premium and excess; totals roll up to the policy and
  the covered vehicles' insurance expiry is refreshed on submit.
* **Fleet Insurance Claim** (submittable) — policy, vehicle, driver, incident date and type,
  estimated loss, claim amount, excess paid, settled amount and settlement date.
* **Fleet Compliance Document** — roadworthy certificates, road tax, permits, fitness and any
  other document type, with issue and expiry dates, reminder window, cost and the Purchase
  Invoice that paid for it. Status is graded Valid / Expiring Soon / Expired nightly.

### Trips and profitability
* **Fleet Trip** (submittable) — vehicle, driver and co-driver, customer, optional rental
  contract, origin and destination, planned versus actual start and end, cargo description and
  weight, start/end odometer and actual distance.
* Freight rate by rate basis, revenue amount, trip expenses (with paid-by and Expense Claim
  link) and multiple stops.
* Gross margin and cost per distance computed on every save; invoice the trip to a **Sales
  Invoice** or ship against a **Delivery Note**.

### Automation
* **Daily** — re-grade compliance document and insurance policy statuses, refresh affected
  vehicles' expiry and next-service fields, and raise due rental invoice schedule rows.
* **Weekly** — recalculate vehicle average consumption from recent fuel logs.
* Every scheduled job is individually guarded, so one bad record cannot stop the rest.

---

## Screenshots

> Screenshots live in `docs/screenshots/`. Add or replace them there and they will render below.

| | |
|---|---|
| ![Fleet workspace](docs/screenshots/workspace.png) | ![Fleet Vehicle](docs/screenshots/fleet-vehicle.png) |
| ![Rental Contract](docs/screenshots/rental-contract.png) | ![Job Card](docs/screenshots/job-card.png) |
| ![Trip costing](docs/screenshots/trip.png) | ![Compliance dashboard](docs/screenshots/compliance.png) |

---

## Installation

Fleet Management is a standard Frappe app and installs with bench.

```bash
# from your bench directory
bench get-app https://github.com/powersoftsystems/fleet_management.git
bench --site <site> install-app fleet_management
bench --site <site> migrate
bench restart
```

To update later:

```bash
bench update --apps fleet_management
```

### Dependencies

* **Frappe Framework** v15 or v16
* **ERPNext** v15 or v16 — **required**. Fleet Management links to and creates ERPNext
  documents (Customer, Supplier, Item, Sales Invoice, Purchase Invoice, Stock Entry, Asset,
  Employee, Expense Claim, Cost Center), so the app will not function on a bare Frappe site.
* Python 3.10+

Enable the scheduler on your site so the daily and weekly jobs run:

```bash
bench --site <site> enable-scheduler
```

---

## Roles

The installer creates three roles, all idempotently:

| Role | Intended for | Typical access |
|---|---|---|
| **Fleet Manager** | Fleet owner / operations manager | Full control of all Fleet documents, rate cards, contracts, policies and claims; submit and cancel rights. |
| **Fleet Supervisor** | Workshop and dispatch supervisors | Day-to-day operations — job cards, fuel logs, trips, maintenance plans and compliance documents; no rate card or contract control. |
| **Fleet Driver** | Drivers | Their own trips and fuel logs, and read access to the vehicles assigned to them. |

Assign roles from **User → Roles** after installation. Pair them with ERPNext's
Accounts User / Stock User roles where drivers or supervisors must post invoices or issue parts.

---

## Configuration checklist

1. Create your **Fleet Vehicle Types** and set the default rate card and service intervals.
2. Create **Fleet Vehicles**, linking each to its ERPNext Asset and Item where you track them.
3. Add **Fleet Drivers** and link them to Employees.
4. Load current **Fleet Insurance Policies** and **Fleet Compliance Documents** so the vehicle
   expiry fields are populated.
5. Create a **Fleet Maintenance Plan** per vehicle and service type.
6. Turn on the scheduler and let the daily job take over the reminders and rental billing.

---

## Roadmap

* **Telematics integration** — ingest odometer, fuel level, engine hours, harsh-braking and
  geofence events from GPS/telematics providers so trips close themselves and maintenance is
  triggered by real engine data rather than manual readings.
* **Driver mobile app** — a Frappe PWA for drivers: accept and start trips, capture proof of
  delivery and signatures, log fuel with a photo of the pump, raise defect reports straight
  into a Job Card, and carry licence and vehicle documents offline.
* Fleet utilisation and cost-per-kilometre dashboards and printable operator reports.
* Tyre and battery lifecycle tracking with per-position fitment history.
* Automated fuel-card statement import and reconciliation.

---

## Contributing

Issues and pull requests are welcome. Please run `ruff check .` and `ruff format .` before
opening a PR, and keep controller logic in the DocType controllers with shared helpers in
`fleet_management/utils.py`.

---

## Licence

GNU General Public License v3.0. See [LICENSE](LICENSE) for the full text.

Copyright (C) Powersoft Systems.

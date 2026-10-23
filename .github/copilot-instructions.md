# Uthiram Repository Instructions

## Canonical application

The root `backend/` and `frontend/` form Uthiram, a fictional-data blood-coordination prototype. This application is blood-only. Its canonical roles are `ADMIN`, `BLOOD_BANK`, and `GENERAL_DONOR`; do not add organ-donation workflows or organ-specific roles here. The separate `client/`, `server/`, and nested `donar/` projects are legacy projects and must remain untouched unless a task explicitly includes them.

The product supports blood-request verification, opt-in donor outreach, donor responses, and coordination. It is a decision-support and coordination tool, not a medical authority. A blood-group filter or donor response never establishes medical eligibility, compatibility, collection, or completed donation. All sample data must be fictional; never use real patient or donor data.

## Safety and access rules

- Do not claim that the app determines a donor's medical eligibility or that a donor is compatible, suitable, approved, or guaranteed to donate.
- Do not add payments, incentives, or rewards tied to donation.
- Use explicit response schemas; never return donor phone numbers or precise contact details from match, notification, or request listings.
- Donor contact details may be returned only after the donor opts in for a particular reservation, the phone is verified, and the caller is the owning requester, the owning verified blood bank, or an administrator. Respect donor revocation.
- Require the appropriate role on every protected route and enforce object ownership or verified blood-bank organisation scope in addition to role checks.
- Only administrators may review blood-bank registrations and verify requests. Blood banks must be verified and active before they can perform bank operations.
- A donor's acceptance is willingness to coordinate, not medical approval or a completed donation. Do not mark a request `FULFILLED` without a donor completion report and authorised blood-bank/admin verification.
- The backend RBC ABO/Rh compatibility module is the sole matching authority. Unknown or unverified donor blood groups are excluded from automated RBC matching. Do not apply RBC rules to plasma, platelets, whole blood, or other components.
- RBC matching requires the donor-selected blood bank to record both blood-group verification and screening completion. These records do not establish medical eligibility or transfusion suitability. Receiving blood-bank professionals must perform required assessment, grouping, component-specific checks, and crossmatching.
- Log sensitive reads and writes using the existing audit service. Do not log phone numbers, credentials, or unnecessary personal data.
- Do not expose donor lists to the public. Donors may only access their own profile, alerts, reservations, and requests.

## Implementation conventions

- Follow the existing FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest, React, TypeScript, Vite, and styling patterns.
- Keep business logic in service modules, validate input with Pydantic, use parameterized SQLAlchemy statements, and keep response schemas explicit.
- Add positive and negative authorization tests for access-control changes, plus workflow tests for state transitions and failure paths.
- Keep the API and browser demo boundary explicit: `frontend/` currently uses fictional browser-only state and is not connected to the API. Never imply that the frontend role preview enforces authorization.
- The outreach worker depends on PostgreSQL row-level locks. SQLite tests are not proof of production concurrency behavior.
- Update `docs/architecture.md` and `README.md` when API behavior, roles, setup, or workflow changes. Document incomplete functionality honestly.
- Run focused backend tests from `backend/`, frontend build/lint from `frontend/`, and `git diff --check` for code changes. Do not fix unrelated pre-existing issues or revert user changes.

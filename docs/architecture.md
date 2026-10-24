# Uthiram Blood Coordination Workflow and API

## Scope and safety

The canonical application coordinates fictional blood requests and willing donors. It is not a medical authority: blood-group filtering and donor responses do not establish eligibility, compatibility, collection, or a completed donation. Use mock data only. Clinical screening and collection decisions remain with authorised professionals.

The canonical API has three roles: `ADMIN`, `BLOOD_BANK`, and `GENERAL_DONOR`. The React site opens at account access and uses this API for registration and sign-in: administrators use their provisioned username, donors and blood banks use email, and login completes through the configured OTP or TOTP challenge. An HTTP-only refresh cookie restores a signed-in session after reload; the access token is held only in memory. The API's `/auth/session` endpoint returns the role associated with the authenticated token. Administrator accounts cannot self-register, and new blood-bank organisations remain pending until verified by an administrator. After sign-in, the dashboard remains a fictional-data demo and is not an authorization boundary or operational workflow. Donors can submit a browser-only blood request and view its demo status separately from incoming donor alerts. A blood bank can accept a donor-submitted request for coordination or decline it; acceptance does not verify the request, and administrator verification remains required before outreach. The bank's decision is shown on the donor's request page. These demo requests and decisions are not sent to the API. The blood-bank overview shows illustrative aggregate blood-group counts only and exposes no donor contact directory. Donor contact details remain reservation-specific and subject to consent, phone verification, authorization, and revocation. Other projects in the repository are separate legacy applications.

## Request lifecycle

`PENDING_VERIFICATION → VERIFIED → OUTREACH_ACTIVE → COORDINATION → COMPLETED_PENDING_VERIFICATION → FULFILLED`

Requests may also be rejected, require clarification, be cancelled, expire, be stopped, or exhaust the configured outreach stages. Requests do not alert donors until staff verify and start outreach. Only an administrator can verify a request; a blood-bank account can operate only on requests belonging to its own verified, active organisation. Donors and requesters can read or cancel only their own requests.

`FULFILLED` is set only after every required active reservation has a donor completion report that an authorised blood bank or administrator verifies. The legacy `POST /requests/{id}/fulfil` endpoint deliberately returns `409 Conflict`; it cannot directly mark a request fulfilled.

## Outreach and reservations

The backend applies five server-managed stages. Each stage lasts two minutes; the worker advances due stages and expires requests whose required-by time passes. The fifth stage begins after approximately eight minutes.

| Stage | Range | Duration |
| --- | --- | --- |
| 1 | 0–5 km | 2 minutes |
| 2 | 5–10 km | 2 minutes |
| 3 | 10–15 km | 2 minutes |
| 4 | 15–20 km | 2 minutes |
| 5 | Beyond 20 km | 2 minutes |

Automated donor matching currently supports red-cell requests only. One backend compatibility module defines the eight ABO/Rh red-cell donor groups for each recipient group and serves the public table used by the frontend. Donors are included only when their blood group has been verified by the verified blood bank they selected, a screening-completion record exists for that same institution, that group is a potential red-cell donor group for the request, availability is `AVAILABLE`, emergency-alert consent is active, availability was confirmed within the last 30 days, and approximate coordinates fall in the current stage. For a bank-owned request, the donor's blood-group review must also be associated with that requesting bank. A donor receives no more than one notification per request. Plasma, platelets, whole blood, and other components require separate clinically approved workflows and cannot start automated donor matching here.

Donors select an active, verified blood bank using `GET /blood-banks/verified`, at profile registration, or through the profile update route. That institution sees the donor's pending blood-group and screening queues and can record the corresponding reviews. Group verification records confirmation of the donor's recorded blood group; screening completion records that a screening process was performed. Neither is an eligibility or transfusion-suitability decision. The receiving institution remains responsible for donor assessment, repeat grouping, component-specific checks, and crossmatching where indicated. Unknown, unverified, or not-screened donor groups are excluded. Blood group filtering, proximity, and donor responses identify potential candidates only.

The API persists outreach batches, notifications, responses, and per-unit reservations. Accepting an alert reserves one unit; PostgreSQL row locking and a partial unique index prevent multiple active reservations from taking the same unit. Donors may cancel a reservation during its two-minute grace period; cancellation resumes outreach where appropriate. The worker uses `FOR UPDATE SKIP LOCKED` and requires PostgreSQL. SQLite tests do not verify production concurrency behavior.

The worker runs as the `outreach-worker` Compose service. `POST /requests/{id}/expand-radius` is an authorized manual advancement endpoint; normal progression does not depend on a browser invoking it.

The API serializes each request's acceptances with a PostgreSQL row lock and uses a partial unique index for active request-unit reservations. The configured `required_donors` count explicitly controls whether a request accepts one or multiple reservations. Notification uniqueness prevents repeat alerts to the same donor for a request.

## Roles and onboarding

- `GENERAL_DONOR`: manages their own donor profile, availability and consent; views and responds to their own active alerts; manages their reservations and contact-sharing choice; reports completion for their own reservation. This role may also submit a request, but can only view or cancel requests they submitted.
- `BLOOD_BANK`: self-registers an organisation, but remains pending until an administrator verifies it. A verified, active bank can manage its own request operations and verify completion reports. Staff access is linked to that organisation.
- `ADMIN`: provisioned using the `ADMIN_EMAIL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD` environment settings and `python -m app.commands.provision_admin` from `backend/`. The password is Argon2-hashed; an existing account is not reset by rerunning the command. Admins review blood-bank registrations, verify requests, and can perform authorised operations.

New requests require the account phone to be verified. In the prototype, request an OTP with `POST /auth/phone/verify/request` and verify it with `POST /auth/phone/verify`. The configured development OTP provider is a mock; do not treat it as production SMS verification.

## Consent-based contact sharing

Donor phone numbers are not included in match or request responses. A donor may opt in to share a verified phone number when accepting an alert. Only the request owner, its owning verified blood bank, or an administrator can retrieve it for the active or completed reservation. The donor can revoke sharing. Contact reads and revocations are audited.

## Completion verification

1. The donor submits `POST /requests/{request_id}/reservations/{reservation_id}/completion-report`.
2. A blood-bank staff member for the request's verified organisation, or an administrator, verifies or requests correction at `POST /requests/{request_id}/completion-reports/{record_id}/verify`.
3. After all required reservations have verified reports, the request becomes `FULFILLED`.

## Main endpoints

| Method | Path | Access |
| --- | --- | --- |
| `POST` | `/auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset-password` | Public; registration supports donors and blood banks; admins cannot self-register |
| `POST` | `/auth/refresh`, `/auth/logout` | Refresh cookie; logout also requires a valid access token |
| `GET` | `/auth/session` | Authenticated account; returns its role |
| `POST` | `/auth/phone/verify/request`, `/auth/phone/verify` | Authenticated account |
| `GET` | `/compatibility/rbc` | Public static RBC rule table; contains no donor data |
| `GET` | `/blood-banks/verified` | Public list of institution names and approximate localities for donor selection |
| `POST` | `/donors/profile`; `GET` `/donors/profile` | Donor, own profile |
| `PATCH` | `/donors/profile/blood-group` | Donor, own profile; clears prior group verification when changed |
| `PATCH` | `/donors/profile/blood-group-verification-bank` | Donor, selects a verified bank; clears prior verification and screening records when changed |
| `GET` | `/blood-banks/donors/pending-blood-group-verification`, `/blood-banks/donors/pending-screening` | Owning verified blood bank; limited to donors who selected that bank |
| `POST` | `/donors/{donor_profile_id}/blood-group/verify` | Verified blood bank; confirms the already-recorded group |
| `POST` | `/blood-banks/donors/{donor_profile_id}/screening-review` | Selected verified blood bank; records or revokes screening completion, not medical eligibility |
| `PATCH` | `/donors/availability` | Donor, own profile |
| `GET` | `/blood-banks/me` | Blood bank, own organisation |
| `GET` | `/admin/blood-banks`; `POST` `/admin/blood-banks/{id}/verification` | Administrator |
| `POST` | `/requests` | Phone-verified donor or verified blood bank |
| `GET` | `/requests`, `/requests/{id}` | Donor (own), blood bank (own organisation), or administrator |
| `POST` | `/requests/{id}/verify` | Administrator |
| `POST` | `/requests/{id}/assign`, `/start-outreach`, `/expand-radius`, `/stop-outreach` | Administrator or owning verified blood bank |
| `GET` | `/requests/{id}/matches` | Administrator or owning verified blood bank; no phone numbers |
| `GET` | `/notifications`; `POST` `/notifications/{id}/accept`, `/decline` | Donor, own alerts |
| `GET` | `/donors/reservations` | Donor, own reservations |
| `POST` | `/requests/{id}/reservations/{reservation_id}/cancel` | Donor, own reservation |
| `POST` | `/donors/reservations/{reservation_id}/revoke-contact-sharing` | Donor, own reservation |
| `GET` | `/requests/{id}/reservations/{reservation_id}/contact` | Request owner, owning verified bank, or administrator; only after donor opt-in |
| `POST` | `/requests/{id}/reservations/{reservation_id}/completion-report` | Donor, own reservation |
| `POST` | `/requests/{id}/completion-reports/{record_id}/verify` | Administrator or owning verified blood bank |
| `POST` | `/requests/{id}/fulfil` | Retired; returns `409 Conflict` |
| `POST` | `/requests/{id}/cancel` | Donor (own request), owning verified blood bank, or administrator |
| `GET` | `/dashboard/stats` | Administrator or verified blood bank |
| `GET` | `/admin/analytics/blood-compatibility` | Administrator; database-derived request groups, identified matches, notifications/acceptance by donor group, verified fulfilments, unfulfilled requests, and average response time |

All route paths are relative to the API root. Consult the running OpenAPI page for request and response schemas.

## Persistence and operations

Blood-specific persistence covers organisations and staff, donor profiles and institution-linked group/screening review records, component-specific requests, request verification history, donor matches, outreach batches, notifications with a donor-group history snapshot, responses, status history, consent, reservations, and completion reports. Workflow actions and sensitive profile/contact reads emit audit events. Apply schema changes with `alembic upgrade head`.

The API, database, frontend, and outreach worker are defined in Docker Compose. The frontend currently uses browser-only fictional state; its donor-facing compatibility view loads the public RBC matrix from the API but does not read a verified personal profile from the API. The database-backed admin analytics endpoint is available, but the demo analytics screen is not wired to it because the frontend has no login/API integration yet. There is no blood inventory matching workflow, document-upload or license-storage flow, full production notification provider, or production readiness claim. Tests use SQLite for most workflow cases; validate migrations and locking against PostgreSQL before deployment.

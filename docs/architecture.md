# Uthiram Workflow and API

## Request lifecycle

`PENDING_VERIFICATION → VERIFIED → OUTREACH_ACTIVE → COORDINATION → FULFILLED`

Requests may also be rejected, require clarification, be cancelled, expire, or exhaust the configured radius stages. Request creation never directly sends alerts. The coordinator verification endpoint records reviewer, decision, timestamp, status history, and an audit event. Only verified requests can start outreach.

## Radius policy

| Stage | Range | Response window |
| --- | --- | --- |
| 1 | 0–5 km | 3 minutes |
| 2 | 5–10 km | 3 minutes |
| 3 | 10–15 km | 4 minutes |
| 4 | 15–25 km | 5 minutes |

Matching filters by exact recorded blood group, `AVAILABLE` status, active emergency-alert consent, recent availability confirmation, and approximate distance. Each donor receives at most one alert per request. A decline is recorded but does not itself expand the radius. Expansion is available after the current stage window; accepted responses are compared to `required_donors`. When the threshold is met, queued alerts are cancelled and request coordination begins.

The frontend demonstration uses fictional local state and a real-time countdown. The API persists stages and notification records. A production deployment still needs a durable background scheduler/worker to advance expired stages and close requests at their required-by time if no client invokes the expansion endpoint.

## Roles

- `DONOR`: owns one blood profile, controls availability and consent, reads their own active alerts, and accepts or declines only their own notification.
- `REQUESTER`: creates requests and reads/cancels only requests they submitted.
- `COORDINATOR`: verifies requests, assigns coordination, starts/expands/stops outreach, views masked matching details, and records fulfilment.
- `ADMIN`: shares coordinator API permissions in this prototype; user and organisation administration still requires dedicated endpoints before deployment.

Coordinator and admin accounts are not self-registered. Existing JWT access-token and refresh-token flows are used. Non-donor users cannot enumerate donor profiles through blood endpoints.

## Main endpoints

| Method | Path | Role |
| --- | --- | --- |
| `POST` | `/auth/register`, `/auth/login` | Public; self-registration is limited to donor/requester |
| `POST` | `/donors/profile` | Donor |
| `GET` | `/donors/profile` | Donor, own profile |
| `PATCH` | `/donors/availability` | Donor, own profile |
| `POST` | `/requests` | Requester |
| `GET` | `/requests`, `/requests/{id}` | Requester (own) or coordinator/admin |
| `POST` | `/requests/{id}/assign`, `/verify` | Coordinator/admin |
| `POST` | `/requests/{id}/start-outreach` | Coordinator/admin, verified requests only |
| `GET` | `/requests/{id}/matches` | Coordinator/admin; donor contact data omitted |
| `GET` | `/notifications` | Donor, own active alerts only |
| `POST` | `/notifications/{id}/accept`, `/decline` | Donor, own alert only |
| `POST` | `/requests/{id}/expand-radius`, `/stop-outreach` | Coordinator/admin |
| `POST` | `/requests/{id}/fulfil` | Coordinator/admin |
| `POST` | `/requests/{id}/cancel` | Requester (own) or coordinator/admin |
| `GET` | `/dashboard/stats` | Coordinator/admin |

## Persistence

Blood-specific tables include organisations, coordinators, donor profiles, requests, verifications, donor matches, outreach batches, notifications, responses, status history, and versioned consent. Existing append-only `audit_logs` and its hash chain record blood workflow actions. Apply the schema with `alembic upgrade head`.

## Safety boundary

Exact donor addresses and phone numbers are not returned by matching APIs. A recorded blood group match is an outreach filter only, not a compatibility or eligibility decision. Clicking **Accept** means willingness to coordinate; it does not confirm a donation. All displayed sample data is fictional.
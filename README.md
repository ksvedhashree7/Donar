# Uthiram

**Verified Requests. Willing Donors. Coordinated Action.**

Uthiram is a fictional-data prototype for coordinating verified blood requirements with willing nearby donors. Its central workflow is request submission, admin verification, consent-based radius outreach, explicit donor responses, follow-up, and automatic cancellation of outstanding alerts when requested donor units are reserved.

Uthiram is not a medical authority. A donor response is not confirmation of eligibility or donation. Final eligibility, compatibility, screening, collection, and clinical decisions remain with the authorised hospital or blood bank.

## Features

- Blood bank/admin workspace preview with request queue, outreach stages, response counts, approximate coverage map, activity, and community response analytics.
- Blood-bank overview with fictional aggregate counts by blood group; it does not expose a donor contact list.
- Donor dashboard with availability and emergency-alert consent controls, a timed flash alert, explicit accept/decline actions, and the ability to submit and track a blood request that a blood bank can accept or decline for coordination.
- Role-specific sign-in and registration form previews for admins, blood banks, and donors; they do not create accounts or authenticate.
- Requester tracking view with a status timeline and no donor personal contact information.
- Five server-managed outreach stages: 0–5, 5–10, 10–15, and 15–20 km for two minutes each, followed by a broader stage beyond 20 km.
- Backend red-cell group compatibility matching for verified, available, consented donors, plus a responsive donor-facing compatibility table.
- Demo controls for creating a fictional emergency, advancing a radius, stopping outreach, and recording fulfilment.
- FastAPI endpoints, SQLAlchemy models, PostgreSQL migrations, three account roles, blood bank verification, per-unit reservations, and audit events.

All people, organisations, localities, requests, and responses shown in the frontend are fictional. Donor location is approximate; phone numbers and exact addresses are never presented.

## Project Layout

```text
backend/                 FastAPI API, SQLAlchemy models, Alembic and pytest
frontend/                Canonical Uthiram React + TypeScript + Vite application
docs/architecture.md     Blood request workflow, radius policy and API reference
docker-compose.yml       Local PostgreSQL, MinIO, API and Vite services
start-uthiram.bat        Windows launcher; checks readiness before opening Chrome
stop-uthiram.bat         Stops local containers without deleting database volumes
```

The canonical website is `frontend/`. `frontend/src/main.tsx` mounts `UthiramApp.tsx`; its existing responsive UI and styling are preserved. `backend/` is the canonical Python API and stores workflow records through SQLAlchemy/PostgreSQL migrations. The root API supports only `ADMIN`, `BLOOD_BANK`, and `GENERAL_DONOR`; organ-donation endpoints are retired from this app.

Other top-level projects are intentionally retained because they are not interchangeable copies: `client/` and `server/` form a separate React/Express/Mongoose organ-donation prototype; `donar/` is a nested Git repository with its own client/server and uncommitted work. They are not part of this launcher or canonical application. The two prototype PDFs and the nested Git repository remain untouched. The unused root npm manifest/lockfile and the duplicate `uthiram-standalone/` HTML export were removed.

## Current Integration Boundary

The React dashboard is still a fictional-data demo whose requests, donor responses, notifications, account-form previews, role preview, and countdown are held in browser state. Donors and blood banks can submit demo blood requests; blood banks can accept a request for coordination or decline it, and the donor workspace displays that decision separately from incoming donor alerts. Acceptance is not request verification: administrator verification is still required before outreach starts. These browser-only requests and decisions are not sent to the API. The role-specific sign-in and registration forms are visual only: credentials are not checked or sent, and registrations are not saved. The blood-bank blood-group counts are illustrative aggregates, not live inventory or donor records. The donor-facing red-cell compatibility table loads its rules from the backend's public compatibility endpoint, so the displayed matrix and automated matching share the same authoritative backend rules. The donor profile and other dashboard data remain fictional and are not API-backed. The API independently provides persisted authentication, donor/request workflows, role checks, audit records, blood bank verification, institution-linked donor blood-group and screening records, RBC donor-group compatibility matching, component-gated outreach, unit reservations, server-managed distance-tier outreach, consent-based contact sharing, institution-verified completion, and database-derived admin compatibility analytics; its HTTP routes are documented in [docs/architecture.md](docs/architecture.md). There is currently no integration for the other dashboard data, document storage flow, or WebSocket/push provider. The dashboard's demo role preview is not an authorization control. Do not use this prototype with real donor or patient data.

Automated group matching is restricted to red-cell requests and donors whose recorded groups and screening completion were reviewed by the verified bank they selected. These review records do not declare medical eligibility or transfusion suitability; the receiving institution remains responsible for assessment, component-specific checks, repeat blood grouping, and crossmatching where indicated. Plasma, platelet, whole-blood, and other component matching is not implemented.

## Run on Windows

Requirements: Docker Desktop with Docker Compose, Google Chrome (or another default browser), and a local `.env` file. The Compose stack runs PostgreSQL, FastAPI, and Vite on loopback ports; MinIO is available but is not needed by the current blood workflow. PostgreSQL is managed in a Docker named volume, not installed as a Windows service. Docker is not installed in the inspected environment. A PostgreSQL service answered on local port 5432, but the documented development credentials were rejected; its configuration is unknown and was left untouched.

For the browser-only demo, double-click [open-uthiram-demo.bat](open-uthiram-demo.bat) in the repository folder. It starts the existing frontend if needed and opens Chrome at `http://127.0.0.1:5173/`; it does not start or connect to PostgreSQL. For the full Docker stack, use [start-uthiram.bat](start-uthiram.bat) instead.

Create the local environment file once, then review the development-only values:

```powershell
Copy-Item .env.example .env
```

Replace every `CHANGE_ME` value in `.env` before launch. Use a URL-safe database password in both `POSTGRES_PASSWORD` and the password portion of `DATABASE_URL`. Set unique random values of at least 32 characters for `JWT_SECRET` and `TOTP_ENCRYPTION_KEY`, and unique local credentials for MinIO. Generate and enter these values using a password manager or another secure local method; do not paste secrets into chat or commit them.

Start with `start-uthiram.bat` in the repository root. It checks Docker and the environment, asks before starting PostgreSQL/applying Alembic migrations, waits for database and HTTP health checks, then opens `http://127.0.0.1:5173/` in Chrome. If Chrome is installed in a nonstandard location, set `CHROME_PATH` to its executable. The launcher and Compose port bindings do not expose the app on the public network.

To stop the app safely, run `stop-uthiram.bat`. It stops containers and preserves PostgreSQL data. `docker compose down` also preserves the named volumes. **Do not use `docker compose down -v`** unless you intentionally want to delete the local database and MinIO data.

### Desktop Shortcut

For a one-click browser demo, right-click `open-uthiram-demo.bat` in File Explorer and choose **Show more options → Create shortcut**. Move the shortcut to the Desktop and rename it `Uthiram — Blood Donation`. For the full Docker stack, create the shortcut from `start-uthiram.bat` instead. Keep the selected launcher in the repository; the shortcut must point to that file.

### Manual Start

From the repository root, after creating `.env` and starting Docker Desktop:

```powershell
docker compose up -d db
docker compose build backend frontend
docker compose run --rm backend alembic upgrade head
docker compose up -d backend frontend outreach-worker
```

Open `http://127.0.0.1:5173/`. The API health endpoint is `http://127.0.0.1:8000/health`; its OpenAPI page is `http://127.0.0.1:8000/docs`.

To run only the frontend without Docker, use `cd frontend`, `npm install`, then `npm run dev`. The frontend demo works without PostgreSQL, but this does not start or connect to the API.

## Tests and Builds

With frontend dependencies installed, run `npm run build` and `npm run lint` from `frontend/`. With `backend/requirements.txt` installed, run `python -m pytest` from `backend/`. Backend tests use an isolated SQLite test database; they do not verify a live PostgreSQL connection. See the final task report for which checks were actually run in the current environment.

## Demo walkthrough

1. Open the blood-bank workspace and select **Simulate emergency**.
2. Submit the fictional ABC Hospital request to simulate verification and start the first outreach stage.
3. Use **Advance demo stage** to move outward, or switch to the donor role and accept/decline the alert.
4. Donor acceptance requires a separate confirmation and does not represent medical eligibility or a completed donation.
5. Use the demo-only fulfilment control to stop remaining alerts. In the API workflow, fulfilment instead requires donor completion reports and receiving-institution verification.

The frontend clock runs in real time. Use the demo stage control to demonstrate radius expansion without waiting for a full response window.

## Roles and API

The canonical API supports `ADMIN`, `BLOOD_BANK`, and `GENERAL_DONOR`. Donors and blood banks can self-register; blood-bank operations remain disabled until an administrator verifies the organisation. Admin accounts are provisioned from `backend/` using `python -m app.commands.provision_admin` after setting `ADMIN_EMAIL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`. Requests require a verified account phone number. See [docs/architecture.md](docs/architecture.md) for the role and ownership rules.

The blood API includes donor profile and availability, request create/list/detail, administrator request verification, blood-bank review, outreach start/expand/stop, donor alert inbox and accept/decline, per-unit reservations with a two-minute cancellation grace period, optional donor contact sharing, and donor-reported/institution-verified completion. A PostgreSQL-backed worker advances expired outreach stages. The legacy direct-fulfil endpoint returns `409 Conflict`. See [docs/architecture.md](docs/architecture.md) for lifecycle and endpoint details.

## Environment Variables

`.env.example` contains placeholder values for PostgreSQL, CORS, JWT, TOTP, MinIO, and initial administrator provisioning. It is a template, not a production secret set. `.env` is ignored by Git; do not commit actual credentials. The development database URL used inside Compose addresses the `db` service. This prototype is not configured for production use or real patient data.
# Uthiram

**Verified Requests. Willing Donors. Coordinated Action.**

Uthiram is a fictional-data prototype for coordinating verified blood requirements with willing nearby donors. Its central workflow is request submission, coordinator verification, consent-based radius outreach, explicit donor responses, follow-up, and automatic cancellation of outstanding alerts when enough willing responses are recorded.

Uthiram is not a medical authority. A donor response is not confirmation of eligibility or donation. Final eligibility, compatibility, screening, collection, and clinical decisions remain with the authorised hospital or blood bank.

## Features

- Coordinator dashboard with request queue, outreach stages, response counts, approximate coverage map, activity, and community response analytics.
- Donor dashboard with availability and emergency-alert consent controls, a timed flash alert, and explicit accept/decline actions.
- Requester tracking view with a status timeline and no donor personal contact information.
- Four configurable demo stages: 0–5 km for 3 minutes, 5–10 km for 3 minutes, 10–15 km for 4 minutes, and 15–25 km for 5 minutes.
- Demo controls for creating a fictional emergency, advancing a radius, stopping outreach, and recording fulfilment.
- FastAPI endpoints, SQLAlchemy models, PostgreSQL migration, JWT role checks, request ownership checks, and audit events.

All people, organisations, localities, requests, and responses shown in the frontend are fictional. Donor location is approximate; phone numbers and exact addresses are never presented.

## Architecture

- `frontend/`: React, TypeScript, Vite, and responsive CSS. The demo workflow runs locally in the browser.
- `backend/`: FastAPI, JWT authentication, SQLAlchemy, Alembic, and PostgreSQL.
- `docs/`: workflow and API notes.
- `docker-compose.yml`: PostgreSQL, MinIO, API, and frontend services.

The frontend demo state is intentionally usable without a database. The backend endpoints persist real workflow records when configured; the frontend currently does not require backend connectivity for the hackathon walkthrough.

## Run locally

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173/`.

### API and database

From the repository root, copy `.env.example` to `.env`, then run:

```powershell
docker compose up --build -d
docker compose exec backend alembic upgrade head
```

The API is at `http://localhost:8000`; OpenAPI docs are at `http://localhost:8000/docs`.

To run backend tests in an environment with `backend/requirements.txt` installed:

```powershell
cd backend
python -m pytest
```

## Demo walkthrough

1. Open the coordinator overview and select **Simulate emergency**.
2. Submit the fictional ABC Hospital request to simulate verification and start the first outreach stage.
3. Use **Advance demo stage** to move outward, or switch to the donor role and accept/decline the alert.
4. Donor acceptance requires a separate confirmation and does not represent medical eligibility or a completed donation.
5. Record fulfilment from outreach to stop all remaining alerts.

The frontend clock runs in real time. Use the demo stage control to demonstrate radius expansion without waiting for a full response window.

## Roles and API

Self-registration supports donor and requester accounts; coordinator and administrator roles are provisioned by an authorised administrator. Every coordinator endpoint checks role permissions; requesters can only read or cancel their own requests, and donors can respond only to their own notifications.

The blood API includes donor profile and availability, request create/list/detail, coordinator assignment and verification, outreach start/expand/stop, donor alert inbox and accept/decline, fulfilment/cancellation, and dashboard statistics. See [docs/architecture.md](docs/architecture.md) for lifecycle and endpoint details.

## Environment variables

See `.env.example` for PostgreSQL, CORS, JWT, TOTP, and MinIO development settings. Replace development secrets before any non-local deployment. This prototype is not configured for production use or real patient data.
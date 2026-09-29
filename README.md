# Uthiram

A small React and Express blood donor matching app. Donor searches use an exact blood-group match and a 20 km radius around New Delhi. Registration collects donor consent and self-reported prescreen answers; only clear self-reports are included in searches.

## Run locally

1. Install dependencies from this directory with `npm install`.
2. Copy `server/.env.example` to `server/.env` and set `MONGO_URI` to your MongoDB connection string.
3. Start MongoDB, then seed sample records with `npm run seed`.
4. Start the client and API with `npm run dev`.
5. Open `http://localhost:5173`.

The API is available at `http://localhost:5000`; its health welcome route is `/`. Donor registration uses `POST /api/donors/register`, and matching uses `POST /api/match`. The Vite development server proxies `/api` calls to the API. Create a production client bundle with `npm run build`.

## Request verification demo

Blood requests can be submitted through the **Request blood** view. They remain `Pending` and are not matched or sent to donors until a reviewer approves them in **Admin review**. In local development, the admin key is `demo-admin`; set `ADMIN_API_KEY` in `server/.env` to override it. Production mode requires an explicit key and has no demo fallback. Do not use the demo key in a deployed environment.

The admin API uses `x-admin-key`: `GET /api/requests/pending`, `PUT /api/requests/:id/approve`, and `PUT /api/requests/:id/reject`. `POST /api/requests` creates a pending request. Approval creates database records for up to three exact-blood-group donor alerts within 20 km; these are simulated only and do not send SMS or place calls. The reviewer workflow is a prototype key gate, not a replacement for authenticated hospital accounts or production RBAC.

Prescreen status is self-reported and is not a medical eligibility decision. Blood-bank staff must confirm final eligibility, including clinical checks, at donation. Organ donation is outside this prototype's scope.

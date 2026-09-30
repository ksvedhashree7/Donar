# Organ Donor Matching Platform: GitHub Copilot Prompt Pack

**Tagline:** Verified, Location-Aware, Consent-Based Organ Donor Matching

## How to use this pack

1. Create the repo with two folders: `/backend` and `/frontend`.
2. Save **Part A** as `.github/copilot-instructions.md`. Copilot reads it on every request.
3. Paste **Part B** phase prompts into Copilot Chat (Agent mode) **one at a time**. Do not start the next phase until the current phase's acceptance checks pass.
4. Use **Part C** as your final review checklist and demo script.

---

# PART A: `.github/copilot-instructions.md`

## Project

A full-stack hackathon prototype that helps hospitals identify **potential** organ donors for recipients. It is a decision-support tool, NOT a medical authority.

## Non-negotiable rules

1. The platform never declares medical eligibility, compatibility, or donor approval. Matching output is always labelled **"Potential Match: Requires Medical Review"**.
2. Donor self-reported data is always `SELF_REPORTED`. Only a doctor of an authorized hospital can set `VERIFIED`. Admins, donors, and recipients can never edit verified medical values.
3. Prototype uses **mock/sandbox data only**. Never real patient data.
4. Every read or write of sensitive data creates an audit log entry.
5. Donors can withdraw consent or registration at any time, with no penalty.
6. No feature may allow payment, incentives, or rewards tied to donation (organ trade is illegal in India).
7. Recipients and the public can never browse donors. Contact with a donor is only via the hospital coordination workflow.
8. Status must never rely on colour alone: always icon + text (e.g. "✔ Verified", "⏳ Pending", "⚠ Requires Review", "● Available").

## Stack

- Frontend: React + Vite + TypeScript, React Router, Tailwind CSS, Axios, TanStack Query, Recharts, Leaflet (OpenStreetMap)
- Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL 15
- Auth: short-lived JWT access token + rotating refresh token (httpOnly cookie), Argon2id hashing, TOTP 2FA, OTP (mock provider in dev; console log)
- Storage: S3-compatible (MinIO locally) with pre-signed URLs; medical files encrypted at rest
- Testing: pytest, Vitest, Playwright (one E2E for the demo flow)
- Dev: docker-compose (api, db, minio, frontend), `.env.example`, Makefile

## Coding standards

- Type hints everywhere; small service-layer functions; no business logic in route handlers.
- Every protected endpoint uses a `require_role(...)` dependency AND an object-level ownership/consent check.
- Never return sensitive fields by default; use explicit response schemas.
- Never log PII or medical values. Log IDs only.
- Validate all input with Pydantic; parameterized queries only (SQLAlchemy).
- Add rate limiting on auth and OTP endpoints.
- Each feature ships with tests for authorization (positive AND negative cases).

## Domain context (India)

- Governing law: Transplantation of Human Organs and Tissues Act (THOA) 1994 and its rules. Living unrelated donation requires an **Authorization Committee**. Organ trade is prohibited.
- Bodies: NOTTO (national), ROTTO (regional), SOTTO (state); TRANSTAN for Tamil Nadu. Reference them in the UI's education section and link out to official sites. Do not invent statistics.
- Privacy: DPDP Act 2023 principles: purpose limitation, explicit consent, data minimisation, right to withdraw, right to erasure where legally allowed.
- ID/health integration is **mocked** in the prototype (ABHA ID, DigiLocker-style verification), behind an adapter interface so a real provider can replace it.

## Three donation modes (model these separately)

1. **LIVING_RELATED**: a specific donor–recipient pair (relative/spouse). Workflow: pair registration → compatibility screening by transplant team → Authorization Committee approval (mock stage) → surgery scheduling. Include **paired exchange** as a stretch feature.
2. **DECEASED_PLEDGE_REGISTRY**: a person pledges to donate after death. Pledged donors are **never matched or contacted for a specific recipient**. The registry stores the pledge, organs/tissues, family-coordination contacts, and consent. Show pledge card and family-awareness info.
3. **DECEASED_ALLOCATION_EVENT**: a hospital reports a brain-stem-dead donor with consent. The system **reverse-matches**: organ → ranked recipient waiting list (ABO, size, HLA/crossmatch flags, urgency, waiting time, distance and ischemia-time window). Output goes to the transplant coordinator for review.

- Tissues (cornea, skin, bone) follow tissue/eye-bank workflows, with no urgent-waiting-list matching in the prototype.

## Matching rules (configurable, versioned)

- Rules live in a `matching_rule_sets` table (version, JSON config, approved_by, effective_from). Each match records the rule-set version.
- ABO for solid organs (Rh does not matter for organ ABO compatibility; store it but do not filter on it):

- O donor → O, A, B, AB
- A donor → A, AB
- B donor → B, AB
- AB donor → AB
- Provide a config toggle for ABO-incompatible programs, disabled by default.
- Hard filters (excluded before scoring): organ mismatch, ABO incompatible, donor not `VERIFIED`, verification expired, donor status `WITHDRAWN`/`UNAVAILABLE`, consent not active, donor age outside the rule-set range.
- Soft factors (scored, each shown with its own explanation): urgency, verification freshness, availability, distance, estimated travel time, HLA/crossmatch = **"Requires specialist review"** (never auto-scored as compatible), size/weight match (liver/heart/lung), waiting time.
- Output for each match: `score`, `factors[]` (name, value, weight, explanation, status), `hard_filter_results[]`, `rule_set_version`, `disclaimer`.
- Never say "compatible", "suitable" or "approved". Use "Potential Match".

## Location and availability

- Location is **opt-in**. Store coarse location (city + geohash precision ~5) by default; exact GPS only if the donor enables it, retained for a short window.
- Recipients and the public never see donor location. Hospitals only see distance and travel-time estimate to their own centre, and only for donors with an active match/coordination case.
- Travel mode sets availability to `LIMITED` or `UNAVAILABLE` with dates; being outside the home city never auto-excludes a donor (it's a soft factor).

## Data model additions beyond the base spec

`consents` (versioned, per purpose, withdrawable), `consent_events`, `access_grants` (who may see what, why, until when), `break_glass_events`, `rule_sets`, `match_reviews`, `coordination_cases`, `case_messages`, `authorization_committee_reviews` (mock), `deceased_donor_events`, `organ_offers`, `hospital_staff`, `document_versions`, `field_verifications` (per medical field: value, status, verified_by, hospital_id, verified_at, expires_at, previous_value_hash).

## Audit log design

- Append-only table; DB user for the app has INSERT/SELECT only (no UPDATE/DELETE).
- Each row stores `prev_hash` and `row_hash` (SHA-256 chain) so tampering is detectable. Provide an admin "verify chain" endpoint.
- Record: actor, role, action, resource type/id, purpose (required for medical views), IP, user agent, timestamp, success/fail.

## Break-glass access

For emergencies a doctor may access a donor record without a prior grant by giving a reason. It is logged, immediately alerts hospital admin and the donor, and is reviewed by an admin later.

---

# PART B: PHASE PROMPTS (paste one at a time)

## Phase 0: Scaffold

> Read `.github/copilot-instructions.md`. Scaffold the monorepo: FastAPI backend (app/, routers/, services/, models/, schemas/, core/, tests/), React+Vite+TS frontend, docker-compose with Postgres, MinIO, backend and frontend, `.env.example`, Makefile (`make up`, `make seed`, `make test`), Alembic configured, CORS, health endpoint, ruff + pytest set up. Do not implement features yet.

**Accept when:** `make up` starts all services; `/health` returns 200; the frontend shows a placeholder page.

## Phase 1: Database and migrations

> Create SQLAlchemy models and Alembic migrations for all tables in the instructions file plus the base list (users, roles, permissions, donors, recipients, doctors, hospitals, hospital_staff, medical_profiles, field_verifications, medical_reports, document_versions, organ_preferences, organ_requirements, potential_matches, match_reviews, coordination_cases, appointments, locations, availability, notifications, consents, consent_events, access_grants, audit_logs, emergency_contacts, verification_records, rule_sets, deceased_donor_events, organ_offers). Include PKs (UUID), FKs, indexes (organ, blood_group, city, status, geohash), CHECK constraints for enums, created_at/updated_at. Make `audit_logs` append-only with hash-chain columns and a DB trigger or revoked privileges preventing UPDATE/DELETE.

**Accept when:** `alembic upgrade head` succeeds on a clean DB; a test proves UPDATE on `audit_logs` fails.

## Phase 2: Auth and security

> Implement registration, login, OTP verification (mock provider), refresh-token rotation, logout, logout-all-devices, forgot password via OTP, TOTP 2FA setup/verify, Argon2id hashing, account lockout, rate limiting. Implement RBAC roles (DONOR, RECIPIENT, DOCTOR, HOSPITAL_STAFF, ADMIN) with a `require_role` dependency and an object-level policy layer (`can_view_donor_medical(actor, donor)`) that checks role, hospital association, active access grant and consent. Add audit logging middleware. Write negative authorization tests for every role pair.

**Accept when:** tests prove a donor cannot read another donor, a recipient cannot list donors, and an admin cannot edit verified medical fields.

## Phase 3: Donor registration and consent

> Build the multi-step donor registration (basic info, mode selection among the three donation modes, organ/tissue preferences, emergency contact, consent). Show the disclaimer that selection is not medical authorization. Build versioned consent management: give, view, withdraw, per-purpose consent (medical evaluation, matching, location, contact). Withdrawal immediately sets the donor to non-matchable and is audited. Add a mock ID-verification adapter (ABHA/DigiLocker style). Add an anti-coercion screen: the donor confirms the decision is voluntary and that no payment is involved; store this as a consent event.

**Accept when:** withdrawing consent removes the donor from all match results in the next query.

## Phase 4: Hospital finder and appointments

> Seed 8 mock hospitals in and around Chennai with lat/lng, services, and doctors. Build `/hospitals/nearby` (haversine + optional travel-time estimate), a Leaflet map with list view, and the appointment flow (Requested → Confirmed → Completed / Cancelled / Rescheduled) with notifications to both sides.

## Phase 5: Doctor verification workflow

> Build the Doctor dashboard: appointment queue, donor evaluation form with per-field verification (status, value, notes, expiry), report upload (encrypted, pre-signed URL, type/expiry metadata), and a submit-verification action that moves the donor lifecycle to MEDICAL_EVALUATED → VERIFIED_DONOR_PROFILE. Every change writes `field_verifications` with previous value hash and an audit entry. Show "Verified by Dr. X · Hospital · Date" everywhere verified data appears. Add a mock "AI extraction" helper that pre-fills fields from an uploaded report, flagged **"Unverified suggestion"**; the doctor must confirm each field.

## Phase 6: Recipient and requirement

> Build recipient records (created/verified by hospital staff or doctors), waiting-list status, and organ requirement creation (organ, ABO, urgency, size params, location, hospital). Recipient identity is pseudonymised (e.g. RCP-2041) in all donor-facing or cross-hospital views.

## Phase 7: Matching engine

> Implement the versioned rules engine per the instructions: hard filters, weighted soft factors, per-factor explanations, HLA = "Requires specialist review". Provide (a) living-donor pair screening, (b) deceased-event reverse allocation (organ → ranked waitlist), and (c) a standard requirement → potential donors search restricted to donors who consented to matching. Store results in `potential_matches` with rule-set version. Build the hospital UI: sortable/filterable table, factor breakdown drawer, "Request medical review", "Start coordination". Include unit tests for the ABO matrix, each hard filter, and score explanations.

**Accept when:** a test shows an unverified, expired, withdrawn, or non-consenting donor never appears, and no response text contains "compatible" or "approved" as a conclusion.

## Phase 8: Availability, travel and location

> Availability toggle, travel mode (dates, destination, return, status), city selection, optional GPS, "last updated". Location visible to hospitals only inside an active coordination case. Add unit tests that recipients and public endpoints never return location.

## Phase 9: Emergency workflow

> When a requirement is marked URGENT: run the matching, notify authorized hospital staff, send secure in-app/email/SMS (mock) donor contact requests **only for donors who have consented to urgent contact**, log all communication in `case_messages`, and escalate to the hospital admin after a configurable timeout (background worker). Show an urgent-case timeline.

## Phase 10: Notifications, documents, admin, analytics

> Notification centre (in-app, email and SMS via mock providers) covering all types in the spec plus expiry reminders (background job). Donor can view approved reports. Admin: hospital/doctor verification, user management, audit viewer with filters, hash-chain verification, break-glass review. Analytics dashboard with Recharts: donors by status, organ demand, blood group distribution, monthly registrations, geographic distribution. **k-anonymity rule:** hide any bucket with fewer than 5 records.

## Phase 11: Landing and education

> Public landing page with the specified hero and CTAs; education pages (organ donation basics, living vs deceased, who can register, process, myths vs facts, consent, privacy, FAQ) with a clear "verify with official sources: NOTTO / SOTTO / TRANSTAN" section. Do not fabricate statistics; use placeholders marked `TODO: cite official source`. Include a persistent footer disclaimer.

## Phase 12: Seed data, E2E and polish

> Create `make seed` with: 3 hospitals, 4 doctors, 30 mock donors (mixed statuses, some expired, some travelling, one withdrawn), 6 recipients, 2 requirements including the demo (Kidney, O+, Chennai, High, Demo Transplant Center; donor DNR-1024, O+, verified 15 Sep 2026, 8.4 km, Available). Write one Playwright test that runs the full demo flow. Run an accessibility pass (labels, focus states, contrast, keyboard navigation, status icons + text), mobile-first layout check, and a security pass (headers, CSP, rate limits, secrets, dependency audit).

---

# PART C: FINAL CHECKLIST AND DEMO SCRIPT

## Safety checklist

- [ ] Disclaimer on landing, donor dashboard, match screens, and footer
- [ ] No text claims compatibility, approval, or diagnosis
- [ ] Verified fields are editable only by the doctor who owns the verification
- [ ] Withdrawn or non-consenting donors never appear in matches
- [ ] Recipients and public cannot enumerate donors
- [ ] Location invisible outside active coordination cases
- [ ] Audit chain verifies; the app DB role cannot alter audit rows
- [ ] All data is clearly mock

## Demo script (about 5 minutes)

1. Landing → Register as donor (OTP) → choose Living or Deceased pledge, pick kidney → consent + voluntariness screen.
2. Find nearest hospital → book evaluation.
3. Doctor logs in → verifies fields → uploads report → submits verification. Donor badge turns **✔ Medically Evaluated**.
4. Hospital creates urgent Kidney O+ requirement.
5. Matching shows **DNR-1024: Potential Match, Requires Medical Review** with a factor breakdown (blood group, verification date, 8.4 km, Available, HLA: specialist review).
6. Doctor opens the profile (purpose captured) → starts coordination → donor gets a secure request.
7. Admin shows the audit log and the hash-chain verification.
8. Closing line: *"The platform identifies potential matches. Doctors and authorized committees make every medical decision."*

## Stretch ideas

Paired kidney exchange graph, multilingual UI (Tamil/Hindi), offline-friendly PWA, ABDM sandbox integration, differential-privacy analytics, donor pledge card with QR.

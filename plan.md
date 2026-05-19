# Implementation Plan: Flight Booking System MVP

## 1. Project Initialization & Infrastructure [DONE]
- Initialize Django project with `flights_backend` as the main package.
- Setup environment variables using `python-dotenv`.
- Configure Docker:
    - `Dockerfile`: Multi-stage build for Django.
    - `docker-compose.yml`: Services for `db` (Postgres), `redis`, `web` (Django), and `worker` (Celery).
- Establish modular app structure:
    - `accounts`: User management and Auth.
    - `flights`: Provider API integration and search.
    - `bookings`: Idempotent booking logic.
    - `payments`: Razorpay integration.
    - `agents`: B2B specific features.
    - `tickets`: PNR and ticket management.
    - `core`: Shared utilities, middleware, and base models.

## 2. Authentication Module [DONE]
- Implement custom `User` model with `role` (Customer, Agent, Admin).
- Setup `djangorestframework-simplejwt` for token-based authentication.
- API Endpoints:
    - `POST /api/v1/auth/register/`
    - `POST /api/v1/auth/login/`
    - `POST /api/v1/auth/refresh/`
    - `GET /api/v1/auth/profile/`

## 3. Flight Search & Provider Integration
- Create a `ProviderService` to wrap the API documented in `apidoc.md`.
- Implement normalization logic to convert provider-specific JSON to a clean, frontend-ready structure.
- API Endpoints:
    - `POST /api/v1/flights/search/`: Support one-way/round-trip.
    - `POST /api/v1/flights/revalidate/`: Mandatory price check before booking.
- Apply B2B markup percentages for `AGENT` users during search.

## 4. Booking Management
- Implement `IdempotencyKey` model and middleware/decorator to prevent duplicate bookings.
- Define `Booking` model with states: `INITIATED`, `PAYMENT_PENDING`, `PROCESSING`, `CONFIRMED`, `FAILED`, `CANCELLED`.
- Ensure all booking operations are wrapped in atomic database transactions.
- API Endpoints:
    - `POST /api/v1/bookings/create/`: Atomic creation of booking and passengers.
    - `GET /api/v1/bookings/{id}/`: Detailed status view.
    - `GET /api/v1/bookings/history/`: Paginated user-specific history.

## 5. Payment Processing
- Integrate Razorpay SDK.
- API Endpoints:
    - `POST /api/v1/payments/initiate/`: Create Razorpay order and link to booking.
    - `POST /api/v1/payments/verify/`: Verify Razorpay signature and update booking to `PROCESSING`.
    - `POST /api/v1/payments/webhook/`: Handle async notifications from Razorpay.

## 6. Async Ticketing & Celery
- Configure Celery with Redis as the broker.
- Create `issue_ticket_task`:
    - Calls provider's `Air_Ticketing` API.
    - Updates booking status to `CONFIRMED`.
    - Stores PNR and ticket info.
    - Implements retry logic with exponential backoff for network failures.
- Implement email notification task upon confirmation.

## 7. B2B Agent Features
- Simple `AgentProfile` to store markup percentage.
- Agent-specific dashboard views for booking history.

## 8. Admin & Monitoring
- Configure Django Admin for all models.
- Implement custom admin actions for manual ticket reconciliation.
- Setup logging for all third-party API interactions and failure points.

## 9. Security & Quality Assurance
- Use `DRF` permission classes for role-based access.
- Implement rate limiting for search and auth endpoints.
- Write unit tests for core services (normalization, markup, payment verification).
- Integration tests for the full booking flow (search -> revalidate -> book -> pay).

## 7-Day Implementation Schedule

### Day 1: Project Setup & Foundation [DONE]
- [x] Initialize Django project and app structure (`accounts`, `flights`, `bookings`, `payments`, `agents`, `tickets`, `core`).
- [x] Configure Docker & Docker Compose (PostgreSQL, Redis, Celery).
- [x] Setup `core` app: Base models (UUID, timestamps), centralized exception handling, and standard response middleware.
- [x] Environment configuration (`.env.example`).

### Day 2: Authentication & Role Management [DONE]
- [x] Implement Custom User model with roles: `CUSTOMER`, `AGENT`, `ADMIN`.
- [x] Integrate `SimpleJWT` for authentication.
- [x] Build Auth APIs: Register, Login, Refresh, and Profile.
- [x] Implement role-based permission classes.

### Day 3: Flight Search & Provider Integration
- [ ] Build `ProviderService` to wrap external Flight API.
- [ ] Implement fare normalization logic (convert provider JSON to clean internal format).
- [ ] Create `POST /api/v1/flights/search/` endpoint.
- [ ] Setup logging for all provider API requests/responses.

### Day 4: Fare Revalidation & B2B Markup
- [ ] Implement `POST /api/v1/flights/revalidate/` logic.
- [ ] Build Agent markup system (apply percentage markup to search results for `AGENT` users).
- [ ] Add flight search validation (date checks, sector validation).

### Day 5: Idempotent Booking System
- [ ] Implement `IdempotencyKey` model and logic.
- [ ] Build `Booking` and `Passenger` models with transactional integrity.
- [ ] Create `POST /api/v1/bookings/create/` (idempotent endpoint).
- [ ] Define booking state machine transitions.

### Day 6: Payments & Razorpay Integration
- [ ] Integrate Razorpay SDK and build `PaymentService`.
- [ ] Implement `POST /api/v1/payments/initiate/` (create Razorpay order).
- [ ] Implement `POST /api/v1/payments/verify/` (signature verification).
- [ ] Build Webhook handler for async payment success/failure.

### Day 7: Async Ticketing & Final Polish
- [ ] Create Celery task for `issue_ticket` (calls provider ticketing API).
- [ ] Build Ticket retrieval and PNR storage logic.
- [ ] Custom Django Admin configuration for monitoring.
- [ ] Run integration tests and final code cleanup.
